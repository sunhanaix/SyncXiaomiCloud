#!/usr/local/bin/python3
import os, sys, re, json, time, requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
import hashlib
import http.cookiejar as cookielib
import datetime
import subprocess
from PIL import Image
from PIL.ExifTags import TAGS
from urllib.parse import urlparse, parse_qsl
from analysis_contact import convert_contact_to_xls
from analysis_sms import convert_sms_to_xls
from xiaomi_login import XiaomiCloudConnector
import shutil
import config as cfg
'''
给定小米的帐号、密码，登录小米云，
下载相册照片、视频、通讯录、短信、录音等信息到本地
SYNC_DIR存放具体数据存放目录，请自行修改
请提前安装好需要的包
pip install requests openpyxl
由于使用了python3的f'{var}'语法，这个似乎只有3.7以后的版本才支持，请使用python3.7+，或者修改这部分语法为'%s' % var的格式
小米云上面记录了每个文件的sha1信息，这样就可以比对本地文件的sha1值是否一样，如果一样的话，就不用下载了，实现断点续传功能
'''

#存放同步数据的地方
SYNC_DIR=cfg.SYNC_DIR

#计算sha1的hash值的时候，哪些扩展名的文件要进行计算
#这里全部用小写，后面比对的时候，也强制小写比较
CHECK_EXT=['.json','.mov','.jpg','jpeg','.png','gif','.mp3','.mp4','wav','aac','wma','flc']

app_path = os.path.dirname(os.path.abspath(sys.argv[0]))
logname=os.path.basename(sys.argv[0]).split('.')[0]+'.log'

if not os.path.isdir(SYNC_DIR):
    os.mkdir(SYNC_DIR)

def now():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

def mylog(ss, log=os.path.join(app_path, logname)):
    ss = str(ss)
    print(now() + '  ' + ss)
    f = open(log, 'a+', encoding='utf8')
    f.write(now() + '  ' + ss + "\n")
    f.close()

def validateTitle(title):
    # title=changeChineseNumToArab(title)
    rstr = r'[\/\\\:\*\?\"\<\>\|]'  # 把不能做文件名的字符处理下
    new_title=title
    try:
        new_title = re.sub(rstr, "_", title)  # 替换为下划线
    except Exception as e:
        print(title)
        mylog(f"error:{title=},failed to convert,reason:{e}")
    return new_title

SUPPORTED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.mov', '.mp4']

def get_photo_datetime(filename): #通过照片的exif信息，获得照片的拍照时间
    try:
        with Image.open(filename) as img:
            exif_data = img._getexif()
            if exif_data:
                for tag, value in exif_data.items():
                    if TAGS.get(tag) == 'DateTimeOriginal':
                        return datetime.datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
        return None
    except Exception:
        return None

def get_video_datetime(filename): #通过ffprobe获得视频meta信息，获得拍摄时间
    try:
        result = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format_tags=creation_time", "-of", "default=noprint_wrappers=1:nokey=1", filename], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0:
            creation_time_str = result.stdout.strip()
            return datetime.datetime.strptime(creation_time_str, "%Y-%m-%dT%H:%M:%S.%fZ")
        return None
    except Exception:
        return None

def get_media_datetime(filename): #给定文件名，通过照片或者视频的exif/meta信息，获得拍摄时间戳
    file_extension = os.path.splitext(filename)[1].lower()
    datetime_from_meta=None
    if file_extension in ('.jpg', '.jpeg', '.png', '.gif'):
        datetime_from_meta = get_photo_datetime(filename)
    elif file_extension in ('.mov', '.mp4'):
        datetime_from_meta = get_video_datetime(filename)
    return datetime_from_meta

def modify_file_timestamp(filename, timestamp): #给定文件名和时间戳，给相关文件修改时间
    if 'debug' in os.environ:
        print(f"{filename=},{timestamp=}")
    try:
        os.utime(filename, (timestamp.timestamp(), timestamp.timestamp()))
    except Exception as e:
        print(f"Error modifying timestamp for {filename}: {e}")

