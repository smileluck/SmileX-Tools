from DrissionPage import ChromiumPage
from utils.mysql import UsingMysql
import time
import datetime
import requests
from bs4 import BeautifulSoup
import re
import json


def fetchBody(results):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with UsingMysql(log_time=True) as um:
        for result in results:
            name = result["name"]
            license = result["license"]
            mp4 = result["contentUrl"]
            thumbnail = result["thumbnailUrl"]

            um.cursor.execute("select * from tb_video where origin_video_url = %s", mp4)
            video = um.cursor.fetchone()
            if video is not None:
                print("MP4 = %s is exist", mp4)
            else:
                data = (
                    "videvo",
                    name,
                    license,
                    mp4,
                    thumbnail,
                    str(result),
                    str(0),
                    str(0),
                    now,
                )
                sql = "INSERT INTO `tb_video` (`source_type`, `title`, `license`, `origin_video_url`, `origin_cover_url`, `req_body`, `ai_generate_flag`, `bucket_flag`, `create_time`) VALUES (%s, %s, %s, %s, %s, %s,%s, %s,%s );"
                um.cursor.execute(sql, data)

    um._conn.commit


if __name__ == "__main__":
    url = "https://www.videvo.net/stock-video-footage/?page=%d"

    jre = re.compile(r"\{.*\}")

    for i in range(100):
        page = i + 1
        response = requests.get(url % page)
        htmlText = response.text
        soup = BeautifulSoup(htmlText, "html.parser")

        # Get the script tags
        scripts = soup.find_all("script", attrs={"type": "application/ld+json"})

        # reg match variables
        variables = []
        for script in scripts:
            dict = json.loads(script.text)
            if dict and dict["@type"] == "ItemList":
                fetchBody(dict["itemListElement"])

        # print result
        for name, value in variables:
            print(f"{name}:{value}")

    print("videvo爬取完毕")
