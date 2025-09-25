import os
import xml.etree.ElementTree as ET

def parse_urdf_file(file_path):
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()

        for joint in root.findall('joint'):
            name = joint.get('name')
            axis = joint.find('axis')
            if axis is not None:
                xyz = axis.get('xyz')
                # 转为float类型
                xyz_list = xyz.split()
                xyz = [float(x) for x in xyz_list]
                # 空格拼接后覆盖回urdf文件
                joint.find('axis').set('xyz', ' '.join(str(x) for x in xyz))
                print(f"Joint Name: {name}, Axis XYZ: {xyz}")

        # 保存文件
        tree.write(file_path)
    except ET.ParseError as e:
        print(f"Error parsing {file_path}: {e}")

def main(directory):
    if not os.path.isdir(directory):
        print(f"The directory {directory} does not exist.")
        return

    # 递归遍历
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.urdf'):
                file_path = os.path.join(root, file)
                parse_urdf_file(file_path)

if __name__ == "__main__":
    # 指定需要搜索的目录
    urdf_directory = "C:\\Users\\drenc\\Desktop\\test\\urdf\\fine\\bak"  
    main(urdf_directory)