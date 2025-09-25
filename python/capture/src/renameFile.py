import os
import shutil

def rename_files_in_directory(directory):
    # 获取文件夹中的所有文件
    files = os.listdir(directory)
    files.sort()  # 确保文件按顺序排列

    # 重命名文件
    for i, filename in enumerate(files):
        if os.path.isfile(os.path.join(directory, filename)):
            # 获取文件名和扩展名
            name, ext = os.path.splitext(filename)
            # 创建同名文件夹
            new_folder = os.path.join(directory, f"{i + 1}")
            if not os.path.exists(new_folder):
                os.makedirs(new_folder)
            # 构造新的文件名
            new_filename = f"model{ext}"
            # 构造新的文件路径
            new_file_path = os.path.join(new_folder, new_filename)
            # 移动文件到新文件夹
            shutil.move(os.path.join(directory, filename), new_file_path)

# 示例调用
rename_files_in_directory(r'C:\\Users\\drenc\\Desktop\\test\\material\\20250513\\')