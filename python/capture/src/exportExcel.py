import os
import pandas as pd
from utils.mysql import UsingMysql, get_connection

# 每批读取的行数
batch_size = 1000

# 初始化计数器
counter = 1

if __name__ == "__main__":

    excel_folder = "excel"
    if not os.path.exists(excel_folder):
        os.makedirs(excel_folder)

    connection = get_connection()
    with UsingMysql(log_time=True) as um:

        while True:
            batch_df = pd.read_sql(
                "select * from tb_video where source_type='pixabay' LIMIT %s OFFSET %s",
                connection,
                params=(batch_size, (counter - 1) * batch_size),
            )
            if batch_df.empty:
                break

            # 导出数据到文件
            file_name = f"excel/data_{counter}.xlsx"
            batch_df.to_excel(file_name, index=False)

            print(f"导出 {file_name} 成功")

            counter += 1
