import httpx, os, uuid
import youdao_utils
import asyncio
from pathlib import Path
import base64

# # 有道的应用ID和密钥，从环境变量中获取
# APP_ID = os.getenv("APP_ID")
# APP_SECRET = os.getenv("APP_SECRET")
APP_ID = "700bb7060b88d1c5"
APP_SECRET = "RFSYK000eGR41yUvRoCj9Mn7wjp0V4gW"

# 接口地址
URL = "https://openapi.youdao.com/ocrtransapi"
INPUT_DIR = Path("./downloaded_memes")
OUTPUT_DIR = Path("./chinese_memes")


async def save_image(base64_str: str, origin_path: Path) -> None:
    """
    保存图片

    :param base64_str: base64编码后的英文图片字符串
    :type base64_str: str
    :param origin_path: 英文版图片的Path路径
    :type origin_path: Path
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    file_name = origin_path.name
    image_bytes = base64.b64decode(base64_str)
    Path(OUTPUT_DIR / file_name).write_bytes(image_bytes)
    print("translate success:" + file_name)


async def translate_one(path: Path) -> None:
    """
    translate_one 的 翻译一张图片
    
    :param path: 图片路径
    :type path: Path
    """
    base64_str = youdao_utils.readFileAsBase64(path=path)
    data = {"q": base64_str, "from": "auto", "to": "auto", "render": "1", "type": "1"}
    httpx.post(
        URL,
    )
    youdao_utils.addAuthParams(APP_ID, APP_SECRET, data)
    async with httpx.AsyncClient() as client:
        r = await client.post(
            url=URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        r.raise_for_status()
        response_obj = r.json()
        await save_image(response_obj["render_image"], path)


async def translate_all()->None:
    """
    翻译INPUT_DIR下面的所有图片
    """
    finished_images = {p.name for p in OUTPUT_DIR.iterdir()}
    image_files = [p for p in INPUT_DIR.iterdir() if p.name not in finished_images]
    for i in image_files:
        await translate_one(i)


if __name__ == "__main__":
    asyncio.run(translate_all())
