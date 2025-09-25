import pandas as pd
import requests
import os
import logging
import time
from typing import List, Dict

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('google_scholar.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class GoogleSpiderDownloader:
    """
    用于从Google Scholar爬虫导出的Excel文件中下载arXiv论文的类
    将URL中的 `https://arxiv.org/abs` 替换为 `https://arxiv.org/pdf` 后下载PDF文件
    """
    def __init__(self, excel_path: str = 'google_scholar_results.xlsx', output_dir: str = 'downloads'):
        """
        初始化下载器
        Args:
            excel_path: Excel文件路径，默认为'google_scholar_results.xlsx'
            output_dir: 下载文件保存目录，默认为'downloads'
        """
        self.excel_path = excel_path
        self.output_dir = output_dir
        self.base_url_abs = 'https://arxiv.org/abs'
        self.base_url_pdf = 'https://arxiv.org/pdf'
        
        # 创建输出目录
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            logger.info(f'创建输出目录: {self.output_dir}')

    def read_excel(self) -> List[Dict]:
        """
        读取Excel文件中的URL
        Returns:
            包含论文信息的字典列表
        """
        try:
            if not os.path.exists(self.excel_path):
                logger.error(f'Excel文件不存在: {self.excel_path}')
                return []

            df = pd.read_excel(self.excel_path)
            logger.info(f'成功读取Excel文件: {self.excel_path}，共 {len(df)} 条记录')

            # 检查是否包含'link'列
            if 'link' not in df.columns:
                logger.warning('Excel文件中未找到名为"link"的列')
                return []

            # 过滤出包含arxiv链接的记录
            arxiv_records = []
            for _, row in df.iterrows():
                link = str(row['link'])
                if self.base_url_abs in link:
                    # 替换URL
                    pdf_link = link.replace(self.base_url_abs, self.base_url_pdf) + '.pdf'
                    arxiv_records.append({
                        'title': str(row.get('title', '未命名')),
                        'abs_link': link,
                        'pdf_link': pdf_link
                    })

            logger.info(f'找到 {len(arxiv_records)} 条包含arXiv链接的记录')
            return arxiv_records

        except Exception as e:
            logger.error(f'读取Excel文件时发生错误: {str(e)}')
            return []

    def download_pdf(self, pdf_link: str, save_path: str) -> bool:
        """
        下载PDF文件
        Args:
            pdf_link: PDF文件的URL
            save_path: 保存路径
        Returns:
            下载成功返回True，否则返回False
        """
        try:
            # 添加请求头，模拟浏览器
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
            }

            logger.info(f'开始下载: {pdf_link}')
            response = requests.get(pdf_link, headers=headers, timeout=30, stream=True)

            if response.status_code == 200:
                # 确保目录存在
                os.makedirs(os.path.dirname(save_path), exist_ok=True)

                
                # 文件存在则跳过
                if os.path.exists(save_path):
                    print("文件已存在，跳过下载")
                    return


                # 写入文件
                with open(save_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                logger.info(f'下载成功: {save_path}')
                return True
            else:
                logger.error(f'下载失败，状态码: {response.status_code}, URL: {pdf_link}')
                return False

        except Exception as e:
            logger.error(f'下载文件时发生错误: {str(e)}, URL: {pdf_link}')
            return False

    def batch_download(self, delay: int = 3) -> int:
        """
        批量下载PDF文件
        Args:
            delay: 下载间隔时间(秒)，默认为3秒
        Returns:
            成功下载的文件数量
        """
        records = self.read_excel()
        if not records:
            logger.warning('没有找到可下载的记录')
            return 0

        success_count = 0
        for i, record in enumerate(records, 1):
            logger.info(f'正在处理第 {i}/{len(records)} 条记录')

            # 生成保存文件名
            title = record['title'].replace(':', '').replace('/', '_').replace('\\', '_')
            # 取标题前30个字符，避免文件名过长
            short_title = title[:30] if len(title) > 30 else title
            save_path = os.path.join(self.output_dir, f'{short_title}.pdf')

            # 下载文件
            if self.download_pdf(record['pdf_link'], save_path):
                success_count += 1

            # 添加延迟，避免请求过快
            if i < len(records):
                logger.info(f'等待 {delay} 秒后继续下载')
                time.sleep(delay)

        logger.info(f'批量下载完成，共成功下载 {success_count}/{len(records)} 个文件')
        time.sleep(5)
        return success_count

def main():
    """
    主函数，执行下载任务
    """
    downloader = GoogleSpiderDownloader()
    downloader.batch_download()

if __name__ == '__main__':
    main()