import asyncio
from pathlib import Path
import hashlib
from config_loader import CONFIG
import alibabacloud_oss_v2 as oss
import alibabacloud_oss_v2.aio as oss_aio
import cloudscraper
from bs4 import BeautifulSoup
import httpx

# 阿里云 OSS 相关常量
# 凭证信息
CREDENTIALS_PROVIER = oss.credentials.StaticCredentialsProvider(
    access_key_id=CONFIG["oss"]["access_key_id"],
    access_key_secret=CONFIG["oss"]["access_key_secret"],
)
OSS_CONFIG = oss.config.load_default()
OSS_CONFIG.credentials_provider = CREDENTIALS_PROVIER
OSS_CONFIG.region = CONFIG["oss"]["region"]
OSS_CLIENT = oss_aio.AsyncClient(OSS_CONFIG)

# 爬虫本体相关常量
LINK_URL = "https://www.memedroid.com/memes/random"
MAX_PAGE_NUM = CONFIG["crawler"]["max_page_num"]
NUM_PER_PAGE = 20
SAVE_PATH = Path(CONFIG["crawler"]["save_path"])


async def save_image_oss(image_url: str):
    """
    上传到oss

    :param image_url: 图片链接
    :type image_url: str
    """
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(image_url)
            resp.raise_for_status()
            data = resp.content
            name = (
                str(Path(CONFIG["crawler"]["save_path"]))
                + "/"
                + (hashlib.md5(data).hexdigest() + ".jpg")
            )
            # 上传到阿里云OSS
            put_object_request = oss.PutObjectRequest(
                bucket=CONFIG["oss"]["bucket_name"], key=name, body=data
            )
            await OSS_CLIENT.put_object(put_object_request)
            print(f"Uploaded image to OSS: {name}")
        except Exception as e:
            print(f"Request error: {e}")
            return
        finally:
            # 关闭 OSS 客户端连接
            await OSS_CLIENT.close()


async def save_image_local(image_url: str):
    # 没有文件夹则创建路径
    SAVE_PATH.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(image_url)
            resp.raise_for_status()
            data = resp.content
            name = hashlib.md5(data).hexdigest() + ".jpg"
            filepath = SAVE_PATH / name
            if filepath.exists():
                print(f"Image already exists: {name}")
                return
            else:
                filepath.write_bytes(data)
                print(f"Saved image: {name}")
        except Exception as e:
            print(f"Request error: {e}")
            return


async def get_image_list(save_oss: bool):
    scraper = cloudscraper.create_scraper()
    def get_page_url(num):
        return LINK_URL + f"?page={num}"
    result = []
    try:
        # 循环访问页面
        for i in range(1, MAX_PAGE_NUM + 1):
            page_url = get_page_url(i)
            response = scraper.get(page_url, timeout=500)
            response.raise_for_status()
            # 获取对应的html
            html = response.text
            soup = BeautifulSoup(html, "html.parser")
            image_nodes = soup.select("picture .img-responsive")
            if len(image_nodes) <= 0:
                raise Exception("no data")
            for node in image_nodes:
                print(node["src"])
                if save_image_oss:
                    await save_image_oss(str(node["src"]))
                else:
                    await save_image_local(str(node["src"]))
    except Exception as e:
        print(e)


if __name__ == "__main__":
    asyncio.run(get_image_list(save_oss=True))
