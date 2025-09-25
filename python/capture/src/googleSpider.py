from DrissionPage import ChromiumPage
import time
import logging
import pandas as pd
import os
from typing import List, Dict

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("google_scholar.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class GoogleScholarSpider:
    """
    Google Scholar 爬虫类，使用 DrissionPage 爬取指定引用页面的所有条目的标题和跳转链接
    """
    def __init__(self):
        """初始化爬虫"""
        self.page = None
        self.results = []
        self.base_url = "https://scholar.google.com/scholar?oi=bibs&hl=en&cites=13105057068849863314"

    def export_to_excel(self, file_path: str = "google_scholar_results.xlsx") -> bool:
        """
        将爬取结果导出到 Excel 文件
        :param file_path: 导出的 Excel 文件路径
        :return: 导出成功返回 True，否则返回 False
        """
        try:
            if not self.results:
                logger.warning("没有可导出的结果")
                return False

            # 创建 DataFrame
            df = pd.DataFrame(self.results)

            # 确保目录存在
            os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)

            # 导出到 Excel
            df.to_excel(file_path, index=False, engine='openpyxl')
            logger.info(f"结果已成功导出到 {file_path}")
            return True
        except Exception as e:
            logger.error(f"导出 Excel 时发生错误: {str(e)}")
            return False

    def init_browser(self):
        """初始化浏览器"""
        try:
            self.page = ChromiumPage()
            # 设置用户代理，模拟真实浏览器
            self.page.set.user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
            logger.info("浏览器初始化成功")
        except Exception as e:
            logger.error(f"浏览器初始化失败: {str(e)}")
            raise

    def close_browser(self):
        """关闭浏览器"""
        if self.page:
            self.page.quit()
            logger.info("浏览器已关闭")

    def crawl(self) -> List[Dict[str, str]]:
        """
        爬取 Google Scholar 页面上的所有条目
        :return: 包含标题和链接的字典列表
        """
        if not self.page:
            logger.error("浏览器未初始化，请先调用 init_browser 方法")
            return []

        try:
            # 打开页面
            logger.info(f"正在打开页面: {self.base_url}")
            self.page.get(self.base_url)
            time.sleep(3)  # 等待页面加载

            # 检查是否有验证码或 403 错误
            if self._check_for_captcha():
                logger.warning("检测到验证码或访问限制，尝试刷新页面...")
                self.page.refresh()
                time.sleep(5)
                if self._check_for_captcha():
                    logger.error("仍然存在验证码或访问限制，无法继续爬取")
                    return []

            # 开始爬取
            self._extract_items()
            self._handle_pagination()

            logger.info(f"爬取完成，共获取 {len(self.results)} 个条目")
            return self.results

        except Exception as e:
            logger.error(f"爬取过程中发生错误: {str(e)}")
            return []

    def _check_for_captcha(self) -> bool:
        """
        检查页面是否有验证码或访问限制
        :return: 如果有验证码或访问限制则返回 True，否则返回 False
        """
        try:
            # 检查 403 错误
            if "403. That's an error" in self.page.html:
                return True
            # 检查验证码元素
            if self.page.ele("tag:div@@id:recaptcha", timeout=1):
                return True
            return False
        except Exception:
            return False

    def _extract_items(self):
        """提取当前页面上的所有条目"""
        try:
            # 定位到结果容器
            results_container = self.page.ele("tag:div@@id:gs_res_ccl")
            if not results_container:
                logger.warning("未找到结果容器")
                return

            # 定位到所有条目
            items = results_container.eles("tag:h3@class=gs_rt")
            if not items:
                logger.warning("当前页面没有找到条目")
                return

            for item in items:
                try:
                    # 提取标题和链接
                    title_element = item.ele("a")
                    if not title_element:
                        continue

                    title = title_element.text
                    link = title_element.attr("href")

                    if title and link:
                        self.results.append({
                            "title": title,
                            "link": link
                        })
                        logger.info(f"已提取条目: {title}")
                except Exception as e:
                    logger.warning(f"提取条目时出错: {str(e)}")
                    continue

            logger.info(f"当前页面共提取 {len(items)} 个条目")
        except Exception as e:
            logger.error(f"提取条目时发生错误: {str(e)}")

    def _handle_pagination(self):
        """处理分页，爬取所有页面"""
        while True:
            try:
                # 查找下一页按钮
                next_button = self.page.ele("#gs_n")
                if not next_button:
                    logger.info("没有找到下一页按钮，已完成爬取")
                    break

                next_link = next_button.ele("text=Next")
                if not next_link:
                    logger.info("已到达最后一页")
                    break

                visibility = next_link.style("visibility")
                if visibility=='hidden':
                    logger.info("已到达最后一页2")
                    break

                # 点击下一页
                logger.info("正在点击下一页")
                next_link.parent().click(by_js=True)
                time.sleep(5)  # 等待页面加载

                # 检查是否有验证码或 403 错误
                if self._check_for_captcha():
                    logger.warning("检测到验证码或访问限制，无法继续爬取")
                    break

                # 提取条目
                self._extract_items()

            except Exception as e:
                logger.error(f"处理分页时发生错误: {str(e)}")
                break

def main():
    """主函数，执行爬虫"""
    spider = GoogleScholarSpider()

    try:
        spider.init_browser()
        results = spider.crawl()

        # 打印结果
        print("\n爬取结果:")
        for i, result in enumerate(results, 1):
            print(f"{i}. 标题: {result['title']}")
            print(f"   链接: {result['link']}")
            print()

        # 保存结果到文件
        with open("google_scholar_results.txt", "w", encoding="utf-8") as f:
            for result in results:
                f.write(f"标题: {result['title']}\n")
                f.write(f"链接: {result['link']}\n\n")
        logger.info("结果已保存到 google_scholar_results.txt")

        spider.export_to_excel();

    finally:
        spider.close_browser()

if __name__ == "__main__":
    main()