import os,json,sys,glob
import sqlite3
import urllib3

import sys
import base64
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import psutil

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def dpapi_decrypt(encrypted):  # 老版本Chrome解密方法
    import ctypes
    import ctypes.wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [('cbData', ctypes.wintypes.DWORD),
                    ('pbData', ctypes.POINTER(ctypes.c_char))]

    p = ctypes.create_string_buffer(encrypted, len(encrypted))
    blobin = DATA_BLOB(ctypes.sizeof(p), p)
    blobout = DATA_BLOB()
    retval = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(blobin), None, None, None, None, 0, ctypes.byref(blobout))
    if not retval:
        raise ctypes.WinError()
    result = ctypes.string_at(blobout.pbData, blobout.cbData)
    ctypes.windll.kernel32.LocalFree(blobout.pbData)
    return result


def aes_decrypt(encrypted_txt):  # 新版本Chrome解密方法
    with open(os.path.join(os.environ['LOCALAPPDATA'],
                           r"Google\Chrome\User Data\Local State"), encoding='utf-8', mode="r") as f:
        jsn = json.loads(str(f.readline()))
    encoded_key = jsn["os_crypt"]["encrypted_key"]
    encrypted_key = base64.b64decode(encoded_key.encode())
    encrypted_key = encrypted_key[5:]
    key = dpapi_decrypt(encrypted_key)
    nonce = encrypted_txt[3:15]
    cipher = Cipher(algorithms.AES(key), None, backend=default_backend())
    cipher.mode = modes.GCM(nonce)
    decryptor = cipher.decryptor()
    return decryptor.update(encrypted_txt[15:])


def chrome_decrypt(encrypted_txt):  # 封装后Chrome解密函数
    if sys.platform == 'win32':
        try:
            if encrypted_txt[:4] == b'x01x00x00x00':
                decrypted_txt = dpapi_decrypt(encrypted_txt)
                return decrypted_txt.decode()
            elif encrypted_txt[:3] == b'v10':
                decrypted_txt = aes_decrypt(encrypted_txt)
                return decrypted_txt[:-16].decode()
        except WindowsError:
            return None
    else:
        raise WindowsError


def get_cookies_from_chrome(domain=None, sql=None):  # 给定域名，返回这个域名下的cookie信息
    if not sql:
        sql = f'SELECT name, encrypted_value as value FROM cookies where host_key like "%{domain}%"'
    else:
        sql = sql
    files=get_chrome_db_path()
    cookie_db =files.get('cookie_file')
    if os.environ.get('debug'):
        print("in get_cookies_from_chrome(),db=%s,sql=%s" % (cookie_db,sql))
    
    dsn = 'file:' + cookie_db + '?mode=ro&nolock=1'
    #con = sqlite3.connect(filename)
    con=sqlite3.connect(dsn,uri=True)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute(sql)
    cookie = ''
    for row in cur:
        if row['value'] is not None:
            name = row['name']
            value = chrome_decrypt(row['value'])
            if value is not None:
                cookie += name + '=' + value + ';'
    return cookie


def get_url_from_chrome(url_query):  # 给定一个URL的SQL where条件查询语句，返回最后一条的url记录
    files=get_chrome_db_path()
    history_db = files.get('history_file')
    dsn = 'file:' + history_db + '?mode=ro&nolock=1'  # 设置只读方式打开，无锁方式，Chrome启动时会锁住History库，所以得nolock
    # print(dsn)
    con = sqlite3.connect(dsn, uri=True)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    sql = "SELECT * FROM urls where url like '%s' order by last_visit_time desc limit 1;" % url_query
    cur.execute(sql)
    for row in cur:
        return row['url']


def get_father_domain(
        full_domain):  # 给定类似testcase.software.ibm.com域名的字串，返回['testcase.software.ibm.com','.software.ibm.com','.ibm.com','.com']
    items = full_domain.split('.')
    N = len(items)
    res = []
    for i in range(N):
        one_item = []
        for j in range(i, N):
            one_item.append(items[j])
        one_domain = ".".join(one_item)
        if one_domain == full_domain:
            res.append(one_domain)
        else:
            res.append('.' + one_domain)
    return res


def gen_sql_clause(full_domain):
    domains = get_father_domain(full_domain)
    sql = 'SELECT name, encrypted_value as value FROM cookies'
    if not domains:
        return sql
    where_clause = ' where ' + " or ".join(["host_key='%s' or host_key='.%s'" % (domain,domain) for domain in domains])
    return sql + where_clause


def get_cookie_by_url(url):
    try:
        host = url.split('://', maxsplit=1)[1].split('/', maxsplit=1)[0]
        sql = gen_sql_clause(host)
        res = get_cookies_from_chrome(sql=sql)
    except Exception as e:
        print(e)
        return None
    return res

def get_profile_dir(): #通过后台进程，找到chrome.exe的进程，查看它带的--profile-directory=xx的参数，找到chrome的profile目录
    for process in psutil.process_iter():
        try:
            cmdline = process.cmdline()
            # cmdline类似如下数据：cmdline=['C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', '--profile-directory=Profile 1', '--restart']
            if len(cmdline)<2: #cmd至少要带个参数才行
                continue
            cmd=os.path.basename(cmdline[0])
            #print(f"{cmdline=}")
            if 'chrome.exe' in cmd.lower():
                # 获取chrome进程的所有命令行参数
                #print(f"{cmdline=}")
                #查找cmdline数组元素中，含有--profile-directory的数据元素
                profile_cmdline=[x for x in cmdline if '--profile-directory' in x]
                #print(f"{profile_cmdline=}")
                #如果找到了，数据长度>0，然后返回等号=后部分的内容
                if len(profile_cmdline)>0:
                    #print(f"{profile_cmdline=}")
                    return profile_cmdline[0].split('=')[1]
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

def search_file_in_path(fname,path):#在一个path下面遍历所有子目录，返回找到的第一个文件绝对路径
    search_path=os.path.join(path,'**')
    search_files = glob.glob(os.path.join(search_path, fname), recursive=True)
    # 遍历所有找到的文件，输出其所在的路径
    for search_file in search_files:
        file_path = os.path.abspath(search_file)
        return file_path

def get_chrome_db_path(): #通过去profile目录里面去找cookie和history文件，返回找到的绝对路径
    # 指定要查找的文件名
    file_name = 'cookies'
    data_path = os.path.join(os.environ['LOCALAPPDATA'], r"Google\Chrome\User Data")
    pdir=get_profile_dir()
    if pdir:
        profile_path=os.path.join(data_path,pdir)
    else:
        profile_path = os.path.join(data_path, 'Default')
    # 使用 glob.glob 函数遍历当前目录及其子目录中所有符合条件的文件
    cookie_file=search_file_in_path('cookies',profile_path)
    history_file = search_file_in_path('history', profile_path)
    return {'cookie_file':cookie_file,'history_file':history_file}

if __name__ == '__main__':
    # domain = 'exmail.qq.com'  # 目标网站域名
    # cookie = get_cookies_from_chrome(domain)
    # print(cookie)
    url = 'https://i.mi.com/contacts'
    res = get_cookie_by_url(url)
    print(res)
