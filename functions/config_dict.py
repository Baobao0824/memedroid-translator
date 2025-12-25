from typing import TypedDict

class _Crawler(TypedDict):
    max_page_num: int
    save_path: str
class _Oss(TypedDict):
    access_key_id: str
    access_key_secret: str
    bucket_name: str
    region: str


class ConfigDict(TypedDict):
    crawler: _Crawler
    oss: _Oss