def file_sha1_old(fname): #这个如果文件较大的话，对于树莓派容易内存溢出
    content=open(fname,'rb').read()
    h=hashlib.sha1(content)
    return h.hexdigest().lower()

def file_sha1(fname): #考虑到树莓派的小内存，需要对文件分片进行sha1计算，避免把内存OOM
    file_piece_size=1024*8
    h=hashlib.sha1(b'')
    f=open(fname,'rb')
    buf=f.read(file_piece_size)
    h.update(buf)
    while len(buf)!=0:
        buf=f.read(file_piece_size)
        h.update(buf)
    f.close()
    return h.hexdigest().lower()
    
def get_all_files(start_path,CHECK_EXT,fname,do_real=False): #获得所有指定目录下的需要的文件
    mylog("trying to caculate the sha1 hash info from %s" % start_path)
    sha1_json_file=fname
    if not do_real:
        file_res = {}
        try:
            ss = open(sha1_json_file, 'r', encoding='utf8').read()
            file_res = json.loads(ss)
        except Exception as e:
            print(e)
            file_res = {}
        mylog("sha1 info: %d records loaded" % len(file_res))
        return file_res
    res={}
    for root, dirs, files in os.walk(start_path):
        for fname in files:
            if os.path.splitext(fname)[1].lower() in CHECK_EXT:
                abs_path=os.path.join(root,fname)
                try:
                    sha1=file_sha1(abs_path)
                except Exception as e:
                    mylog(f"caculate sha1 for file:{abs_path} failed! reason:{e}")
                    continue
                if sha1 in res:
                    res[sha1].append(abs_path)
                else:
                    res[sha1]=[abs_path]
    open(sha1_json_file,'w',encoding='utf8').write(json.dumps(res,indent=2,ensure_ascii=False))
    mylog("sha1 info: %d records loaded" % len(res))
    return res

