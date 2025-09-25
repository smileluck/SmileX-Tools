import os
from pxr import Usd, UsdGeom, Gf, Sdf, UsdShade
import xml.etree.ElementTree as ET
from xml.dom import minidom

# 静态变量配置
INPUT_USD_FILE = "D:\project\SmileX\capture-resource-python\Lightwheel_Refrigerator044/Refrigerator044.usd"  # 输入USD文件路径
OUTPUT_DIR = "D:\project\SmileX\capture-resource-python\Lightwheel_Refrigerator044/11/"  # 输出目录

print(Usd.GetVersion())


def parse_usd_file(usd_path):
    """解析USD文件，提取关节和链接信息"""
    stage = Usd.Stage.Open(usd_path)
    if not stage:
        raise ValueError(f"无法打开USD文件: {usd_path}")

    # 存储链接和关节信息
    links = {}
    joints = []

    # 遍历所有primitives
    for prim in stage.Traverse():
        if prim.IsA(UsdGeom.Mesh):
            link_name = prim.GetName()
            # 获取mesh路径和变换
            mesh_prim = UsdGeom.Mesh(prim)
            mesh_path = str(mesh_prim.GetPrim().GetPath())  # 修正此处

            # 获取变换矩阵
            xform = UsdGeom.Xformable(prim)
            transform = xform.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
            translation = Gf.Vec3d(transform.ExtractTranslation())
            rotation = Gf.Rotation(transform.ExtractRotation())

            links[link_name] = {
                "mesh_path": mesh_path,
                "translation": translation,
                "rotation": rotation,
                "visual_mesh": None,  # 后续填充
                "collision_mesh": None,  # 后续填充
            }

    # 这里需要根据USD中的层次结构和约束关系推断关节
    # 简化版：假设每个子链接通过关节连接到父链接
    # 实际应用中需要分析USD中的约束关系

    return links, joints, stage


def create_urdf_structure(links, joints, output_dir):
    """创建URDF文件结构"""
    # 创建根元素
    robot = ET.Element("robot", name="generated_robot")

    # 添加links
    for link_name, link_data in links.items():
        link = ET.SubElement(robot, "link", name=link_name)

        # 添加视觉元素
        visual = ET.SubElement(link, "visual")
        origin = ET.SubElement(
            visual,
            "origin",
            xyz=f"{link_data['translation'][0]} {link_data['translation'][1]} {link_data['translation'][2]}",
            rpy="0 0 0",
        )  # 简化的旋转表示
        geometry = ET.SubElement(visual, "geometry")

        # 创建相对于模型文件夹的mesh路径
        mesh_file = f"meshes/{link_name}.obj"
        mesh = ET.SubElement(geometry, "mesh", filename=mesh_file)

        # 添加材质（如果有）
        if "material" in link_data:
            material = ET.SubElement(visual, "material", name=link_data["material"])
            color = ET.SubElement(material, "color", rgba="1 1 1 1")  # 默认白色

    # 添加joints
    for joint in joints:
        joint_element = ET.SubElement(
            robot, "joint", name=joint["name"], type=joint["type"]
        )
        origin = ET.SubElement(
            joint_element,
            "origin",
            xyz=f"{joint['origin_xyz'][0]} {joint['origin_xyz'][1]} {joint['origin_xyz'][2]}",
            rpy=f"{joint['origin_rpy'][0]} {joint['origin_rpy'][1]} {joint['origin_rpy'][2]}",
        )
        parent = ET.SubElement(joint_element, "parent", link=joint["parent"])
        child = ET.SubElement(joint_element, "child", link=joint["child"])

        if joint["type"] != "fixed":
            axis = ET.SubElement(joint_element, "axis", xyz="0 0 1")  # 默认绕Z轴
            limit = ET.SubElement(
                joint_element,
                "limit",
                effort="100",
                velocity="1",
                lower=str(joint.get("lower", 0)),
                upper=str(joint.get("upper", 0)),
            )

    # 美化XML输出
    xml_str = minidom.parseString(ET.tostring(robot)).toprettyxml(indent="  ")

    # 保存URDF文件
    urdf_path = os.path.join(output_dir, "robot.urdf")
    with open(urdf_path, "w") as f:
        f.write(xml_str)

    return urdf_path


# def export_meshes(stage, links, output_dir):
#     """导出USD中的网格为OBJ格式"""
#     # 创建meshes目录
#     meshes_dir = os.path.join(output_dir, 'meshes')
#     os.makedirs(meshes_dir, exist_ok=True)

#     for link_name, link_data in links.items():
#         mesh_prim = stage.GetPrimAtPath(Sdf.Path(link_data['mesh_path']))
#         if mesh_prim:
#             mesh_prim.GetMesh().Export(mesh_prim, obj_path)
#             obj_path = os.path.join(meshes_dir, f"{link_name}.obj")

