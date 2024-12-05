# SyncXiaomiCloud
Sync Down XiaoMi Cloud's photoes,videos,audios,SMS,contacts  
# requires:
please install requests and openpyxl pkg and use python3.7 +  
# usage:
modify device_id , username and password and target DIR in config.py
put analysis_contact.py/analysis_sms.py/xiaomi_login.py/xiaomi.py to the same folder,  
then execulate ./xiaomi.py  (suggest)
or use ./xiaomi_chrome.py (discard method)

# 新增docker部署方式
目前做了arm64和x64的两个image，  
可以docker pull sunbeat/sync_xiaomi:x64  
或者docker pull sunbeat/sync_xiaomi:arm64  
进行介质拉取。  
然后docker run -v /xx/config.py:/app/config.py   \  
-v /xx/docker_xiaomi:/app/xiaomi \  
sunbeat/sync_xiaomi:x64  
其中/xx/config.py里面修改成你的配置文件  
/xx/docker_xiaomi修改成你要存放数据的目录  

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
这里以Chrome浏览器方式为例，首先在Chrome浏览器中正确登录小米云，然后在浏览器地址栏中输入地址：
https://account.xiaomi.com ，然后按F12键，调出开发工具，点击开发工具中的左侧Cookies，选择account.xiaomi.com，然后就可以看到deviceId了。
这里要注意的是，当前网站一定是account.xiaomi.com，而不是i.mi.com，因为不同网站，不同的cookie，就没deviceId信息了。
![image](https://github.com/sunhanaix/SyncXiaomiCloud/blob/main/use_Chrome_find_deviceId.jpg?raw=true)
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
来降低安全性来启动chrome的，  
非要使用xiaomi_chrome.py的，请自行对比xiaomi.py的变动内容对xiaomi_chrome.py进行修改.  

## 捐赠

您的捐赠将鼓励我继续完善SyncXiaomiCloud。

* 对于个人用户，可以使用支付宝或者微信进行捐赠。

 
| 支付宝 | 微信支付 |
| ------ | --------- |
| <img src="https://www.sunbeatus.com/alipay.jpg" height="248px" width="164px" title="支付宝" style="display:inherit;"/> | <img src="https://www.sunbeatus.com/wechatpay.jpg" height="248px" width="164px" title="微信支付" style="display:inherit;"/> |

使用 QQ 扫码加入：
* QQ 群：765883686（为控制人数和人员质量，需付费10元入群。微信或支付宝支付后，申请入群时贴上转账单号即可。

![](https://www.sunbeatus.com/xiaomi_cloud_qq_group.jpg)
