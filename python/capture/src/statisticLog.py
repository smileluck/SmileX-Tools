import re
from collections import defaultdict


def group_logs_by_keyword(log_file_path, keyword_pattern):
    # 用于存储分组结果的字典，键为关键字，值为对应的日志行列表
    log_groups = defaultdict(list)

    # 读取日志文件
    with open(log_file_path, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            # 使用正则表达式查找关键字
            match = re.search(keyword_pattern, line)
            if match:
                # 提取关键字
                keyword = match.group(0)
                # 将当前行添加到对应关键字的列表中
                log_groups[keyword].append(line)

    strs = []

    # 输出分组结果
    for keyword, lines in log_groups.items():
        # 将每行中的用空格分割，然后读取第一个字符串作为时间，比较所有行中的时间，时间格式是 hh:mm:ss.sss，如果大于45分钟，则输出
        times = [line.split()[0] for line in lines if not line.startswith("Caused")]
        #  过滤 times = caused 的
        # 将 %H:%M:%S.%f 转换为秒数
        times = [
            int(time.split(":")[0]) * 3600
            + int(time.split(":")[1]) * 60
            + float(time.split(":")[2])
            for time in times
        ]

        # 判断line中是否同时存在 train3d_only 和success
        hasSuccess = False
        for line in lines:
            if "train3d_only" in line and "Success" in line:
                hasSuccess = True

        # if hasSuccess:
        #     strs.append(f"{keyword} has been running for {(max(times) - min(times)) / 60:.2f} minutes. {hasSuccess}")

        if max(times) - min(times) > 45 * 60 :  # 45 分钟
            # 打印时长，以分钟为单位
            # print(f"{keyword} has been running for {(max(times) - min(times)) / 60:.2f} minutes.")
            strs.append(
                f"{keyword} has been running for {(max(times) - min(times)) / 60:.2f} minutes. {hasSuccess}"
            )
            # print(f"{keyword}: {lines}")
            # print(f"{keyword} has been running for more than 45 minutes.")
            # print(f"{keyword}: {lines}")
            # 将同一关键字的所有日志行合并成一行，用制表符分隔
            # combined_line = "\t".join(lines)
            # print(f"{keyword}: {combined_line}")

    # 保存结果到  txt 文件
    with open("result.txt", "w", encoding="utf-8") as file:
        for str in strs:
            file.write(str + "\n")

    return log_groups


# 使用示例
if __name__ == "__main__":
    log_file = "111.txt"  # 替换为实际的日志文件路径
    # 假设日志中的关键字是IP地址，格式类似为 task_id:
    keyword_pattern = r'"task_id": (\d+),'
    groups = group_logs_by_keyword(log_file, keyword_pattern)
