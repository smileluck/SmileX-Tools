import pandas as pd
from utils.mysql import UsingMysql


if __name__ == "__main__":

    with UsingMysql(log_time=True) as um:
        um.cursor.execute("select * from tb_video where source_type='pixabay'")
        result = um.cursor.fetchall()
        for item in result:
            origin_video_url = item["origin_video_url"]
            splitResult = origin_video_url.split("_tiny")
            dict = {
                "tiny": splitResult[0] + "_tiny" + splitResult[1],
                "small": splitResult[0] + "_small" + splitResult[1],
                "medium": splitResult[0] + "_medium" + splitResult[1],
                "large": splitResult[0] + "_large" + splitResult[1],
                "source": splitResult[0] + splitResult[1],
            }
            print(item['id'], str(dict))
            um.cursor.execute(
                "update tb_video set origin_video_opt = %s where id = %s",
                (str(dict), item["id"]),
            )

        um._conn.commit

        print(result)


# 创建一个示例数据框
# data = {
#     '姓名': ['张三', '李四', '王五'],
#     '年龄': [28, 34, 45],
#     '城市': ['北京', '上海', '广州']
# }
# df = pd.DataFrame(data)

# # 导出到 Excel 文件
# df.to_excel('输出.xlsx', index=False)

# # print("数据已成功导出到 '输出.xlsx'")
