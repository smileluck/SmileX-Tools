import requests
import pandas as pd
import logging
import os
from bs4 import BeautifulSoup
import time
from typing import List, Dict
import json 
import re

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('theory_spider.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TheorySpider:
    """
    用于从Google Scholar爬虫导出的Excel文件中获取论文作者信息的类
    读取第二列link字符串，筛选包含thecvf.com和arxiv.org的链接，访问并解析获取作者信息
    将作者信息写入Excel文件的第四列
    """
    def __init__(self, excel_path: str = 'google_scholar_results.xlsx'):
        """
        初始化爬虫
        Args:
            excel_path: Excel文件路径，默认为'google_scholar_results.xlsx'
        """
        self.excel_path = excel_path
        self.target_domains = ['thecvf.com', 'arxiv.org']
        # 检查必要的依赖库是否已安装
        self._check_dependencies()

    def _check_dependencies(self):
        """检查必要的依赖库是否已安装"""
        try:
            import pandas
        except ImportError:
            logger.error('请安装pandas库: pip install pandas')
            raise ImportError('pandas库未安装')
        try:
            import bs4
        except ImportError:
            logger.error('请安装BeautifulSoup库: pip install beautifulsoup4')
            raise ImportError('BeautifulSoup库未安装')

    def read_excel(self) -> pd.DataFrame:
        """
        读取Excel文件
        Returns:
            包含论文信息的DataFrame
        """
        try:
            if not os.path.exists(self.excel_path):
                logger.error(f'Excel文件不存在: {self.excel_path}')
                return pd.DataFrame()

            df = pd.read_excel(self.excel_path)
            logger.info(f'成功读取Excel文件: {self.excel_path}，共 {len(df)} 条记录')

            # 检查是否包含至少两列数据
            if len(df.columns) < 2:
                logger.warning('Excel文件中至少需要包含两列数据')
                return pd.DataFrame()

            # 获取第二列的列名
            second_column_name = df.columns[1]
            logger.info(f'第二列列名为: {second_column_name}')

            return df

        except Exception as e:
            logger.error(f'读取Excel文件时发生错误: {str(e)}')
            return pd.DataFrame()

    def filter_links(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        筛选包含目标域名的链接
        Args:
            df: 包含论文信息的DataFrame
        Returns:
            筛选后的DataFrame
        """
        # 获取第二列的列名
        second_column_name = df.columns[1]

        # 筛选包含目标域名的链接
        filtered_df = df[df[second_column_name].str.contains('|'.join(self.target_domains), na=False)]
        logger.info(f'筛选出 {len(filtered_df)} 条包含目标域名的记录')
        return filtered_df

    def get_author_info_ieee(self, url: str) -> str:
        """
        获取网页中的作者信息（从xplGlobal.document.metadata变量中提取）
        Args:
            url: 网页URL
        Returns:
            作者信息字符串，如果获取失败则返回空字符串
        """
        try:
            # 添加请求头，模拟浏览器
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
            }

            logger.info(f'开始访问: {url}')
            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # 查找包含xplGlobal.document.metadata的脚本块
                script_tags = soup.find_all('script')
                metadata_script = None
                for script in script_tags:
                    if script.string and 'xplGlobal.document.metadata' in script.string:
                        metadata_script = script.string
                        break

                if metadata_script:
                    pattern = r'xplGlobal\.document\.metadata=({.*?});'
                    match = re.search(pattern, metadata_script, re.DOTALL)  # re.DOTALL 让 . 匹配换行符

                    if match:
                        # 2. 提取并清理 JSON 字符串（去除可能的多余字符）
                        json_str = match.group(1).strip()

                        try:
                            # 解析JSON
                            metadata = json.loads(json_str)

                            # 提取authors字段
                            if 'authors' in metadata:
                                authors = [author['name'] for author in metadata['authors']]
                                author_str = '; '.join(authors)
                                logger.info(f'成功获取作者信息: {author_str}')
                                return author_str
                            else:
                                logger.warning(f'未在metadata中找到authors字段: {url}')
                                return ''
                        except json.JSONDecodeError as e:
                            logger.error(f'解析metadata JSON时发生错误: {str(e)}, URL: {url}')
                            return ''
                    
                else:
                    logger.warning(f'未找到xplGlobal.document.metadata脚本块: {url}')
                    return ''
            else:
                logger.error(f'访问失败，状态码: {response.status_code}, URL: {url}')
                return ''

        except Exception as e:
            logger.error(f'获取作者信息时发生错误: {str(e)}, URL: {url}')
            return ''

    def get_author_info(self, url: str) -> str:
        """
        获取网页中的作者信息
        Args:
            url: 网页URL
        Returns:
            作者信息字符串，如果获取失败则返回空字符串
        """
        try:
            # 添加请求头，模拟浏览器
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
            }

            logger.info(f'开始访问: {url}')
            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # 查找meta标签中name=citation_author的数据
                author_tags = soup.find_all('meta', attrs={'name': 'citation_author'})
                authors = [tag['content'] for tag in author_tags]

                if authors:
                    author_str = '; '.join(authors)
                    logger.info(f'成功获取作者信息: {author_str}')
                    return author_str
                else:
                    logger.warning(f'未找到作者信息: {url}')
                    return ''
            else:
                logger.error(f'访问失败，状态码: {response.status_code}, URL: {url}')
                return ''

        except Exception as e:
            logger.error(f'获取作者信息时发生错误: {str(e)}, URL: {url}')
            return ''

    def process_links(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        处理筛选后的链接，获取作者信息并添加到DataFrame中
        Args:
            df: 筛选后的DataFrame
        Returns:
            处理后的DataFrame
        """
        # 确保DataFrame至少有4列
        # while len(df.columns) < 4:
        #     df.insert(len(df.columns), f'col_{len(df.columns)}', '')
        #     logger.info(f'添加空列至DataFrame，当前列数: {len(df.columns)}')

        # 遍历筛选后的记录
        for index, row in df.iterrows():
            logger.info(f'正在处理第 {index+1}/{len(df)} 条记录')
            # 获取第二列的链接
            second_column_name = df.columns[1]
            url = row[second_column_name]

            # 保存作者信息到第五列（索引为4）
            df.loc[index, 'has_download'] = f'=IF(ISNUMBER(SEARCH("arxiv", B{index+2})), "是", "否")'

            if not url: continue

            # 如果是 .pdf后缀跳过
            if url.endswith('.pdf'): continue

            authors = ''

            # 判断 url 是否包含 arxiv.org 或 thecvf.com
            if "arxiv.org" in url or "thecvf.com" in url:
                # 获取作者信息
                authors = self.get_author_info(url)
            elif "ieee.org" in url:
                authors = self.get_author_info_ieee(url)
            else:
                logger.warning(f'未找到作者信息: {url}')
                continue



            # 保存作者信息到第四列（索引为3）
            # df['D'] = authors
            df.loc[index, 'authors'] = authors



            # 添加延迟，避免请求过快
            time.sleep(3)

        return df

    def save_results(self, df: pd.DataFrame) -> bool:
        """
        保存结果到Excel文件
        Args:
            df: 处理后的DataFrame
        Returns:
            保存成功返回True，否则返回False
        """
        try:
            # 直接覆盖原文件
            df.to_excel(self.excel_path, index=False)
            logger.info(f'结果已保存到原文件: {self.excel_path}')
            return True

        except Exception as e:
            logger.error(f'保存结果时发生错误: {str(e)}')
            return False

    def run(self) -> bool:
        """
        运行爬虫
        Returns:
            运行成功返回True，否则返回False
        """
        try:
            # 读取Excel文件
            df = self.read_excel()
            if df.empty:
                logger.warning('没有找到有效的Excel数据')
                return False

            # 筛选链接
            # filtered_df = self.filter_links(df)
            # if filtered_df.empty:
            #     logger.warning('没有找到包含目标域名的链接')
            #     return False

            # 处理链接
            processed_df = self.process_links(df)

            # 保存结果
            return self.save_results(processed_df)

        except Exception as e:
            logger.error(f'运行爬虫时发生错误: {str(e)}')
            return False

def main():
    """
    主函数，执行爬虫任务
    """
    spider = TheorySpider()
    spider.run()

if __name__ == '__main__':
    main()