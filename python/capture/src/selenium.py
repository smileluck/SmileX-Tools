import cloudscraper
import urllib3
import requests
import httpx

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time


# url = "https://pixabay.com/zh/videos/search/?order=ec&pagi=1"
# urllib3.disable_warnings()

# scraper = cloudscraper.create_scraper(
#     delay=20, browser={"browser": "chrome", "platform": "windows", "mobile": False}
# )

# resp = scraper.get(url)

# print(resp.status_code)
# print(resp.text)

global brower


def openBrower():
    global brower
    brower = webdriver.Chrome()


def openPixaby():
    global brower
    if not brower:
        print("未启动浏览器")
        pass
    else:
        brower.get("https://pixabay.com/zh/videos/search/?order=ec&pagi=1")


headers = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
    # 'accept-encoding': 'gzip, deflate, br',
    "accept-language": "zh-CN,zh;q=0.9",
    # "cookie": cookies,
    "referer": "https://pixabay.com/",
    "sec-ch-ua": '"Chromium";v="94", "Google Chrome";v="94", ";Not A Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "same-origin",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 Safari/537.36",
}


def capturePixaby():
    time.sleep(10)

    cookieObj = {}
    cookieStr = ""
    cookies = brower.get_cookies()
    # 打印Cookies
    for cookie in cookies:
        cookieObj[cookie["name"]] = cookie["value"]
        cookieStr += cookie["name"] + "=" + cookie["value"] + ";"

    print(cookieStr)
    headers["cookie"] = "csrftoken=ek1S1F2UFmxiDTJxNIVVP61bbGeq30Tj; lang=zh; anonymous_user_id=a57e71046a8c4b54a317942549742ccc; dwf_homepage_music_theme_links=True; dwf_use_ssr_following_page=False; __cf_bm=aG2Vdwn8Top6loG7EJQOWjJu6V.nJda_D0oIObCvP_c-1717060110-1.0.1.1-KTaxyDH3aCo6WTRteEA6zaQbkK0c9FIRDrp2rXmLpJF_c.Nu0fWqqP2eyXhqewE7AtEdurQb7RKcq5NYR1xTuA; is_human=1; _sp_ses.aded=*; OptanonConsent=isGpcEnabled=0&datestamp=Thu+May+30+2024+17%3A10%3A15+GMT%2B0800+(%E4%B8%AD%E5%9B%BD%E6%A0%87%E5%87%86%E6%97%B6%E9%97%B4)&version=202401.2.0&browserGpcFlag=0&isIABGlobal=false&hosts=&consentId=94a075d7-ec09-4ea4-9b29-3c432cff9a68&interactionCount=1&landingPath=https%3A%2F%2Fpixabay.com%2Fzh%2Fvideos%2Fsearch%2F%3Forder%3Dec%26pagi%3D1&groups=C0001%3A1%2CC0002%3A1%2CC0003%3A1%2CC0004%3A1; _sp_id.aded=afe7652e-f836-4e15-8110-47adf351a493.1717060114.1.1717060216..4978b328-4b1a-4485-9096-a2964548119f..00c00af5-9b0f-47fd-9d72-d572e2fb6164.1717060114781.6"

    url = "https://pixabay.com/zh/videos/search/?order=ec&pagi=2"
    # urllib3.disable_warnings()

    scraper = cloudscraper.create_scraper(
        delay=5, browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )
    resp = scraper.get(url, headers=headers,)
    # print(resp)

    # client = httpx.Client(http2=True,verify=False)
    # resp = client.get(url,headers=headers,timeout=20)
    # resp = requests.get(url, headers=headers)
    print(resp)


if __name__ == "__main__":
    openBrower()

    openPixaby()
    capturePixaby()

    time.sleep(100000)