#             # 使用USD导出OBJ功能
#             # 注意：实际应用中可能需要使用UsdExport命令行工具或相关API
#             # 这里简化处理，仅作示例
#             try:
#                 # 实际实现需要使用USD的导出功能
#                 # 例如：UsdGeomExportArgs().Export(mesh_prim, obj_path)
#                 print(f"导出网格 {link_name} 到 {obj_path}")
#                 # 实际导出代码会更复杂，需要处理顶点、法线、纹理坐标等
#             except Exception as e:
#                 print(f"导出网格 {link_name} 失败: {e}")

#     # 处理材质和纹理
#     export_materials_and_textures(stage, output_dir)


def export_meshes(stage, links, output_dir):
    """导出USD中的网格为OBJ格式"""
    # 创建meshes目录
    meshes_dir = os.path.join(output_dir, "meshes")
    os.makedirs(meshes_dir, exist_ok=True)

    # 创建materials目录
    materials_dir = os.path.join(output_dir, "materials")
    os.makedirs(materials_dir, exist_ok=True)

    # 创建textures目录
    textures_dir = os.path.join(output_dir, "textures")
    os.makedirs(textures_dir, exist_ok=True)

    # 为每个网格创建OBJ文件
    for link_name, link_data in links.items():
        mesh_prim = stage.GetPrimAtPath(Sdf.Path(link_data["mesh_path"]))
        if not mesh_prim or not mesh_prim.IsA(UsdGeom.Mesh):
            print(f"警告: {link_data['mesh_path']} 不是有效的网格，跳过导出")
            continue

        obj_path = os.path.join(meshes_dir, f"{link_name}.obj")
        mtl_path = os.path.join(materials_dir, f"{link_name}.mtl")

        try:
            mesh = UsdGeom.Mesh(mesh_prim)

            # 获取顶点数据
            points = mesh.GetPointsAttr().Get()
            if not points:
                print(f"警告: 网格 {link_name} 没有顶点数据，跳过导出")
                continue

            # 获取法线数据
            normals = mesh.GetNormalsAttr().Get()

            # 获取纹理坐标
            tex_coords = None
            if mesh.GetPrim().HasAttribute("st"):
                tex_coords = mesh.GetPrim().GetAttribute("st").Get()

            # 获取面索引
            face_vertex_counts = mesh.GetFaceVertexCountsAttr().Get()
            face_vertex_indices = mesh.GetFaceVertexIndicesAttr().Get()

            # 尝试获取材质绑定
            material_binding = UsdShade.MaterialBindingAPI(mesh_prim)
            bound_materials = material_binding.ComputeBoundMaterials([mesh_prim])

            material_name = None
            if bound_materials and isinstance(bound_materials[0][0], UsdShade.Material):
                material = bound_materials[0][0]
                material_name = material.GetPrim().GetName()

                # 尝试提取材质信息和贴图
                write_material_file(material, mtl_path, textures_dir, stage)

            # 写入OBJ文件
            with open(obj_path, "w") as f:
                # 写入文件头
                f.write(f"# OBJ file exported from USD\n")
                f.write(f"# Mesh: {link_name}\n")

                # 如果有材质，引用材质文件
                if material_name:
                    f.write(f"mtllib ../materials/{link_name}.mtl\n")

                # 写入顶点
                for point in points:
                    f.write(f"v {point[0]} {point[1]} {point[2]}\n")

                # 写入法线
                if normals:
                    for normal in normals:
                        f.write(f"vn {normal[0]} {normal[1]} {normal[2]}\n")

                # 写入纹理坐标
                if tex_coords:
                    for coord in tex_coords:
                        f.write(f"vt {coord[0]} {coord[1]}\n")

                # 写入面
                current_vertex_index = 0
                for i, count in enumerate(face_vertex_counts):
                    indices = face_vertex_indices[
                        current_vertex_index : current_vertex_index + count
                    ]

                    # 写入材质组（如果有）
                    if material_name and i == 0:
                        f.write(f"usemtl {material_name}\n")

                    # 构建面的索引字符串
                    face_str = "f"
                    for idx in indices:
                        vertex_idx = idx + 1  # OBJ索引从1开始

                        if tex_coords and normals:
                            face_str += f" {vertex_idx}/{vertex_idx}/{vertex_idx}"
                        elif tex_coords:
                            face_str += f" {vertex_idx}/{vertex_idx}"
                        elif normals:
                            face_str += f" {vertex_idx}//{vertex_idx}"
                        else:
                            face_str += f" {vertex_idx}"

                    f.write(f"{face_str}\n")
                    current_vertex_index += count

            print(f"成功导出网格 {link_name} 到 {obj_path}")

        except Exception as e:
            print(f"导出网格 {link_name} 失败: {e}")


