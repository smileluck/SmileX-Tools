import trimesh
import pyrender
import numpy as np
import cv2
import os


def generate_glb_cover(glb_file_path, output_image_path):
    # 加载 GLB 文件
    mesh = trimesh.load_mesh(glb_file_path)

    # 如果是场景，合并所有网格
    if isinstance(mesh, trimesh.Scene):
        meshes = list(mesh.geometry.values())
        combined_mesh = trimesh.util.concatenate(meshes)
    else:
        combined_mesh = mesh

    # 计算最小边界框
    bounds = combined_mesh.bounds
    center = combined_mesh.centroid
    extent = bounds[1] - bounds[0]
    max_extent = np.max(extent)

    # 获取每个轴上的具体尺寸
    x_extent, y_extent, z_extent = extent

    print(f"X-axis extent: {x_extent}")
    print(f"Y-axis extent: {y_extent}")
    print(f"Z-axis extent: {z_extent}")

    # 创建一个 Pyrender 场景
    scene = pyrender.Scene()

    # 将网格添加到场景中
    pyr_mesh = pyrender.Mesh.from_trimesh(combined_mesh)
    scene.add(pyr_mesh)

    # 添加相机
    camera = pyrender.PerspectiveCamera(yfov=np.pi / 4.0)
    # 根据边界框调整相机位置
    camera_distance = (max_extent) / (2 * np.tan(camera.yfov / 3))
    camera_pose = np.eye(4)
    camera_pose[:3, 3] = center + np.array([0, 0, camera_distance])
    scene.add(camera, pose=camera_pose)

    # 添加光源
    light = pyrender.DirectionalLight(color=[1.0, 1.0, 1.0], intensity=1.5)

    # 计算光源位置，使其位于相机的45度角上方
    light_distance = camera_distance * np.sqrt(2)  # 45度角的距离
    light_offset = np.array([0, light_distance / 2, light_distance / 2])
    light_pose = np.eye(4)
    light_pose[:3, 3] = center + light_offset

    # 添加光源到场景中
    scene.add(light, pose=light_pose)

    # # 添加点光源以模拟环绕光
    # point_light = pyrender.PointLight(color=[1.0, 1.0, 1.0], intensity=2.0)
    # light_pose = np.eye(4)
    # light_pose[:3, 3] = center  # 将光源放置在模型中心
    # scene.add(point_light, pose=light_pose)

    # 计算合适的视口大小
    scale_factor = 1  # 调整比例以确保模型完全显示
    if x_extent < z_extent:
        base_height = 600  # 基准高度
        viewport_height = int(base_height * scale_factor)
        viewport_width = int(
            viewport_height * (x_extent / z_extent)
        )  # 根据宽高比调整宽度
    else:
        base_width = 800  # 基准宽度
        viewport_width = int(base_width / x_extent * scale_factor)
        viewport_height = int(viewport_width * (z_extent / x_extent))

    # 创建渲染器
    r = pyrender.OffscreenRenderer(
        viewport_width=viewport_width, viewport_height=viewport_height
    )

    print(f"Bounding viewport width: {viewport_width}")
    print(f"Bounding viewport height: {viewport_height}")

    # 渲染场景
    color, depth = r.render(scene)

    # 找到非零深度值的像素
    non_zero_depth = np.nonzero(depth)
    if non_zero_depth[0].size == 0 or non_zero_depth[1].size == 0:
        # 如果没有找到任何非零深度值，返回默认值或抛出异常
        return (0, 0), (viewport_width, viewport_height)

    # 计算最小包围框的左上角和右下角坐标
    min_x = np.min(non_zero_depth[1])
    min_y = np.min(non_zero_depth[0])
    max_x = np.max(non_zero_depth[1])
    max_y = np.max(non_zero_depth[0])

    left_top = (min_x, min_y)
    right_bottom = (max_x, max_y)

    # 计算最小包围框的宽度和高度
    width = max_x - min_x
    height = max_y - min_y

    print(f"Bounding Box Width: {width}")
    print(f"Bounding Box Height: {height}")
    
    # # 创建渲染器
    # r = pyrender.OffscreenRenderer(
    #     viewport_width=width, viewport_height=height
    # )

    # # 渲染场景
    # color, depth = r.render(scene)

    # 根据深度信息创建透明度通道
    alpha = np.where(depth > 0, 255, 0).astype(np.uint8)

    # 将颜色通道和透明度通道合并成 RGBA 图像
    rgba = np.dstack((color, alpha)).astype(np.uint8)

    # 裁剪图像以去除四周的空白区域
    cropped_rgba = rgba[min_y:max_y+1, min_x:max_x+1]
    
    # 保存渲染结果为带有透明背景的 PNG 图片
    cv2.imwrite(output_image_path, cv2.cvtColor(cropped_rgba, cv2.COLOR_RGBA2BGRA))

    # 释放渲染器资源
    r.delete()


# 新增函数：遍历文件夹并生成预览图
def generate_previews_from_folder(folder_path):
    for root, dirs, files in os.walk(folder_path):
        for dir_name in dirs:
            print(dir_name)
            subfolder_path = os.path.join(root, dir_name)
            glb_file_path = os.path.join(subfolder_path, "model.glb")
            if os.path.exists(glb_file_path):
                output_image_path = os.path.join(subfolder_path, "preview.png")
                generate_glb_cover(glb_file_path, output_image_path)


# 新增函数：指定文件夹并生成预览图
def generate_previews_from_assign_folder(folder_path):
    glb_file_path = os.path.join(folder_path, "model.glb")
    if os.path.exists(glb_file_path):
        output_image_path = os.path.join(folder_path, "preview.png")
        generate_glb_cover(glb_file_path, output_image_path)


if __name__ == "__main__":
    folder_path = "C:\\Users\\drenc\\Desktop\\test\\material\\20250513"
    generate_previews_from_folder(folder_path)

    # folder_path = "C:\\Users\\drenc\\Desktop\\test\\model\\material\\20250218\\137"
    # generate_previews_from_assign_folder(folder_path)
