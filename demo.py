#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import alibabacloud_oss_v2 as oss
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Tuple, Optional
import signal

class DownloadTask:
    """下载任务类"""
    def __init__(self, object_key: str, local_path: str, size: int):
        self.object_key = object_key
        self.local_path = local_path
        self.size = size

class DownloadResult:
    """下载结果类"""
    def __init__(self, object_key: str, success: bool = False, error: Optional[str] = None, size: int = 0):
        self.object_key = object_key
        self.success = success
        self.error = error
        self.size = size

class BatchDownloader:
    """批量下载器"""

    def __init__(self, client: oss.Client, bucket: str, max_workers: int = 5):
        self.client = client
        self.bucket = bucket
        self.max_workers = max_workers
        self.stop_event = threading.Event()

    def list_objects(self, prefix: str = "", max_keys: int = 1000) -> List[DownloadTask]:
        """列举存储空间中指定前缀的所有对象"""
        tasks = []
        continuation_token = None

        print(f"正在扫描存储空间中的文件...")

        while not self.stop_event.is_set():
            try:
                # 创建列举对象请求
                request = oss.ListObjectsV2Request(
                    bucket=self.bucket,
                    prefix=prefix,
                    max_keys=max_keys,
                    continuation_token=continuation_token
                )

                # 执行列举操作
                result = self.client.list_objects_v2(request)

                # 处理列举结果
                for obj in result.contents:
                    # 跳过文件夹对象（以/结尾且大小为0）
                    if obj.key.endswith('/') and obj.size == 0:
                        continue

                    # 计算本地文件路径
                    relative_path = obj.key[len(prefix):] if prefix else obj.key

                    tasks.append(DownloadTask(
                        object_key=obj.key,
                        local_path=relative_path,
                        size=obj.size
                    ))

                # 检查是否还有更多对象
                if not result.next_continuation_token:
                    break
                continuation_token = result.next_continuation_token

            except Exception as e:
                raise Exception(f"列举对象失败: {str(e)}")

        return tasks

    def download_file(self, task: DownloadTask, local_dir: str) -> DownloadResult:
        """下载单个文件"""
        result = DownloadResult(task.object_key, size=task.size)

        try:
            # 计算完整的本地文件路径
            full_local_path = os.path.join(local_dir, task.local_path)

            # 创建本地文件目录
            os.makedirs(os.path.dirname(full_local_path), exist_ok=True)

            # 检查文件是否已存在且大小一致（断点续传）
            if os.path.exists(full_local_path):
                local_size = os.path.getsize(full_local_path)
                if local_size == task.size:
                    result.success = True
                    return result

            # 创建下载请求
            get_request = oss.GetObjectRequest(
                bucket=self.bucket,
                key=task.object_key
            )

            # 执行下载
            response = self.client.get_object(get_request)

            # 保存文件
            with open(full_local_path, 'wb') as f:
                with response.body as body_stream:
                    # 分块读取并写入
                    for chunk in body_stream.iter_bytes(block_size=1024 * 1024):  # 1MB块
                        if self.stop_event.is_set():
                            raise Exception("下载被中断")
                        f.write(chunk)

            result.success = True

        except Exception as e:
            result.error = str(e)
            # 如果下载失败，删除不完整的文件
            try:
                if os.path.exists(full_local_path):
                    os.remove(full_local_path)
            except:
                pass

        return result

    def batch_download(self, tasks: List[DownloadTask], local_dir: str) -> List[DownloadResult]:
        """执行批量下载"""
        results = []
        completed = 0
        total = len(tasks)

        print(f"开始下载 {total} 个文件，使用 {self.max_workers} 个并发...")

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有下载任务
            future_to_task = {
                executor.submit(self.download_file, task, local_dir): task
                for task in tasks
            }

            # 处理完成的任务
            for future in as_completed(future_to_task):
                if self.stop_event.is_set():
                    break

                task = future_to_task[future]
                try:
                    result = future.result()
                    results.append(result)
                    completed += 1

                    # 显示进度
                    if result.success:
                        print(f"✓ [{completed}/{total}] {result.object_key} ({self.format_bytes(result.size)})")
                    else:
                        print(f"✗ [{completed}/{total}] {result.object_key} - 错误: {result.error}")

                except Exception as e:
                    result = DownloadResult(task.object_key, error=str(e), size=task.size)
                    results.append(result)
                    completed += 1
                    print(f"✗ [{completed}/{total}] {task.object_key} - 异常: {str(e)}")

        return results

    def stop(self):
        """停止下载"""
        self.stop_event.set()
        print("\n正在停止下载...")

    @staticmethod
    def format_bytes(bytes_size: int) -> str:
        """格式化字节数为可读格式"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.1f} PB"

def signal_handler(signum, frame):
    """信号处理器"""
    print(f"\n接收到信号 {signum}，正在停止...")
    if hasattr(signal_handler, 'downloader'):
        signal_handler.downloader.stop()
    sys.exit(0)

def main():
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description="OSS 批量下载工具")

    # 添加命令行参数
    parser.add_argument('--region', help='存储空间所在的区域', required=True)
    parser.add_argument('--bucket', help='存储空间的名称', required=True)
    parser.add_argument('--endpoint', help='自定义访问域名（可选）')
    parser.add_argument('--prefix', help='要下载的文件夹前缀，空字符串表示下载整个存储空间', default="")
    parser.add_argument('--local-dir', help='本地下载目录', default="./downloads")
    parser.add_argument('--workers', help='并发下载数量', type=int, default=5)
    parser.add_argument('--max-keys', help='每次列举的最大对象数', type=int, default=1000)

    # 解析命令行参数
    args = parser.parse_args()

    try:
        # 从环境变量中加载凭证信息，用于身份验证
        credentials_provider = oss.credentials.EnvironmentVariableCredentialsProvider()

        # 加载SDK的默认配置
        cfg = oss.config.load_default()
        cfg.credentials_provider = credentials_provider
        cfg.region = args.region

        # 如果提供了endpoint参数，则设置自定义endpoint
        if args.endpoint:
            cfg.endpoint = args.endpoint

        # 创建OSS客户端
        client = oss.Client(cfg)

        # 创建本地下载目录
        local_dir = getattr(args, 'local_dir')
        os.makedirs(local_dir, exist_ok=True)

        # 创建批量下载器
        downloader = BatchDownloader(client, args.bucket, args.workers)

        # 设置信号处理器以支持优雅停止
        signal_handler.downloader = downloader
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        print(f"开始批量下载")
        print(f"存储空间: {args.bucket}")
        print(f"前缀: '{args.prefix}' {'(整个存储空间)' if not args.prefix else ''}")
        print(f"本地目录: {local_dir}")
        print(f"并发数: {args.workers}")
        print("-" * 50)

        # 列举所有需要下载的对象
        tasks = downloader.list_objects(args.prefix, getattr(args, 'max_keys'))

        if not tasks:
            print("没有找到需要下载的文件")
            return

        print(f"找到 {len(tasks)} 个文件需要下载")
        print("-" * 50)

        # 执行批量下载
        start_time = time.time()
        results = downloader.batch_download(tasks, local_dir)
        end_time = time.time()

        # 统计下载结果
        success_count = sum(1 for r in results if r.success)
        fail_count = len(results) - success_count
        total_size = sum(r.size for r in results if r.success)
        duration = end_time - start_time

        print("-" * 50)
        print(f"下载完成!")
        print(f"成功: {success_count}")
        print(f"失败: {fail_count}")
        print(f"总大小: {BatchDownloader.format_bytes(total_size)}")
        print(f"耗时: {duration:.2f} 秒")

        if fail_count > 0:
            print(f"\n失败的文件:")
            for result in results:
                if not result.success:
                    print(f"  - {result.object_key}: {result.error}")

    except KeyboardInterrupt:
        print("\n下载被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"错误: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()