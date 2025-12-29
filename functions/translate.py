from typing import List
import httpx
import functions.youdao_utils as youdao_utils
import asyncio
from pathlib import Path
import base64
import alibabacloud_oss_v2 as oss
import alibabacloud_oss_v2.aio as oss_aio
from functions.config_loader import CONFIG

# # 有道的应用ID和密钥，从配置文件中获取
APP_ID = CONFIG["translate"]["app_id"]
APP_SECRET = CONFIG["translate"]["app_secret"]

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

# 接口地址
URL = "https://openapi.youdao.com/ocrtransapi"
INPUT_DIR = Path(CONFIG["crawler"]["save_path"])
OUTPUT_DIR = Path(CONFIG["translate"]["output_path"])


async def save_image_oss(base64_str: str, origin_path: Path) -> None:
    """
    上传到oss

    :param base64_str: base64编码后的英文图片字符串
    :type base64_str: str
    :param origin_path: 英文版图片的Path路径
    :type origin_path: Path
    """
    try:
        image_bytes = base64.b64decode(base64_str)
        name = str(Path(CONFIG["crawler"]["save_path"])) + "/" + (base64_str + ".jpg")
        # 上传到阿里云OSS
        put_object_request = oss.PutObjectRequest(
            bucket=CONFIG["oss"]["bucket_name"], key=name, body=image_bytes
        )
        await OSS_CLIENT.put_object(put_object_request)
        print(f"Uploaded translated image to OSS: {name}")
    except Exception as e:
        print(f"OSS upload error: {e}")
        return

async def save_image_local(base64_str: str, origin_path: Path) -> None:
    """
    本地保存图片

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

async def translate_one_from_oss(key:str) -> None:
    """
    translate_one 翻译一张图片
    :param key: 图片在OSS中的key
    :type key: str
    """
    try:
        get_request = oss.GetObjectRequest(
            bucket=CONFIG["oss"]["bucket_name"],
            key = key
        )
        response = await OSS_CLIENT.get_object(get_request)
        if not response.body:
            raise Exception(f"Failed to download image from OSS: {key}")
        # FIXME: 这里的问题不知道怎么修复，但是代码本身是没问题的
        image_bytes = await response.body.read() #type: ignore
        if isinstance(image_bytes,bytes):
            base64_str = base64.b64encode(image_bytes).decode()
        else:
            raise Exception(f"Failed to change b64 : {key}")
        print(base64_str)
        data = {"q": base64_str, "from": "auto", "to": "auto", "render": "1", "type": "1"}
        httpx.post(
            URL
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
            # TODO: 存储到阿里云OSS的判定
            await save_image_local(response_obj["render_image"], Path(key))
    except Exception as e:
        print(e)
    finally:
        await OSS_CLIENT.close()

async def get_en_list_from_oss() ->List[str] :
    """
    从阿里云OSS容器中提取图片列表
    """
    try:
        object_keys = []
        continuation_token = None
        get_objects_request = oss.ListObjectsV2Request(
            bucket=CONFIG["oss"]["bucket_name"],
            # 这里其实写死也没事，毕竟阿里云oss用的就是'/'，如果你用Path的话，在win上面反而会拼错
            prefix=CONFIG["crawler"]["save_path"] + "/",
            max_keys=CONFIG["translate"]["max_key_length"],
            continuation_token=continuation_token,
        )
        # 获取对象列表
        result = await OSS_CLIENT.list_objects_v2(get_objects_request)
        if result.contents is not None:
            for obj in result.contents:
                print(f"Found object in OSS: {obj.key}")
                object_keys.append(obj.key)
        else:
            raise Exception("No objects found in OSS bucket.")
    except Exception as e:
        print(f"OSS get object error: {e}")
    finally:
        await OSS_CLIENT.close()
        return object_keys


async def translate_all() -> None:
    """
    翻译INPUT_DIR下面的所有图片
    TODO: 从阿里云OSS容器中提取，然后改造这一段。翻译已经写完了，之后就可以写这边了
    """
    # await get_en_list_from_oss()
    await translate_one_from_oss('memes_en/ItemSprite_diamond.png')

    # finished_images = {p.name for p in OUTPUT_DIR.iterdir()}
    # image_files = [p for p in INPUT_DIR.iterdir() if p.name not in finished_images]
    # for i in image_files:
    #     await translate_one(i)


if __name__ == "__main__":
    asyncio.run(translate_all())
