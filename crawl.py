from playwright.async_api import async_playwright
import asyncio
from pathlib import Path
import hashlib
from playwright.async_api import Page
import argparse, sys, os

# oss相关环境变量
ENDPOINT = os.getenv('OSS_ENDPOINT')
BUCKET_NAME = os.getenv('OSS_BUCKET_NAME')
ACCESS_KEY_ID = os.getenv('OSS_ACCESS_KEY_ID')
ACCESS_KEY_SECRET = os.getenv('OSS_ACCESS_KEY_SECRET')
USE_OSS = all([ENDPOINT, BUCKET_NAME, ACCESS_KEY_ID, ACCESS_KEY_SECRET])

# 爬虫本体相关常量
LINK_URL = "https://www.memedroid.com/memes/random"
MAX_PAGE_NUM = 1
NUM_PER_PAGE = 20
SAVE_PATH = Path("./downloaded_memes")


def parse_cli():
    p = argparse.ArgumentParser(description="Memedroid 图片批量下载")
    p.add_argument(
        "-p", "--pages", type=int, default=10, help="要抓取的页数（默认 10）"
    )
    args = p.parse_args()
    # 如果用户给的是 0 或负数，也强制用默认值
    return args.pages if args.pages > 0 else 10


# 保存图片
async def save_image(image_url: str, page: Page):
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


async def main():
    # 根据页码生成对应的URL
    def get_page_url(num):
        return LINK_URL + f"?page={num}"

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
                await page.goto(page_url, wait_until="domcontentloaded")
                # 等待图片加载完成
                await page.locator(".img-responsive").last.wait_for()
                # 获取图片元素
                img_elements = await page.locator("picture .img-responsive").all()
                for img in img_elements:
                    src = await img.get_attribute("src")
                    if src is None:
                        raise Exception("Image src attribute is empty")
                    else:
                        await save_image(src, page)
        except Exception as e:
            print(f"Error occurred: {e}")


if __name__ == "__main__":
    MAX_PAGE_NUM = parse_cli()
    asyncio.run(main())
