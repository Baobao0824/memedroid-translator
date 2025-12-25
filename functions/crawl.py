from playwright.async_api import async_playwright
import asyncio
from pathlib import Path
import hashlib
from playwright.async_api import Page
from functions.config_loader import CONFIG
import alibabacloud_oss_v2 as oss
import alibabacloud_oss_v2.aio as oss_aio

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


async def save_image_oss(image_url: str, page: Page):
    '''
    上传到oss
    
    :param image_url: 图片链接
    :type image_url: str 
    :param page: playwright的page对象
    :type page: Page
    '''
    try:
        resp = await page.request.get(image_url)
        if not resp.ok:
            raise Exception(f"Failed to download image: {image_url}")
        else:
            data = await resp.body()
            name = str(Path(CONFIG["crawler"]["save_path"])) +'/'+ (
                hashlib.md5(data).hexdigest() + ".jpg"
            )
            # 我去原来这么传就行了啊
            # 上传到阿里云OSS
            put_object_request = oss.PutObjectRequest(
                bucket=CONFIG["oss"]["bucket_name"],
                key=name,
                body=data
            )
            await OSS_CLIENT.put_object(put_object_request)
            print(f"Uploaded image to OSS: {name}")
    except Exception as e:
        print(f"Request error: {e}")
        return
    finally:
        # 关闭 OSS 客户端连接
        await OSS_CLIENT.close()


# 保存图片
async def save_image_local(image_url: str, page: Page):
    # 没有文件夹则创建路径
    SAVE_PATH.mkdir(parents=True, exist_ok=True)
    try:
        resp = await page.request.get(image_url)
        if not resp.ok:
            raise Exception(f"Failed to download image: {image_url}")
        else:
            data = await resp.body()
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
    # 根据页码生成对应的URL
    def get_page_url(num):
        return LINK_URL + f"?page={num}"
    result = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()
        try:
            # 循环访问页面
            for i in range(1, MAX_PAGE_NUM + 1):
                page_url = get_page_url(i)
                await page.goto(page_url, wait_until="domcontentloaded", timeout=0)
                # 等待图片加载完成
                await page.locator(".img-responsive").last.wait_for()
                # 获取图片元素
                img_elements = await page.locator("picture .img-responsive").all()
                for img in img_elements:
                    src = await img.get_attribute("src")
                    if src is None:
                        raise Exception("Image src attribute is empty")
                    else:
                        if save_oss:
                            await save_image_oss(src, page)
                        else:
                            await save_image_local(src, page)
        except Exception as e:
            print(f"Error occurred: {e}")


if __name__ == "__main__":
    asyncio.run(get_image_list(save_oss=True))
