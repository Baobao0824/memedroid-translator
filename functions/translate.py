from typing import List
import httpx
import functions.youdao_utils as youdao_utils
import asyncio
from pathlib import Path
import base64
import alibabacloud_oss_v2 as oss
import alibabacloud_oss_v2.aio as oss_aio
from functions.config_loader import CONFIG

# 有道的应用ID和密钥，从配置文件中获取
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


async def save_image_oss(base64_str: str, name: str) -> None:
    """
    上传到oss
    :param base64_str: base64编码后的英文图片字符串
    :type base64_str: str
    :param name: 文件名，一般来说必须和原名一样
    :type name: str
    """
    try:
        image_bytes = base64.b64decode(base64_str)
        name = str(Path(CONFIG["translate"]["output_path"])) + "/" + name
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


async def translate_one_from_oss(key: str) -> None:
    """
    translate_one 翻译一张图片
    :param key: 图片在OSS中的key
    :type key: str
    """
    try:
        file_name = key.split("/")[-1]
        get_request = oss.GetObjectRequest(bucket=CONFIG["oss"]["bucket_name"], key=key)
        response = await OSS_CLIENT.get_object(get_request)
        if not response.body:
            raise Exception(f"Failed to download image from OSS: {key}")
        # FIXME: 这里的问题不知道怎么修复，但是代码本身是没问题的
        image_bytes = await response.body.read()  # type: ignore
        if isinstance(image_bytes, bytes):
            base64_str = base64.b64encode(image_bytes).decode()
        else:
            raise Exception(f"Failed to change b64 : {key}")
        data = {
            "q": base64_str,
            "from": "auto",
            "to": "auto",
            "render": "1",
            "type": "1",
        }
        httpx.post(URL)
        youdao_utils.addAuthParams(APP_ID, APP_SECRET, data)
        async with httpx.AsyncClient() as client:
            r = await client.post(
                url=URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            r.raise_for_status()
            response_obj = r.json()
            await save_image_oss(response_obj["render_image"], file_name)
    except Exception as e:
        print(e)
    finally:
        await OSS_CLIENT.close()


async def get_list_from_oss(mode: str) -> List[str]:
    """
    从阿里云容器中获取中英文图片list，

    :param mode: 模式，必须是'en'或'zh'
    :type mode: str
    :return: 返回的list（图片key）
    :rtype: List[str]
    """
    prefix = (
        CONFIG["crawler"]["save_path"]
        if mode == "en"
        else CONFIG["translate"]["output_path"]
    )
    try:
        object_keys = []
        continuation_token = None
        get_objects_request = oss.ListObjectsV2Request(
            bucket=CONFIG["oss"]["bucket_name"],
            # 这里其实写死也没事，毕竟阿里云oss用的就是'/'，如果你用Path的话，在win上面反而会拼错
            prefix=prefix + "/",
            max_keys=CONFIG["translate"]["max_key_length"],
            continuation_token=continuation_token,
        )
        # 获取对象列表
        result = await OSS_CLIENT.list_objects_v2(get_objects_request)
        if result.contents is not None:
            for obj in result.contents:
                object_keys.append(obj.key)
        else:
            raise Exception("No objects found in OSS bucket.")
    except Exception as e:
        print(f"OSS get object error: {e}")
    finally:
        await OSS_CLIENT.close()
        return object_keys


async def translate_all_from_oss() -> None:
    """
    翻译crawler的目录下面的所有图片
    """
    # 从空器中找到英文图片list
    en_list = await get_list_from_oss("en")
    # 中文list
    finished_images = await get_list_from_oss("zh")
    en_list = [p for p in en_list if p not in finished_images]
    for i in en_list:
        await translate_one_from_oss(i)


if __name__ == "__main__":
    asyncio.run(translate_all_from_oss())
