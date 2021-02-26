# SyncXiaomiCloud
Sync Down XiaoMi Cloud's photoes,videos,audios,SMS,contacts  
# requires:
please install requests and openpyxl pkg and use python3.7 +  
# usage:
modify xiaomi.py's username and password,  
put analysis_contact.py/analysis_sms.py/xiaomi_login.py/xiaomi.py to the same folder,  
then execulate ./xiaomi.py  

# 描述
给定小米的帐号、密码，登录小米云，  
下载相册照片、视频、通讯录、短信、录音等信息到本地。  
SYNC_DIR存放具体数据存放目录，请自行修改。  
请提前安装好需要的包。  
pip install requests openpyxl。  
由于使用了python3的f'{var}'语法，这个似乎只有3.7以后的版本才支持，请使用python3.7+，或者修改这部分语法为'%s' % var的格式。  
小米云上面记录了每个文件的sha1信息，这样就可以比对本地文件的sha1值是否一样，如果一样的话，就不用下载了，实现断点续传功能。  
# 用法：
修改xiaomi.py中的用户名和密码，  
把analysis_contact.py/analysis_sms.py/xiaomi_login.py/xiaomi.py几个文件放在一个目录下。  
执行./xiaomi.py进行下载自己帐号小米云上的资源  
