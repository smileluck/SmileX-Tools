from DrissionPage import ChromiumPage
from utils.mysql import UsingMysql
import time
import datetime
import threading
from concurrent.futures import (
    ThreadPoolExecutor,
    wait,
    ALL_COMPLETED,
    FIRST_COMPLETED,
    as_completed,
)

# s = threading.Semaphore(10)
pool = ThreadPoolExecutor(max_workers=10)
list = []
tlist = []


def insert(li):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with UsingMysql(log_time=True) as um:
        a = li.ele("tag:a@@class:list-content-bg")

        img = a.eles("tag:img")[0]

        name = img.attr("alt")
        license = ""
        mp4 = li.attr("data-video")

        my_url = img.attr("srcset")
        if my_url.index("?") != -1:
            my_url = my_url.split("?")[0]

        thumbnail = my_url

        um.cursor.execute("select * from tb_video where origin_video_url = %s", mp4)
        video = um.cursor.fetchone()
        if video is not None:
            print("MP4 = %s is exist", mp4)
        else:
            data = (
                "shipin",
                name,
                license,
                mp4,
                thumbnail,
                str(a),
                str(0),
                str(0),
                now,
            )
            sql = "INSERT INTO `tb_video` (`source_type`, `title`, `license`, `origin_video_url`, `origin_cover_url`, `req_body`, `ai_generate_flag`, `bucket_flag`, `create_time`) VALUES (%s, %s, %s, %s, %s, %s,%s, %s,%s );"
            um.cursor.execute(sql, data)
            um._conn.commit()


def fetchBody(results):
    for li in results:
        tlist.append(pool.submit(insert, li))

    wait(tlist, return_when=ALL_COMPLETED)
    print("----complete-----")


def loopPage():

    for _ in range(100):
        page.wait(2)
        res = page.listen.wait()  # 等待并获取一个数据包

        # videos = page.eles('//*[@id="result-box"]/ul/li[3]/div[1]/a')
        resultBox = page.ele("#result-box")
        videos = resultBox.child().eles("tag:li")

        fetchBody(videos)

        resultBox.next().child().click()



if __name__ == "__main__":

    page = ChromiumPage()

    url = "https://shipin520.com/shipin-sp/"
    page.listen.start("https://shipin520.com/shipin-sp")
    page.get(url)

    num = 2

    type = page.ele("text:用途：").next().children()

    while num < len(type):
        type = page.ele("text:用途：").next().children()
        _ = type[num]
        _.click()
        page.wait(2)
        loopPage()

    pool.shutdown()
    print("shipin爬取完毕")
