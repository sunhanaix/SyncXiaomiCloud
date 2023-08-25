# SyncXiaomiCloud
Sync Down XiaoMi Cloud's photoes,videos,audios,SMS,contacts  
# requires:
please install requests and openpyxl pkg and use python3.7 +  
# usage:
modify device_id , username and password and target DIR in config.py
put analysis_contact.py/analysis_sms.py/xiaomi_login.py/xiaomi.py to the same folder,  
then execulate ./xiaomi.py  (suggest)
or use ./xiaomi_chrome.py (discard method)

# 描述
给定小米的帐号、密码，登录小米云，  
下载相册照片、视频、通讯录、短信、录音等信息到本地。  
SYNC_DIR存放具体数据存放目录，请自行修改。  
请提前安装好需要的包。  
pip install requests openpyxl ……
由于使用了python3的f'{var}'语法，这个似乎只有3.7以后的版本才支持，请使用python3.7+，或者修改这部分语法为'%s' % var的格式。  
小米云上面记录了每个文件的sha1信息，这样就可以比对本地文件的sha1值是否一样，如果一样的话，就不用下载了，实现断点续传功能。  
# 用法： 
由于对新登入设备访问小米云相册等敏感资源的安全限制，需要手工登录小米云相册，获得device_id信息（比如用fiddler抓包），填入config.py
修改config.py中的用户名和密码和存放同步小米云上的数据目录 
把analysis_contact.py/analysis_sms.py/xiaomi_login.py/xiaomi.py几个文件放在一个目录下。  
执行./xiaomi.py
也可以使用xiaomi_chrome.py方式，此方式，需要你首先要用chrome浏览器，已经成功登录了i.mi.com网站，不要logout。  
此时执行xiaomi_chrome.py，它会去读取chrome浏览器的cookie信息，用那个cookie去登录小米云，下载资源。  
如果想使用Edge浏览器，理论上也是可以，需要修改chrome.py的获得路径部分，变换成edge相关目录。
（把Google\Chrome，替换成Microsoft\Edge），具体如何，还请自行实现。
由于后续基本全部转移到了树莓派上使用此脚本，偶尔在windows上跑这个脚本。都是自动化方式。
另外，**由于在 Chrome Version 114.0.5735.110 后续版本后，对cookie库进行了保护，防止其它程序偷cookie**
已经无法再直接使用偷chrome cookie方式登录了。
**因此xiaomi_chrome.py就停止维护了**，后续所有增加的新特性，bug修复，也都在xiaomi.py上进行，
老版本chrome用户想就像用这个脚本的，或者自己执行chrome.exe --disable-features=LockProfileCookieDatabase
来降低安全性来启动chrome的，非要使用xiaomi_chrome.py的，请自行对比xiaomi.py的变动内容对xiaomi_chrome.py进行修改.
