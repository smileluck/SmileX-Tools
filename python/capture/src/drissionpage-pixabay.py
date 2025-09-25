from DrissionPage import ChromiumPage
from utils.mysql import UsingMysql
import time
import datetime


def fetchBody(results):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with UsingMysql(log_time=True) as um:
        for result in results:
            # result = results[idx]
            description = result["description"]
            duration = result["duration"]
            height = result["height"]
            width = result["width"]
            name = result["name"]
            alt = result["alt"] 
            isAiGenerated = result["isAiGenerated"]
            mp4 = result["sources"]["mp4"]
            thumbnail = result["sources"]["thumbnail"]
            source_id = result["id"]

            um.cursor.execute("select * from tb_video where origin_id = %s", source_id)
            video = um.cursor.fetchone()
            if video is not None:
                print("source_id = %s is exist", source_id)
            else:
                data = (
                    "pixabay",
                    name,
                    alt,
                    description,
                    mp4,
                    thumbnail,
                    str(width),
                    str(height),
                    str(duration),
                    str(result),
                    str(1 if isAiGenerated else 0),
                    str(0),
                    now,
                    source_id,
                )
                sql = "INSERT INTO `tb_video` (`source_type`, `title`, `tags`, `description`, `origin_video_url`, `origin_cover_url`, `width`, `height`, `duration`, `req_body`, `ai_generate_flag`, `bucket_flag`, `create_time`, `origin_id`) VALUES (%s, %s, %s, %s, %s,%s, %s, %s, %s, %s, %s, %s, %s,%s);"
                um.cursor.execute(sql, data)

    um._conn.commit


if __name__ == "__main__":

    page = ChromiumPage()

    url = "https://pixabay.com/zh/videos/search/?order=ec&pagi=%d"

    startPage = 551
    openPage = startPage + 1

    page.get(url % openPage)

    page.listen.start("https://pixabay.com/zh/videos/search/?order=ec")

    page.wait.eles_loaded(".:page")  # 等待 id 为 div1 的元素加载
    # page.wait.ele_displayed('.:pages')
    # page.ele(".:pages").child().link = "https://pixabay.com/zh/videos/search/?order=ec&pagi=1"


    # page.ele(".:page").child().click()

    res = page.listen.wait()  # 等待并获取一个数据包
    page.wait(3)

    print(res)

    pageInfo = res.response.body["page"]

    pages = pageInfo["pages"]

    print("pages=%s,total=%d", pages, pageInfo["total"])
    fetchBody(pageInfo["results"])
    for _ in range(pages - startPage):
        page.wait(3)
        ul_ele = page.ele("tag:span@@text():下一页").parent()
        ul_ele.click()  # 点击下一页

        res = page.listen.wait()  # 等待并获取一个数据包
        print(res)  # 474
        pageInfo = res.response.body["page"]
        # print(pageInfo)  # 打印数据包url
        fetchBody(pageInfo["results"])
        
    print("pixabay爬取完毕")