def write_material_file(material, mtl_path, textures_dir, stage):
    """写入材质文件(.mtl)并处理纹理"""
    import shutil

    try:
        with open(mtl_path, "w") as f:
            material_name = material.GetPrim().GetName()
            f.write(f"# Material file\n")
            f.write(f"newmtl {material_name}\n")

            # 设置默认材质属性
            f.write("Ns 96.078431\n")  # 光泽度
            f.write("Ka 1.000000 1.000000 1.000000\n")  # 环境光颜色
            f.write("Kd 1.000000 1.000000 1.000000\n")  # 漫反射颜色
            f.write("Ks 1.000000 1.000000 1.000000\n")  # 镜面反射颜色
            f.write("Ni 1.000000\n")  # 光学密度
            f.write("d 1.000000\n")  # 透明度
            f.write("illum 2\n")  # 光照模型

            # 提取纹理信息
            texture_files = find_texture_files(material, stage)

            # 处理基础颜色/漫反射纹理
            if "diffuse" in texture_files:
                src_texture = texture_files["diffuse"]
                dest_texture = os.path.join(textures_dir, os.path.basename(src_texture))

                # 复制纹理文件
                try:
                    if not os.path.exists(dest_texture):
                        shutil.copy2(src_texture, dest_texture)
                        print(f"复制纹理: {src_texture} -> {dest_texture}")
                    else:
                        print(f"纹理已存在: {dest_texture}")

                    # 在MTL文件中引用纹理
                    f.write(f"map_Kd ../textures/{os.path.basename(src_texture)}\n")
                except Exception as e:
                    print(f"复制纹理失败: {e}")

            # 处理法线贴图
            if "normal" in texture_files:
                src_texture = texture_files["normal"]
                dest_texture = os.path.join(textures_dir, os.path.basename(src_texture))

                try:
                    if not os.path.exists(dest_texture):
                        shutil.copy2(src_texture, dest_texture)
                        print(f"复制法线贴图: {src_texture} -> {dest_texture}")

                    # 在MTL文件中引用法线贴图
                    f.write(f"map_bump ../textures/{os.path.basename(src_texture)}\n")
                except Exception as e:
                    print(f"复制法线贴图失败: {e}")

            # 处理其他纹理类型（如粗糙度、金属度等）
            for tex_type, tex_path in texture_files.items():
                if tex_type not in ["diffuse", "normal"]:
                    src_texture = tex_path
                    dest_texture = os.path.join(
                        textures_dir, os.path.basename(src_texture)
                    )

                    try:
                        if not os.path.exists(dest_texture):
                            shutil.copy2(src_texture, dest_texture)
                            print(
                                f"复制{tex_type}贴图: {src_texture} -> {dest_texture}"
                            )

                        # 根据纹理类型写入适当的MTL指令
                        if tex_type == "roughness":
                            f.write(
                                f"map_Pr ../textures/{os.path.basename(src_texture)}\n"
                            )
                        elif tex_type == "metallic":
                            f.write(
                                f"map_Pm ../textures/{os.path.basename(src_texture)}\n"
                            )
                        # 可以添加更多纹理类型映射

                    except Exception as e:
                        print(f"复制{tex_type}贴图失败: {e}")

            print(f"成功导出材质文件到 {mtl_path}")

    except Exception as e:
        print(f"导出材质文件失败: {e}")


