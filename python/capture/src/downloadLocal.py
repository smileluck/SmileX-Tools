import os
import requests
import pandas as pd
import json
from tqdm import tqdm
from utils.mysql import UsingMysql, get_connection

# 每批读取的行数
batch_size = 100

# 初始化计数器
counter = 1


def download_files_from_db(http_url):

    print("下载路径 %s", http_url)

    # 假设data是从数据库中获取的数据列表，每个元素包含一个'http_url'字段
    # http_url = item["http_url"]
    file_name = os.path.basename(http_url)
    file_path = os.path.join(os.getcwd(), file_name)

    print(f"正在下载文件: {file_name}")
    print(f"文件路径: {file_path}")

    try:
        # 使用系统代理
        # proxies = {"http": "192.168.21.175:7897"}

        # response = requests.get(http_url, stream=True)
        # response.raise_for_status()  # 检查请求是否成功

        # total_size = int(response.headers.get('content-length', 0))
        # block_size = 8192  # 1 Kibibyte

        # with open(file_path, "wb") as f:
        #     for data in tqdm(response.iter_content(block_size), total=total_size // block_size, unit='KB', unit_scale=True, desc=file_name, ascii=True):
        #         f.write(data)

        response = requests.get(http_url, stream=True)
        response.raise_for_status()  # 检查请求是否成功

        total_size = int(response.headers.get("content-length", 0))
        block_size = 8192  # 8 Kibibyte

        with open(file_path, "wb") as f:
            with tqdm(
                total=total_size, unit="B", unit_scale=True, desc=file_name, ascii=True
            ) as pbar:
                for data in response.iter_content(block_size):
                    if data:
                        f.write(data)
                        pbar.update(len(data))

        # with requests.get(http_url, stream=True, timeout=99999) as r:
        #     with open(file_name, "wb") as f:
        #         for chunk in r.iter_content(chunk_size=8192):
        #             if chunk:
        #                 f.write(chunk)
        print(f"File downloaded: {file_path}")
    except requests.exceptions.RequestException as e:
        print(f"Failed to download file from {http_url}: {e}")


if __name__ == "__main__":

    connection = get_connection()
    with UsingMysql(log_time=True) as um:
        batch_df = pd.read_sql(
            "select * from tb_video where source_type='pixabay' LIMIT %s OFFSET %s",
            connection,
            params=(batch_size, (counter - 1) * batch_size),
        )
        if not batch_df.empty:
            # 导出数据到文件
            download_urls = []
            for index, row in batch_df.iterrows():
                opt = row["origin_video_opt"]
                try:
                    # 替换单引号为双引号
                    opt_dict = json.loads(opt.replace("'", '"'))
                    http_url = opt_dict.get("source")  # 假设字典中有 'http_url' 键
                    if http_url:
                        # http_url = http_url.replace("_source", "")
                        download_files_from_db(http_url)
                        
                        # download_urls.append(http_url)
                except json.JSONDecodeError:
                    print(f"Failed to decode JSON from {opt}")