class xiaomi(object):

    def __init__(self,username,password,do_sha1_first=True):
        connector = XiaomiCloudConnector(username, password)
        self.logged = connector.login()
        if not self.logged:
            mylog("login failed")
            return
        self.connector=connector
        self.s=connector._session
        self.uuid=connector._userId
        self.prepare_gallery()
        self.update_cnt=0 #用于存放，本次更新了多少个文件
        self.sha1_file=os.path.join(SYNC_DIR,'sha1.json')
        #下面尝试去遍历SYNC_DIR目录，去获得其下每个文件的sha1信息，如果do_real=True则遍历，否则直接从self.sha1_file中读取上次记录的信息
        self.sha1_info=get_all_files(SYNC_DIR,CHECK_EXT,self.sha1_file,do_real=do_sha1_first)

    def save_sha1_to_file(self): #强制覆盖报错sha1文件信息
        open(self.sha1_file,'w',encoding='utf8').write(json.dumps(self.sha1_info,indent=2,ensure_ascii=False))

    def prepare_gallery(self): #跟踪浏览器记录，访问相册前，都会执行这个，但似乎不执行这个也可以？
        url='https://i.mi.com/gallery/user/lite/index/prepare'
        headers = {
            "User-Agent": self.connector._agent,
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        cookie={'i.mi.com_istrudev':'true',
                'i.mi.com_isvalid_servicetoken':'true',
                }
        fields={'serviceToken':self.s.cookies.get('serviceToken')}
        self.s.post(url,headers=headers,cookies=cookie,data=fields,verify=False,timeout=10)

    def album_list(self): #返回相册列表，有哪些相册的目录信息
        url='https://i.mi.com/gallery/user/album/list?ts=%d&pageNum=0&pageSize=100&isShared=false&numOfThumbnails=1' % (time.time()*100)
        mylog("in album_list(),url=%s" % url)
        album_dir=os.path.join(SYNC_DIR,'album')
        if not os.path.isdir(album_dir):
            os.mkdir(album_dir)
        cookie={'i.mi.com_istrudev':'true',
                'i.mi.com_isvalid_servicetoken':'true',
                }
        r = self.s.get(url, cookies=cookie,verify=False,timeout=30)
        ss=json.dumps(r.json(),indent=2,ensure_ascii=False)
        fname=os.path.join(album_dir,'album_list.json')
        open(fname,'w',encoding='utf8').write(ss)
        mylog(ss)
        self.albums=r.json()['data']['albums']  #相关相册信息，存放到公共区域
        for album in self.albums:
            name=album.get('name')
            if not name:
                if album.get('albumId')=='2'or album.get('albumId')==2:
                    name='截图'
                elif album.get('albumId')=='1'or album.get('albumId')==1:
                    name='相机'
                elif album.get('albumId')=='1000':
                    name='private'
                else: 
                    mylog(f"not name,{name=},{album=}")
            name=validateTitle(name)
            name=os.path.join(album_dir,name)
            album['folder']=name
            if not os.path.isdir(name):
                os.mkdir(name)
    
    #给定相册id信息，起止日期，每次获得数量，获得这个相册下的所有照片/视频信息，返回结果到result里面
    def get_one_album(self,albumId,folder,startDate='20000101',endDate='20991231',pageSize=500):
        results=[]
        i=0
        while True:
            url = 'https://i.mi.com/gallery/user/galleries?ts=%d&startDate=%s&endDate=%s&pageNum=%d&pageSize=%s&albumId=%s' % (
                time.time() * 1000, startDate,endDate,i,pageSize, albumId)
            r = self.s.get(url, verify=False,timeout=40)
            mylog("in get_one_album(),url=%s" % url)
            fname = os.path.basename(folder) + '%d.json' % i
            fname = os.path.join(folder, fname)
            album_details = r.json()
            open(fname, 'w', encoding='utf8').write(json.dumps(album_details, indent=2, ensure_ascii=False))
            results += album_details['data']['galleries']
            if album_details['code']==0 and album_details['data']['isLastPage']:
                return results
            i+=1
        return results

    # 给定一个照片/视频的id信息，把它删除
    def del_one_media(self, id):
        url='https://i.mi.com/gallery/info/delete'
        mylog(f"trying to delete {id=} media")
        data={'id':id,
              'serviceToken':self.s.cookies.get('serviceToken')
              }
        r=self.s.post(url,verify=False,timeout=10,data=data)
        if not r.status_code==200:
            mylog(f"ERROR: del_one_media  ,{id=} failed, status_code<>200" )
            mylog(r.text)
            return False
        result={}
        try:
            result=r.json()
        except Exception as e:
            mylog(f"ERROR: del_one_media  ,{id=} failed, can not decode response json data ,reason:{e}")
            mylog(r.text)
            return False
        if not result['code']==0:
            mylog(f"ERROR: del_one_media  ,{id=} failed, result['code'] is not 0")
            mylog(r.text)
            return False

    #给定一个照片/视频的id信息，以及存放到的目录和文件名，把它下载到对应地方
    def download_one_pic(self,folder,pic_id,fname):
        ts = int(time.time() * 1000)
        url = 'https://i.mi.com/gallery/storage?ts=%d&id=%s&callBack=dl_img_cb_%d_0' % (ts,pic_id,ts)
        print(url)
        if os.environ.get('debug'):
            mylog("cookies=%s" % cookies)
        r=self.s.get(url,verify=False,timeout=10)
        if not r.status_code==200:
            mylog("phase1 ,folder=%s,pic_id=%s failed, status_code<>200" % (folder,pic_id))
            mylog(r.text)
            return False
        result={}
        try:
            result=r.json()
        except Exception as e:
            print(e)
            mylog("folder=%s,pic_id=%s failed" % (folder, pic_id))
            mylog(r.text)
            return False
        if not result['code']==0:
            mylog("folder=%s,pic_id=%s failed" % (folder, pic_id))
            mylog(r.text)
            return False
        next_url=result['data']['url']
        print(next_url)
        r=self.s.get(next_url,verify=False,timeout=10)
        if not r.status_code==200:
            mylog("phase2 ,folder=%s,pic_id=%s failed, status_code<>200" % (folder, pic_id))
            mylog(r.text)
            return False
        result={}
        try:
            reg = re.search(r'\((.+)\)', r.text)
            result=json.loads(reg.group(1))
        except Exception as e:
            print(e)
            mylog("folder=%s,pic_id=%s failed" % (folder, pic_id))
            mylog(r.text)
            return False
        if not result:
            mylog("folder=%s,pic_id=%s failed" % (folder, pic_id))
            mylog(r.text)
            return False
        real_url=result['url']
        print(real_url)
        meta=result['meta']
        try:
            block_size = 1024 * 1024  
            r=self.s.post(real_url,data={'meta':meta},verify=False,timeout=3600,stream=True)
            if not r.status_code==200:
                mylog("phase3 ,downloading pic,folder=%s,pic_id=%s failed, status_code<>200" % (folder, pic_id))
                mylog(r.text)
                return False
            total_size = int(r.headers.get('content-length', 0)) 
            print(f"Total size: {total_size/1024/1024:.2f} MB")  
            downloaded_size = 0 
            with open(fname, 'wb') as f:
                while downloaded_size < total_size:
                    data = r.raw.read(block_size) 
                    f.write(data)
                    downloaded_size += block_size
        except Exception as e:
            mylog(f"ERROR: in phase3 ,downloading pic,folder={folder},pic_id={pic_id} failed, reson: {e}")
            return None
        #open(fname,'wb').write(r.content) 这个容易导致内存不足
        datetime_from_meta = get_media_datetime(fname)
        if datetime_from_meta:
            modify_file_timestamp(fname, datetime_from_meta)
        if cfg.down_and_del: #要是设置了下载后就删除云端的参数，执行删除操作
            self.del_one_media(pic_id)
        return file_sha1(fname)
    
    #给定一个dict格式的相册信息，对整个相册进行下载
    def download_album(self, folder,one_album):
        for one_pic in one_album:
            pic_name=one_pic.get('fileName')
            sha1=one_pic.get('sha1').lower()
            size=one_pic.get('size')
            id=one_pic.get('id')
            if not pic_name:
                mylog("in download_album for %s failed, can not get fileName" % folder)
            if not id:
                mylog("in download_album for %s failed, can not get id" % folder)
            pic_name=os.path.join(folder,pic_name)
            mylog("trying to download %s" % pic_name)
            if sha1 in self.sha1_info:
                if os.path.isfile(pic_name):
                    mylog("%s already in local dir : %s , will not download it" % (pic_name,folder))
                else:
                    mylog("%s already in local:%s, but not in local dir:%s,trying to link it locally" % (pic_name,self.sha1_info[sha1],folder))
                    try:
                        os.link(self.sha1_info[sha1][0],pic_name)
                    except Exception as e:
                        mylog(f"make hard link failed from {self.sha1_info[sha1][0]} to {pic_name},reason:{e}")
                        if os.path.isfile(self.sha1_info[sha1][0]):
                            shutil.copy(self.sha1_info[sha1][0], pic_name)
                        else:
                            mylog(f"{self.sha1_info[sha1][0]} was gone, maybe deleted,will ignore")
                continue
            sha1_written=self.download_one_pic(folder=folder, pic_id=id,fname=pic_name)
            if not sha1_written: #download_one_pic失败的话，很可能是session过期了，需要重新login下
                self.logged = self.connector.login()
                if not self.logged:
                    mylog("re-login failed")
                    continue
                self.s=self.connector._session
                sha1_written=self.download_one_pic(folder=folder, pic_id=id,fname=pic_name)
            if not sha1_written==sha1:
                mylog("%s sha1 writen not right" % pic_name)
                continue
            self.sha1_info[sha1]=[pic_name]
            self.update_cnt+=1
            if self.update_cnt % 10 ==0: #每次下载了10个照片/视频，就更新一次sha1下信息文件，下次断点续传的时候，可以少下载些
                mylog(f"updated {self.update_cnt} records in this time")
                mylog(f"do save_sha1_to_file:{self.sha1_file}")
                self.save_sha1_to_file()

    def get_album_info(self): #根据前面获得的总的相册信息（self.albums），把每个子相册的详细内容获得，并扔到self.albums_details数组中
        self.albums_details=[]
        for album in self.albums:
            id=album.get('albumId')
            if not id:
                mylog("%s can not get albumId! ignore it" % album.get('folder'))
                continue
            num=album.get('mediaCount')
            if not num:
                mylog("%s can not get mediaCount! ignore it" % album.get('folder'))
                continue
            folder=album.get('folder')
            if not folder:
                mylog("%s can not get folder name! ignore it")
                mylog(album)
                continue
            print("trying for %s" % folder)
            album_details=self.get_one_album(id,folder)
            fname=os.path.basename(folder)+'.json'
            fname=os.path.join(folder,fname)
            open(fname,'w',encoding='utf8').write(json.dumps(album_details,indent=2,ensure_ascii=False))
            self.albums_details.append({'folder':folder,'json_name':fname,'album':album_details})
    
    #获取相关的所有录音记录信息
    def record_list(self,offset=0,limit=500): #返回录音文件信息，有哪些录音文件
        url='https://i.mi.com/sfs/%s/ns/recorder/dir/0/list?offset=%s&limit=%s&_dc=%d&uuid=%s' % (
            self.uuid,offset,limit,time.time()*1000,self.uuid)
        mylog("in record_list(),url=%s" % url)
        record_dir=os.path.join(SYNC_DIR,'record')
        if not os.path.isdir(record_dir):
            os.mkdir(record_dir)
        r = self.s.get(url, verify=False,timeout=10)
        ss=json.dumps(r.json(),indent=2,ensure_ascii=False)
        self.record_dir=record_dir
        fname=os.path.join(record_dir,'record_list.json')
        open(fname,'w',encoding='utf8').write(ss)
        mylog("record json was writtn in  %s" % fname)
        mylog(ss)
        self.record=r.json()['data']['list']  #相关录音信息，存放到公共区域

    #给定录音文件的id，对它进行下载到本地
    def download_one_record(self,id,fname): #下载一个音频文件
        ts = int(time.time() * 1000)
        url = 'https://i.mi.com/sfs/%s/ns/recorder/file/%s/storage' % (self.uuid,id)
        print(url)
        if os.environ.get('debug'):
            mylog("cookies=%s" % cookies)
        r=self.s.get(url,verify=False,timeout=10)
        if not r.status_code==200:
            mylog("download_one_record() phase1 ,fname=%s,id=%s failed, status_code<>200" % (fname,id))
            mylog(r.text)
            return False
        result={}
        try:
            result=r.json()
        except Exception as e:
            print(e)
            mylog("download_one_record(), fname=%s,id=%s failed" % (fname, id))
            mylog(r.text)
            return False
        if not result['code']==0:
            mylog("download_one_record() fname=%s,pic_id=%s failed" % (fname, id))
            mylog(r.text)
            return False
        next_url=result['data']['url']
        print(next_url)
        r=self.s.get(next_url,verify=False,timeout=10)
        if not r.status_code==200:
            mylog("download_one_record() phase2 ,fname=%s,id=%s failed, status_code<>200" % (fname, id))
            mylog(r.text)
            return False
        result={}
        try:
            reg = re.search(r'\((.+)\)', r.text)
            result=json.loads(reg.group(1))
        except Exception as e:
            print(e)
            mylog("download_one_record() fname=%s,id=%s failed" % (fname, id))
            mylog(r.text)
            return False
        if not result:
            mylog("download_one_record() fname=%s,id=%s failed" % (fname, id))
            mylog(r.text)
            return False
        real_url=result['url']
        print(real_url)
        meta=result['meta']
        r=self.s.post(real_url,data={'meta':meta},verify=False,timeout=3600)
        if not r.status_code==200:
            mylog("download_one_record() phase3 ,downloading record,fname=%s,id=%s failed, status_code<>200" % (fname, id))
            mylog(r.text)
            return False
        open(fname,'wb').write(r.content)
        mylog("%s was written" % fname)
        return file_sha1(fname)

    #下载所有的录音信息
    def download_all_records(self):
        for one_record in self.record:
            sha1=one_record.get('sha1')
            name=one_record.get('name')
            id=one_record.get('id')
            if not name:
                mylog("can not get name for this record: %s" % one_record)
                continue
            if not id:
                mylog("can not get id for this record: %s" % one_record)
                continue
            name=name.lower()
            if name.find('.mp3') >-1:
                name=name.split('.mp3')[0]+'.mp3'
            elif name.find('.aac') >-1:
                name = name.split('.aac')[0] + '.aac'
            elif name.find('.mp4') >-1:
                name=name.split('.mp4')[0]+'.mp4'
            elif name.find('.wav') >-1:
                name=name.split('.wav')[0]+'.wav'
            elif name.find('.wma') >-1:
                name=name.split('.wma')[0]+'.wma'
            elif name.find('.flc') >-1:
                name=name.split('.flc')[0]+'.flc'
            else:
                name=name
            fname=validateTitle(name) #去掉name中的特殊字符，免得无法保存
            fname=os.path.join(self.record_dir,fname)
            if sha1 in self.sha1_info:
                mylog("%s already in local:%s" % (fname, self.sha1_info[sha1]))
                continue
            sha1_written=self.download_one_record(id=id,fname=fname)
            if not sha1_written:
                self.logged = self.connector.login()
                if not self.logged:
                    mylog("re-login failed")
                    continue
                self.s=self.connector._session
                sha1_written=self.download_one_record(id=id,fname=fname)
            if not sha1_written==sha1:
                mylog("%s sha1 writen not right" % pic_name)
                continue
            self.sha1_info[sha1]=[fname]
            self.update_cnt+=1
            if self.update_cnt % 10 ==0:
                mylog(f"updated {self.update_cnt} records in this time")
                mylog(f"do save_sha1_to_file:{self.sha1_file}")
                self.save_sha1_to_file()

    #获得通讯录信息，结果存到一个json文件中，供后续格式化到excel使用
    def get_contacts(self,limit=400):
        syncTag = 0
        syncIgnoreTag = 0
        self.contracts={}
        contract_dir=os.path.join(SYNC_DIR,'contracts')
        if not os.path.isdir(contract_dir):
            os.mkdir(contract_dir)
        mylog("trying to get contracts info")
        while True:
            url='https://i.mi.com/contacts/%s/initdata?_dc=%d&syncTag=%s&limit=%s&syncIgnoreTag=%s&uuid=%s' % (
                self.uuid,time.time()*1000,syncTag,limit,syncIgnoreTag,self.uuid)
            print(url)
            r = self.s.get(url, verify=False,timeout=20)
            if not r.status_code==200:
                mylog("status_code<>200 ,can not get contacts")
                mylog(r.text)
                return False
            result = {}
            try:
                result = r.json()
            except Exception as e:
                print(e)
                mylog("can not get contacts")
                mylog(r.text)
                return False
            if not result['code'] == 0:
                mylog("can not get contacts")
                mylog(r.text)
                return False
            fname=os.path.join(contract_dir,'contact%s.json' % syncTag)
            open(fname,'w',encoding='utf8').write(json.dumps(result['data'],indent=2,ensure_ascii=False))
            self.contracts.update(result['data']['content'])
            if result['data']['lastPage']:
                break
            syncTag=result['data']['syncTag']
            syncIgnoreTag = result['data']['syncIgnoreTag']
        fname = os.path.join(contract_dir, 'contact.json')
        open(fname, 'w', encoding='utf8').write(json.dumps(self.contracts,indent=2,ensure_ascii=False))
        mylog("contracs info was written to %s" % fname)
        return fname
    
    #获得短信记录信息，结果存在一个json文件中，供后续格式成excel格式使用
    def get_sms(self,limit=400,readMode='older',withPhoneCall='true'):
        syncTag = 0
        syncThreadTag = 0
        self.sms=[]
        sms_dir=os.path.join(SYNC_DIR,'sms')
        if not os.path.isdir(sms_dir):
            os.mkdir(sms_dir)
        mylog("trying to get SMS info")
        while True:
            url='https://i.mi.com/sms/%s/full/thread?syncTag=%s&syncThreadTag=%s&limit=%s&_dc=%d&readMode=%s&withPhoneCall=%s&uuid=%s' % (
                self.uuid,syncTag,syncThreadTag,limit,time.time()*1000,readMode,withPhoneCall,self.uuid)
            print(url)
            r = self.s.get(url, verify=False,timeout=20)
            if not r.status_code==200:
                mylog("status_code<>200 ,can not get contacts")
                mylog(r.text)
                return False
            result = {}
            try:
                result = r.json()
            except Exception as e:
                print(e)
                mylog("can not get contacts")
                mylog(r.text)
                return False
            if not result['code'] == 0:
                mylog("can not get contacts")
                mylog(r.text)
                return False
            fname=os.path.join(sms_dir,'sms%s.json' % syncThreadTag)
            open(fname,'w',encoding='utf8').write(json.dumps(result['data'],indent=2,ensure_ascii=False))
            self.sms.extend(result['data']['entries'])
            if result['data']['phonecall_view']['lastPage'] or not result['data']['entries']:
                break
            syncTag=result['data']['watermark']['syncTag']
            syncThreadTag = result['data']['watermark']['syncThreadTag']
        fname = os.path.join(sms_dir, 'sms.json')
        open(fname, 'w', encoding='utf8').write(json.dumps(self.sms,indent=2,ensure_ascii=False))
        mylog("SMS info was written to %s" % fname)
        return fname

def main():
    #初始化
    mylog("trying to login Xiaomi Account")
    xm = xiaomi(username=cfg.username,password=cfg.password,do_sha1_first=cfg.do_sha1_first)
    print(xm)
    if not xm.logged:
        sys.exit(-1)
    #开始遍历相册，获得相册列表
    mylog("trying to get album list")
    xm.album_list() #相册信息存放到了xm.albums里面
    #获得每一个相册的具体信息
    mylog("trying to get every album info")
    xm.get_album_info()
    #遍历相册，逐个下载相册（如果图片或者视频的sha1在和本地文件的相同，那么就跳过）
    for one_album in xm.albums_details:
        mylog(f"trying to download {one_album['folder']} pics or videoes")
        xm.download_album(one_album['folder'],one_album['album'])
    mylog("album was downloaded OK!")
    #下载通讯录
    mylog("trying to download contracts")
    contacts_file=xm.get_contacts()
    contact_tgt=os.path.join(SYNC_DIR,'contacts.xlsx')
    phone_dict_file=convert_contact_to_xls(src=contacts_file,tgt=contact_tgt)
    if phone_dict_file:
        mylog("contacts was written to:%s" % contact_tgt)
    else:
        mylog("dealing contacts with error!")
    #下载短信记录
    mylog("trying to download SMS details")
    sms_file=xm.get_sms()
    sms_tgt=os.path.join(SYNC_DIR,'sms.xlsx')
    sms_info=convert_sms_to_xls(src=sms_file,tgt=sms_tgt,contact=phone_dict_file)
    if sms_info:
        mylog("sms was written to: %s" % sms_tgt)
    else:
        mylog("dealing sms with error!")
    #下载录音记录
    mylog("trying to get all record audio list")
    xm.record_list()
    mylog("trying to download recoder mp3")
    xm.download_all_records()
    #更新sha1记录信息
    mylog("trying to update sha1 json file")
    xm.save_sha1_to_file()
    mylog("all sync down was done")

if __name__ == '__main__':
    main()
