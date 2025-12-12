import httpx,os


APP_ID = '700bb7060b88d1c5'
APP_SECRET = 'RFSYK000eGR41yUvRoCj9Mn7wjp0V4gW'
# # 有道的应用ID和密钥，从环境变量中获取
# APP_ID = os.getenv("APP_ID")
# APP_SECRET = os.getenv("APP_SECRET")

# 接口地址
URL = "https://openapi.youdao.com/ocrtransapi"

async def translate():
    httpx.post(URL,data={
        'type': '1',
        'from'  : 'auto',
        'to' : 'auto',
        'appKey': APP_ID,
        'salt': 


    })