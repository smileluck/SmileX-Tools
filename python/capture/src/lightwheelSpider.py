# 这是爬取 lightWheel.ai 的脚本
# 通过http的方式
import requests
import json
import os
from tqdm import tqdm


# 分页获取,POST请求
def post_lightwheel(url, body):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    response = requests.post(url, headers=headers, data=json.dumps(body))
    return response.json()


# 控制分页变量，并循环调用post_lightweel
def get_lightwheel_spider(url):
    pageNum = 1
    pageSize = 1000
    body = {
        "page": pageNum,
        "pageSize": pageSize,
        "query": {"name": "", "assetTypes": ["Manipulation", "Locomotion"]},
    }
    # while True:
    body["page"] = pageNum
    result = post_lightwheel(url, body)
    # 读取 data
    data = result["data"]
    # 读取data.records
    records = data["records"]
    print(len(records))
    # 遍历records 写入到 本地txt文件
    # for record in records:
    # json格式化后保存到本地数据库
    with open("lightwheel.txt", "a", encoding="utf-8") as f:
        f.write(json.dumps(records, ensure_ascii=False) + "\n")

        # if result["data"]["total"] == 0:
        # break


# 读取lightwheel.txt文件，转换成json对象，遍历json对象
def read_lightwheel_txt():
    with open("lightwheel.txt", "r", encoding="utf-8") as f:
        for line in f:
            json_obj = json.loads(line)
            for record in json_obj:
                file_url = record["fileUrl"]
                download_file(file_url)

                name = record["name"]
                images = record["images"]

                num = 0
                for image in images:
                    download_file(image["fileUrl"], f"{name}_{num}")
                    num = num + 1


# 下载fileUrl对象
def download_file(file_url, file_name=""):
    # 配置超时时间为1小时
    requests.adapters.DEFAULT_RETRIES = 5
    session = requests.Session()
    session.keep_alive = False
    session.mount("http://", requests.adapters.HTTPAdapter(max_retries=5))
    session.mount("https://", requests.adapters.HTTPAdapter(max_retries=5))
    session.timeout = 3600
    print(file_url)

    # 解析文件名
    if file_name == "":
        file_name = file_url.split("/")[-1]
    else:
        file_name = file_name + "." + file_url.split(".")[-1]

    # 创建lightwheel文件夹
    if not os.path.exists("lightwheel"):
        os.mkdir("lightwheel")

    # 拼接本地路径
    file_path = os.path.join("lightwheel", file_name)

    # 下载失败则删除文件
    try:
        # 文件存在则跳过
        if os.path.exists(file_path):
            print("文件已存在，跳过下载")
            return

        response = requests.get(file_url)

        # 下载显示进度
        print(f"正在下载文件: {file_name}")
        response.raise_for_status()
        total_size = int(response.headers.get("content-length", 0))
        block_size = 1024

        # 创建进度条
        progress_bar = tqdm(
            total=total_size,
            unit="B",
            unit_scale=True,
            desc=f"下载 {file_path}",
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
        )

        with open(file_path, "wb") as f:
            with progress_bar as pbar:
                for data in response.iter_content(block_size):
                    if data:
                        pbar.update(len(data))
                        f.write(data)

        progress_bar.close()

        print("下载完成")

        # 解压 zip 文件
        if file_name.endswith(".zip"):
            import zipfile

            with zipfile.ZipFile(file_path, "r") as zip_ref:
                zip_ref.extractall(f"lightwheel")
            os.remove(file_path)

    except Exception as e:
        print("下载失败，删除文件")
        if os.path.exists(file_path):
            os.remove(file_path)
        # raise e


# 运行
if __name__ == "__main__":
    url = "https://lightwheel.ai/lwApi/open/asset/asset_page"
    result = get_lightwheel_spider(url)
    read_lightwheel_txt()
    # print(result)
