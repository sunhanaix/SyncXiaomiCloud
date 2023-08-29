#配置相关个人信息
SYNC_DIR=r'e:\XiaoMi' #从小米云上拉下来的数据存放的目录
device_id='wb_50894a5e-3ee3-4205-8322-d3e1361a9ef3'  #这个要网页登录小米云，用fiddler抓包或者F12去找到自己的device_id才行，这个默认值必须修改掉！
username='13901238888' #登录的用户名
password='abc1234' #登录的密码
do_sha1_first=False #是否强制重新扫描目标目录所有文件，重新计算sha1，建议怀疑本地文件有额外copy进入文件时，将之为True
down_and_del=False  #下载后，是否删除小米云上图片/视频信息？