def find_texture_files(material, stage):
    """查找材质网络中的所有纹理文件"""
    texture_files = {}

    # 获取材质的输出连接
    outputs = material.GetOutputs()

    # 遍历所有输出，查找连接的着色器
    for output in outputs:
        connections = output.GetConnectedSources()
        for connection in connections:
            connection = connection[0]
            if connection.IsValid():
                source_prim = connection.source
                if not source_prim:
                    print(f"警告: 连接源基本体无效: {connection}")
                    continue

                # 检查是否是着色器
                shader = UsdShade.Shader(source_prim)
                if not shader:
                    continue

                # 尝试获取着色器ID
                shader_id = None
                id_attr = shader.GetIdAttr()
                if id_attr:
                    shader_id = id_attr.Get()

                # 检查是否是纹理节点（终极兼容性方法）
                is_texture = False
                if shader_id and "Texture" in shader_id:
                    is_texture = True
                else:
                    # 检查是否有"file"输入
                    file_input = shader.GetInput("file")
                    if file_input:
                        is_texture = True

                if is_texture:
                    # 获取纹理文件路径
                    file_input = shader.GetInput("file")
                    if file_input and file_input.HasValue():
                        texture_path = file_input.Get()

                        # 确定纹理类型
                        texture_type = determine_texture_type(output.GetBaseName())

                        # 存储纹理路径
                        texture_files[texture_type] = texture_path

                        print(f"找到{texture_type}纹理: {texture_path}")

                # 如果是表面着色器，继续深入查找
                is_surface_shader = False
                if shader_id and "Surface" in shader_id:
                    is_surface_shader = True
                else:
                    # 检查是否有"surface"输出
                    surface_output = shader.GetOutput("surface")
                    if surface_output:
                        is_surface_shader = True

                if is_surface_shader:
                    # 查找着色器可能连接的纹理输入
                    # 常见的纹理输入名称
                    texture_input_names = [
                        "diffuseColor",
                        "baseColor",
                        "normal",
                        "roughness",
                        "metallic",
                        "specularColor",
                    ]

                    for input_name in texture_input_names:
                        input_obj = shader.GetInput(input_name)
                        if input_obj:
                            input_conn = input_obj.GetConnectedSources()
                            for conn in input_conn:
                                if conn.IsValid():
                                    # 获取输入连接的源基本体
                                    input_source_prim = conn.source
                                    if input_source_prim:
                                        # 检查是否是纹理节点
                                        nested_shader = UsdShade.Shader(
                                            input_source_prim
                                        )
                                        if nested_shader:
                                            # 递归检查这个着色器
                                            nested_textures = (
                                                find_texture_files_in_shader(
                                                    nested_shader
                                                )
                                            )
                                            for (
                                                tex_type,
                                                tex_path,
                                            ) in nested_textures.items():
                                                texture_files[tex_type] = tex_path

    return texture_files


def find_texture_files_in_shader(shader):
    """在单个着色器节点中查找纹理文件"""
    textures = {}

    # 尝试获取着色器ID
    shader_id = None
    id_attr = shader.GetIdAttr()
    if id_attr:
        shader_id = id_attr.Get()

    # 检查是否是纹理节点
    is_texture = False
    if shader_id and "Texture" in shader_id:
        is_texture = True
    else:
        # 检查是否有"file"输入
        file_input = shader.GetInput("file")
        if file_input:
            is_texture = True

    if is_texture:
        # 获取纹理文件路径
        file_input = shader.GetInput("file")
        if file_input and file_input.HasValue():
            texture_path = file_input.Get()
            texture_type = determine_texture_type(shader.GetPrim().GetName())
            textures[texture_type] = texture_path

    return textures


def determine_texture_type(name):
    """根据名称确定纹理类型"""
    name = name.lower()

    if "diffuse" in name or "albedo" in name or "basecolor" in name:
        return "diffuse"
    elif "normal" in name or "bump" in name:
        return "normal"
    elif "roughness" in name:
        return "roughness"
    elif "metallic" in name or "metalness" in name:
        return "metallic"
    elif "specular" in name:
        return "specular"
    elif "emissive" in name:
        return "emissive"
    elif "opacity" in name or "alpha" in name:
        return "opacity"
    else:
        return "unknown_" + name


def export_materials_and_textures(stage, output_dir):
    """导出材质和纹理"""
    # 创建materials目录
    materials_dir = os.path.join(output_dir, "materials")
    os.makedirs(materials_dir, exist_ok=True)

    # 创建textures目录
    textures_dir = os.path.join(output_dir, "textures")
    os.makedirs(textures_dir, exist_ok=True)

    # 这里需要遍历USD中的材质和纹理
    # 简化版：查找所有材质和纹理并导出
    # 实际应用中需要分析USD中的材质网络

    print(f"导出材质到 {materials_dir}")
    print(f"导出纹理到 {textures_dir}")

    # 示例：遍历所有primitives查找材质和纹理
    for prim in stage.Traverse():
        if prim.HasAPI("Material"):
            # 处理材质
            pass
        # 查找纹理引用并导出到textures目录


def main():
    # 确保输出目录存在
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    try:
        # 解析USD文件
        links, joints = parse_usd_file(INPUT_USD_FILE)

        # 打开USD阶段用于导出网格
        stage = Usd.Stage.Open(INPUT_USD_FILE)

        # 导出网格
        export_meshes(stage, links, OUTPUT_DIR)

        # 创建URDF结构
        urdf_path = create_urdf_structure(links, joints, OUTPUT_DIR)

        print(f"成功导出URDF文件到: {urdf_path}")
        print(f"模型文件保存在: {os.path.join(OUTPUT_DIR, 'meshes')}")
        print(
            f"材质和纹理保存在: {os.path.join(OUTPUT_DIR, 'materials')} 和 {os.path.join(OUTPUT_DIR, 'textures')}"
        )

    except Exception as e:
        print(f"转换过程中发生错误: {e}")


if __name__ == "__main__":
    main()
