import crawl_bs4 as crawl
import translate as translate
from datetime import datetime
import asyncio

async def workflow():
    await crawl.get_image_list(save_oss=True)
    await translate.translate_all_from_oss()
    print('工作流已完成，',datetime.now())

if __name__ == '__main__':
    asyncio.run(workflow())