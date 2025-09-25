import shutil
from pxr import Usd, UsdGeom, UsdPhysics, Gf, UsdShade, Sdf
import xml.etree.ElementTree as ET
import os
import numpy as np


class UsdToUrdfConverter:
    def __init__(self):
        self.urdf_root = ET.Element("robot")
        self.link_id_counter = 0
        self.joint_id_counter = 0
        self.transform_stack = []
        self.visited_links = set()
        self.links = {}
        self.joints = []

    def convert(self, usd_file_path, urdf_output_path):
        """主转换函数：解析USD并生成URDF"""

        # 读取usd所在目录
        usd_dir = os.path.dirname(usd_file_path)

        # 创建文件夹
        meshes_dir, materials_dir, textures_dir = self._create_mkdir(urdf_output_path)

        # 打开USD文件
        stage = Usd.Stage.Open(usd_file_path)
        if not stage:
            raise ValueError(f"无法打开USD文件: {usd_file_path}")

        # 从根节点开始遍历
        root_prim = stage.GetPseudoRoot()
        self._traverse_prim(root_prim, parent_link=None, is_root=True)

        # 导出网格
        self.export_meshes(
            stage, self.links, usd_dir, meshes_dir, materials_dir, textures_dir
        )

        # 导出URDF
        self._export_urdf(urdf_output_path)

    def _create_mkdir(self, output_dir):
        """创建文件夹"""
        # 创建meshes目录
        meshes_dir = os.path.join(output_dir, "meshes")
        os.makedirs(meshes_dir, exist_ok=True)

        # 创建materials目录
        materials_dir = os.path.join(output_dir, "materials")
        os.makedirs(materials_dir, exist_ok=True)

        # 创建textures目录
        textures_dir = os.path.join(output_dir, "textures")
        os.makedirs(textures_dir, exist_ok=True)

        return meshes_dir, materials_dir, textures_dir

    def export_meshes(
        self, stage, links, usd_dir, meshes_dir, materials_dir, textures_dir
    ):
        """导出USD中的网格为OBJ格式"""

        # 为每个网格创建OBJ文件
        for link_name, link_data in links.items():
            mesh_prim = stage.GetPrimAtPath(Sdf.Path(link_data["mesh_path"]))
            if not mesh_prim or not mesh_prim.IsA(UsdGeom.Mesh):
                print(f"警告: {link_data['mesh_path']} 不是有效的网格，跳过导出")
                continue

            obj_path = os.path.join(meshes_dir, f"{link_name}.obj")
            mtl_path = os.path.join(materials_dir, f"{link_name}.mtl")
            mdl_path = os.path.join(materials_dir, f"{link_name}.mdl")

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
                if bound_materials and isinstance(
                    bound_materials[0][0], UsdShade.Material
                ):
                    material = bound_materials[0][0]
                    material_name = material.GetPrim().GetName()

                    # 尝试提取材质信息和贴图
                    write_material_file(material, mtl_path, textures_dir, stage)
                    write_material_mdl(material, mdl_path, textures_dir)
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

    def _export_urdf(self, output_path):
        """导出URDF xml"""
        tree = ET.ElementTree(self.urdf_root)

        # 文件不存在
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        urdf_path = os.path.join(output_path, "robot.urdf")
        tree.write(urdf_path, encoding="utf-8", xml_declaration=True)
        print(f"URDF已保存至: {urdf_path}")

    def _traverse_prim(self, prim, parent_link, is_root=False):
        """递归遍历USD Prim，构建URDF结构"""
        prim_path = prim.GetPath().pathString

        # 跳过已处理的Link
        if prim_path in self.visited_links:
            return

        self.visited_links.add(prim_path)

        # 获取当前Prim的变换矩阵（累积父级变换）
        xformable = UsdGeom.Xformable(prim)
        time_code = Usd.TimeCode.Default()  # 使用默认时间码（通常是0）
        local_transform = xformable.ComputeLocalToWorldTransform(time_code)
        if self.transform_stack:
            parent_transform = self.transform_stack[-1]
            local_transform = parent_transform * local_transform

        # 处理伪根节点（特殊情况）
        if prim.IsPseudoRoot():
            # 伪根节点没有类型名称，直接遍历其子节点
            self.transform_stack.append(local_transform)
            for child_prim in prim.GetChildren():
                self._traverse_prim(child_prim, parent_link, is_root=False)
            self.transform_stack.pop()
            return

        # 处理Xform类型（变换层级）
        if prim.GetTypeName() == "Xform":
            self.transform_stack.append(local_transform)
            for child_prim in prim.GetChildren():
                self._traverse_prim(child_prim, parent_link, is_root=False)
            self.transform_stack.pop()
            return

        # 处理Link（几何实体）
        if self._is_geometric_prim(prim):

            link_name = self._generate_link_name(prim_path)
            # 获取mesh路径和变换
            mesh_prim = UsdGeom.Mesh(prim)
            mesh_path = str(mesh_prim.GetPrim().GetPath())  # 修正此处

            # 获取变换矩阵
            xform = UsdGeom.Xformable(prim)
            transform = xform.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
            translation = Gf.Vec3d(transform.ExtractTranslation())
            rotation = Gf.Rotation(transform.ExtractRotation())

            self.links[link_name] = {
                "mesh_path": mesh_path,
                "translation": translation,
                "rotation": rotation,
                "visual_mesh": None,  # 后续填充
                "collision_mesh": None,  # 后续填充
            }

            link = self._create_link(link_name, prim, local_transform)
            # self.links[link_name] = link

            # 创建Joint（非根节点时）
            if not is_root and parent_link:
                joint_name = self._generate_joint_name(prim_path)
                joint = self._create_joint(
                    joint_name, parent_link, link, local_transform
                )
                # self.joints[joint_name] = joint

            # 继续遍历子节点
            for child_prim in prim.GetChildren():
                self._traverse_prim(child_prim, link, is_root=False)

    def _is_geometric_prim(self, prim):
        """判断Prim是否为几何实体（可作为Link）"""
        return (
            prim.IsA(UsdGeom.Mesh)
            or prim.IsA(UsdGeom.Cylinder)
            or prim.IsA(UsdGeom.Sphere)
            or prim.IsA(UsdGeom.Cone)
        )

    def _generate_link_name(self, prim_path):
        """生成唯一的Link名称"""
        base_name = os.path.basename(prim_path).replace("/", "_")
        if not base_name:
            base_name = f"link_{self.link_id_counter}"
            self.link_id_counter += 1
        return base_name

    def _generate_joint_name(self, prim_path):
        """生成唯一的Joint名称"""
        base_name = os.path.basename(prim_path).replace("/", "_") + "_joint"
        if not base_name:
            base_name = f"joint_{self.joint_id_counter}"
            self.joint_id_counter += 1
        return base_name

    def _create_link(self, link_name, prim, transform):
        """创建URDF Link节点，包含几何和惯性信息"""
        link = ET.SubElement(self.urdf_root, "link", name=link_name)

        # 转换变换矩阵为URDF的origin
        origin = self._transform_to_origin(transform)
        if origin:
            link.append(origin)

        # 添加几何信息
        visual = ET.SubElement(link, "visual")
        visual.append(ET.SubElement(visual, "origin"))
        geometry = ET.SubElement(visual, "geometry")

        if prim.IsA(UsdGeom.Mesh):
            self._add_mesh_geometry(geometry, prim)
        elif prim.IsA(UsdGeom.Cylinder):
            self._add_cylinder_geometry(geometry, prim)
        elif prim.IsA(UsdGeom.Sphere):
            self._add_sphere_geometry(geometry, prim)
        elif prim.IsA(UsdGeom.Cone):
            self._add_cone_geometry(geometry, prim)

        # 添加碰撞信息（简化为视觉几何）
        collision = ET.SubElement(link, "collision")
        collision.append(ET.SubElement(collision, "origin"))
        collision_geometry = ET.SubElement(collision, "geometry")

        # 修正后代码
        if len(geometry):
            geom_element = geometry[0]
            new_element = ET.Element(geom_element.tag, geom_element.attrib)
            new_element.text = geom_element.text
            new_element.tail = geom_element.tail
            collision_geometry.append(new_element)

        # 添加惯性信息（默认值，需根据实际模型调整）
        inertia = ET.SubElement(link, "inertial")
        inertia.append(ET.SubElement(inertia, "mass", value="1.0"))
        inertia.append(
            ET.SubElement(
                inertia,
                "inertia",
                ixx="0.1",
                ixy="0.0",
                ixz="0.0",
                iyy="0.1",
                iyz="0.0",
                izz="0.1",
            )
        )

        return link

    def _add_mesh_geometry(self, parent, prim):
        """添加Mesh几何到URDF"""
        mesh = UsdGeom.Mesh(prim)
        mesh_element = ET.SubElement(parent, "mesh")

        # 获取USD中的USDZ格式引用（若有）
        # 或直接生成STL数据（需额外处理）
        # 此处简化为引用外部STL文件
        usd_prim_path = prim.GetPath().pathString
        stl_path = f"{usd_prim_path.replace('/', '_')}.stl"
        mesh_element.set("filename", stl_path)

    def _add_cylinder_geometry(self, parent, prim):
        """添加圆柱体几何到URDF"""
        cylinder = UsdGeom.Cylinder(prim)
        radius = cylinder.GetRadiusAttr().Get() or 0.1
        height = cylinder.GetHeightAttr().Get() or 0.2
        cylinder_element = ET.SubElement(
            parent, "cylinder", radius=f"{radius}", length=f"{height}"
        )

    def _add_sphere_geometry(self, parent, prim):
        """添加球体几何到URDF"""
        sphere = UsdGeom.Sphere(prim)
        radius = sphere.GetRadiusAttr().Get() or 0.1
        sphere_element = ET.SubElement(parent, "sphere", radius=f"{radius}")

    def _add_cone_geometry(self, parent, prim):
        """添加圆锥体几何到URDF"""
        cone = UsdGeom.Cone(prim)
        radius = cone.GetRadiusAttr().Get() or 0.1
        height = cone.GetHeightAttr().Get() or 0.2
        cone_element = ET.SubElement(
            parent, "cone", radius=f"{radius}", length=f"{height}"
        )

    def _create_joint(self, joint_name, parent_link, child_link, transform):
        """创建URDF Joint节点"""
        joint = ET.SubElement(
            self.urdf_root, "joint", name=joint_name, type="fixed"
        )  # 默认为固定关节
        joint.set("parent", parent_link)
        joint.set("child", child_link)

        # 设置关节原点（从变换矩阵提取）
        origin = self._transform_to_origin(transform)
        if origin:
            joint.append(origin)
        return joint

    def _transform_to_origin(self, transform):
        """将变换矩阵转换为URDF的origin节点"""
        if not transform:
            return None

        # 提取平移向量 (x, y, z)
        translation = (transform[3][0], transform[3][1], transform[3][2])

        # 提取旋转矩阵
        rotation_matrix = Gf.Matrix3d(
            transform[0][0],
            transform[0][1],
            transform[0][2],
            transform[1][0],
            transform[1][1],
            transform[1][2],
            transform[2][0],
            transform[2][1],
            transform[2][2],
        )

        # 直接从矩阵提取旋转四元数
        quat = rotation_matrix.ExtractRotation().GetQuat()

        # 四元数转换为RPY (roll-pitch-yaw)
        rpy = self._quaternion_to_rpy(quat)

        origin = ET.Element("origin")
        origin.set("xyz", f"{translation[0]} {translation[1]} {translation[2]}")

        if rpy:
            origin.set("rpy", f"{rpy[0]} {rpy[1]} {rpy[2]}")

        return origin

    def _quaternion_to_rpy(self, quat):
        """四元数(qw, qx, qy, qz)转换为rpy（roll-pitch-yaw）"""
        # 注意：Gf.Quatd的顺序是 (qw, qx, qy, qz)
        qw = quat.GetReal()
        qx, qy, qz = quat.GetImaginary()

        # 四元数转RPY的标准公式
        roll = np.arctan2(2 * (qw * qx + qy * qz), 1 - 2 * (qx**2 + qy**2))
        pitch = np.arcsin(2 * (qw * qy - qz * qx))
        yaw = np.arctan2(2 * (qw * qz + qx * qy), 1 - 2 * (qy**2 + qz**2))

        return (roll, pitch, yaw)


def write_material_mdl(material, mtl_path, textures_dir):
    """写入材质文件(.mdl)并处理纹理"""

    shader = material.GetPrim().GetChild("Shader")
    try:
        # 定义材质属性（从你的数据中提取）
        properties = {
            "name": "OmniPBR",
            "diffuse_color_constant": [1, 1, 1],
            "diffuse_texture": None,
            "enable_ORM_texture": False,
            "normalmap_texture": "",
            "metallic_texture_influence": 1.0,
            "ORM_texture": None,
            "reflection_roughness_texture_influence": 1.0,
            "specular_level": 0.5,
        }

        # 漫反射颜色
        if shader.HasAttribute("inputs:diffuse_color_constant"):
            temp_value = shader.GetAttribute("inputs:diffuse_color_constant").Get()
            properties["diffuse_color_constant"][0] = temp_value[0]
            properties["diffuse_color_constant"][1] = temp_value[1]
            properties["diffuse_color_constant"][2] = temp_value[2]

        # 镜面反射颜色
        if shader.HasAttribute("inputs:specular_level"):
            properties["specular_level"] = shader.GetAttribute(
                "inputs:specular_level"
            ).Get()

        # 开启ORM纹理
        if shader.HasAttribute("inputs:enable_ORM_texture"):
            properties["enable_ORM_texture"] = shader.GetAttribute(
                "inputs:enable_ORM_texture"
            ).Get()
        else:
            properties["enable_ORM_texture"] = False

        # ORM纹理
        if shader.HasAttribute("inputs:ORM_texture"):
            properties["ORM_texture"] = shader.GetAttribute("inputs:ORM_texture").Get()

        # 法线
        if shader.HasAttribute("inputs:normalmap_texture"):
            properties["normalmap_texture"] = shader.GetAttribute(
                "inputs:normalmap_texture"
            ).Get()

        # 漫反射材质
        if shader.HasAttribute("inputs:diffuse_texture"):
            properties["diffuse_texture"] = shader.GetAttribute(
                "inputs:diffuse_texture"
            ).Get()

        # 粗糙度
        if shader.HasAttribute("inputs:reflection_roughness_texture_influence"):
            properties["reflection_roughness_texture_influence"] = shader.GetAttribute(
                "inputs:reflection_roughness_texture_influence"
            ).Get()

        # 金属度
        if shader.HasAttribute("inputs:metallic_texture_influence"):
            properties["metallic_texture_influence"] = shader.GetAttribute(
                "inputs:metallic_texture_influence"
            ).Get()

        # 复制材质文件
        if (
            properties["diffuse_texture"] is not None
            and properties["diffuse_texture"] != ""
        ):
            name = os.path.basename(properties["diffuse_texture"].path)
            src_texture = properties["diffuse_texture"].resolvedPath

            dest_texture = os.path.join(textures_dir, name)

            if not os.path.exists(dest_texture):
                # 复制文件
                shutil.copy2(src_texture, dest_texture)
                print(f"复制diffuse材质")
            else:
                print(f"diffuse材质已存在")

        # 复制ORM材质文件
        if properties["ORM_texture"] is not None and properties["ORM_texture"] != "":
            name = os.path.basename(properties["ORM_texture"].path)
            src_texture = properties["ORM_texture"].resolvedPath

            dest_texture = os.path.join(textures_dir, name)

            if not os.path.exists(dest_texture):
                # 复制文件
                shutil.copy2(src_texture, dest_texture)
                print(f"复制ORM材质")
            else:
                print(f"ORM材质已存在")

        # 复制法线材质文件
        if (
            properties["normalmap_texture"] is not None
            and properties["normalmap_texture"] != ""
        ):
            name = os.path.basename(properties["normalmap_texture"].path)
            src_texture = properties["normalmap_texture"].resolvedPath

            dest_texture = os.path.join(textures_dir, name)

            if not os.path.exists(dest_texture):
                # 复制文件
                shutil.copy2(src_texture, dest_texture)
                print(f"复制normal材质")
            else:
                print(f"normal材质已存在")

        # 生成 MDL 代码的模板
        mdl_template = """
            import "OmniPBR.mdl"; // 对应 info:mdl:sourceAsset 里的 @OmniPBR.mdl@

            material {name}(
                // 基础颜色属性
                color diffuse_color_constant = color({diffuse_color[0]}, {diffuse_color[1]}, {diffuse_color[2]}),
                texture_2d diffuse_texture = texture_2d("{diffuse_texture}"),

                // ORM纹理属性
                bool enable_ORM_texture = {enable_ORM_texture},
                float metallic_texture_influence = {metallic_texture_influence},
                texture_2d ORM_texture = texture_2d("{ORM_texture}"),
                float reflection_roughness_texture_influence = {reflection_roughness_texture_influence},

                // 高光属性
                float specular_level = {specular_level}

                // 法线贴图属性
                texture_2d normalmap_texture = texture_2d("{normalmap_texture}"),
                float normal_strength = 1.0  // 法线强度控制（0.0~1.0）
            ) {{
                surface {{
                      // 1. 计算基础颜色（漫反射颜色 * 漫反射纹理采样）
                    texture_2d_sample diffuse_sample = texture_2d_sample(diffuse_texture, uv_world());
                    color base_color = diffuse_color_constant * diffuse_sample.rgb;

                    
                    // 2. 处理ORM纹理（修正通道映射：R=金属度，G=粗糙度，B=环境光遮蔽）
                    float metallic = 0.0;
                    float roughness = 0.5;  // 默认粗糙度
                    float occlusion = 1.0;  // 默认环境光遮蔽（1.0表示无遮蔽）
                    
                    if (enable_ORM_texture) {{
                        texture_2d_sample orm_sample = texture_2d_sample(ORM_texture, uv_world());
                        metallic = orm_sample.r * metallic_texture_influence;  // 金属度（R通道）
                        roughness = orm_sample.g * reflection_roughness_texture_influence;  // 粗糙度（G通道）
                        occlusion = orm_sample.b;  // 环境光遮蔽（B通道）
                    }}

                    
                    // 3. 处理法线贴图
                    vector normal = vector(0.0, 0.0, 1.0);  // 默认法线（垂直表面）
                    if (normalmap_texture != texture_2d("")) {{  // 若法线贴图存在
                        texture_2d_sample normal_sample = texture_2d_sample(normalmap_texture, uv_world());
                        // 法线贴图RGB范围[0,1]转法向量范围[-1,1]
                        normal = normalize(vector(
                            2.0 * normal_sample.r - 1.0,
                            2.0 * normal_sample.g - 1.0,
                            2.0 * normal_sample.b - 1.0
                        ));
                        normal = normalize(normal);
                    }}
                    
                    float specular = specular_level;
                    
                    // 输出PBR核心属性（根据渲染器要求调整属性名）
                    return material_surface(
                        base_color = base_color,
                        metallic = metallic,
                        roughness = roughness,
                        occlusion = occlusion,
                        normal = normal,
                        specular = specular
                    );
                }}
            }}
            """

        # 填充模板
        mdl_code = mdl_template.format(
            name=properties["name"],
            diffuse_color=properties["diffuse_color_constant"],
            diffuse_texture=properties["diffuse_texture"],
            enable_ORM_texture=(
                "true" if properties["enable_ORM_texture"] else "false"
            ),
            metallic_texture_influence=properties["metallic_texture_influence"],
            ORM_texture=properties["ORM_texture"],
            reflection_roughness_texture_influence=properties[
                "reflection_roughness_texture_influence"
            ],
            specular_level=properties["specular_level"],
            normalmap_texture=properties["normalmap_texture"],
        )

        with open(mtl_path, "w") as f:
            f.write(mdl_code)
    except Exception as e:
        print(f"导出材质文件失败2: {e}")


def write_material_file(material, mtl_path, textures_dir, stage):
    """写入材质文件(.mtl)并处理纹理"""
    import shutil

    try:
        with open(mtl_path, "w") as f:
            material_name = material.GetPrim().GetName()
            shader = material.GetPrim().GetChild("Shader")

            # ORM纹理
            texture_files = {
                "ORM_texture": None,
                "diffuse_texture": None,
                "enable_ORM_texture": False,
                "normalmap_texture": None,
            }

            # ORM材质
            if shader.HasAttribute("inputs:enable_ORM_texture"):
                texture_files["enable_ORM_texture"] = (
                    True
                    if shader.GetAttribute("inputs:enable_ORM_texture").Get()
                    else False
                )

            if shader.HasAttribute("inputs:ORM_texture"):
                texture_files["ORM_texture"] = shader.GetAttribute(
                    "inputs:ORM_texture"
                ).Get()

            # 漫反射材质
            if shader.HasAttribute("inputs:diffuse_texture"):
                texture_files["diffuse_texture"] = shader.GetAttribute(
                    "inputs:diffuse_texture"
                ).Get()

            # 法线贴图材质
            if shader.HasAttribute("inputs:normalmap_texture"):
                texture_files["normalmap_texture"] = shader.GetAttribute(
                    "inputs:normalmap_texture"
                ).Get()

            f.write(f"# Material file\n")
            f.write(f"newmtl {material_name}\n")
            f.write("\n")

            f.write("Ni 1.000000\n")  # 光学密度
            f.write("d 1.000000\n")  # 透明度
            f.write("illum 2\n")  # 光照模型
            f.write("\n")

            # 漫反射颜色
            if shader.HasAttribute("inputs:diffuse_color_constant"):
                kd_value = shader.GetAttribute("inputs:diffuse_color_constant").Get()
                f.write(f"Ka {kd_value[0]} {kd_value[1]} {kd_value[2]}\n")
                f.write(f"Kd {kd_value[0]} {kd_value[1]} {kd_value[2]}\n")
            else:
                f.write("Ka 1.000000 1.000000 1.000000\n")  # 环境光颜色
                f.write("Kd 1.000000 1.000000 1.000000\n")  # 漫反射颜色
            f.write("\n")

            # 镜面反射颜色
            if shader.HasAttribute("inputs:specular_level"):
                ks_value = shader.GetAttribute("inputs:specular_level").Get()
                f.write(f"Ks {ks_value} {ks_value} {ks_value}\n")  # 镜面反射颜色
            else:
                f.write("Ks 1.000000 1.000000 1.000000\n")  # 镜面反射颜色
            f.write("\n")

            # 粗糙度
            if shader.HasAttribute("inputs:reflection_roughness_texture_influence"):
                ns_value = shader.GetAttribute(
                    "inputs:reflection_roughness_texture_influence"
                ).Get()
                ns = 1000 * (1 - ns_value)
                f.write(f"Ns {ns}\n")  # 粗糙度
            else:
                f.write("Ns 96.078431\n")  # 光泽度
            f.write("\n")

            # 处理基础颜色/漫反射纹理
            if (
                "diffuse_texture" in texture_files
                and texture_files["diffuse_texture"] is not None
            ):
                src_texture = texture_files["diffuse_texture"].resolvedPath
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
            f.write("\n")

            # ORM（金属度、粗糙度、环境光遮蔽）
            if (
                "ORM_texture" in texture_files
                and texture_files["enable_ORM_texture"]
                and texture_files["ORM_texture"] is not None
            ):
                src_texture = texture_files["ORM_texture"].resolvedPath
                dest_texture = os.path.join(textures_dir, os.path.basename(src_texture))

                # 复制纹理文件
                try:
                    if not os.path.exists(dest_texture):
                        shutil.copy2(src_texture, dest_texture)
                        print(f"复制纹理: {src_texture} -> {dest_texture}")
                    else:
                        print(f"纹理已存在: {dest_texture}")

                    # 在MTL文件中引用纹理
                    f.write(f"map_Ks ../textures/{os.path.basename(src_texture)}\n")
                    f.write(f"map_Ns ../textures/{os.path.basename(src_texture)}\n")
                    f.write(f"map_Ka ../textures/{os.path.basename(src_texture)}\n")
                except Exception as e:
                    print(f"复制纹理失败: {e}")
            f.write("\n")

            # 法线贴图
            if (
                "normalmap_texture" in texture_files
                and texture_files["normalmap_texture"] is not None
            ):
                src_texture = texture_files["normalmap_texture"].resolvedPath
                dest_texture = os.path.join(textures_dir, os.path.basename(src_texture))

                # 复制纹理文件
                try:
                    if not os.path.exists(dest_texture):
                        shutil.copy2(src_texture, dest_texture)
                        print(f"复制纹理: {src_texture} -> {dest_texture}")
                    else:
                        print(f"纹理已存在: {dest_texture}")

                    # 在MTL文件中引用纹理
                    f.write(f"map_dump ../textures/{os.path.basename(src_texture)}\n")
                except Exception as e:
                    print(f"复制纹理失败: {e}")
            f.write("\n")

            ##### PBR属性 (非标准MTL扩展) #####

            f.write("# PBR\n")

            # 粗糙度
            if shader.HasAttribute("inputs:reflection_roughness_texture_influence"):
                ns_value = shader.GetAttribute(
                    "inputs:reflection_roughness_texture_influence"
                ).Get()
                f.write(f"Pr {ns_value}\n")  # 粗糙度
            f.write("\n")

            # 金属度
            if shader.HasAttribute("inputs:metallic_texture_influence"):
                ns_value = shader.GetAttribute(
                    "inputs:metallic_texture_influence"
                ).Get()
                f.write(f"Pm {ns_value}\n")
            f.write("\n")

            # ORM（金属度、粗糙度、环境光遮蔽）
            if "ORM_texture" in texture_files and texture_files["enable_ORM_texture"] and texture_files["ORM_texture"] is not None:
                src_texture = texture_files["ORM_texture"].resolvedPath
                dest_texture = os.path.join(textures_dir, os.path.basename(src_texture))

                # 复制纹理文件
                try:
                    if not os.path.exists(dest_texture):
                        shutil.copy2(src_texture, dest_texture)
                        print(f"复制纹理: {src_texture} -> {dest_texture}")
                    else:
                        print(f"纹理已存在: {dest_texture}")

                    # 在MTL文件中引用纹理
                    f.write(f"Pm ../textures/{os.path.basename(src_texture)}\n")
                    f.write(f"Pr ../textures/{os.path.basename(src_texture)}\n")
                    f.write(f"Ao ../textures/{os.path.basename(src_texture)}\n")
                except Exception as e:
                    print(f"复制纹理失败: {e}")
            f.write("\n")

            # 提取纹理信息
            # texture_files = find_texture_files(material, stage)

            # 处理法线贴图
            # if "normal" in texture_files and texture_files["normal"] is not None:
            #     src_texture = texture_files["normal"].resolvedPath
            #     dest_texture = os.path.join(textures_dir, os.path.basename(src_texture))

            #     try:
            #         if not os.path.exists(dest_texture):
            #             shutil.copy2(src_texture, dest_texture)
            #             print(f"复制法线贴图: {src_texture} -> {dest_texture}")

            #         # 在MTL文件中引用法线贴图
            #         f.write(f"map_bump ../textures/{os.path.basename(src_texture)}\n")
            #     except Exception as e:
            #         print(f"复制法线贴图失败: {e}")

            # 处理其他纹理类型（如粗糙度、金属度等）
            # for tex_type, tex_path in texture_files.items():
            #     if tex_type not in ["diffuse", "normal"]:
            #         src_texture = tex_path
            #         dest_texture = os.path.join(
            #             textures_dir, os.path.basename(src_texture)
            #         )

            #         try:
            #             if not os.path.exists(dest_texture):
            #                 shutil.copy2(src_texture, dest_texture)
            #                 print(
            #                     f"复制{tex_type}贴图: {src_texture} -> {dest_texture}"
            #                 )

            #             # 根据纹理类型写入适当的MTL指令
            #             if tex_type == "roughness":
            #                 f.write(
            #                     f"map_Pr ../textures/{os.path.basename(src_texture)}\n"
            #                 )
            #             elif tex_type == "metallic":
            #                 f.write(
            #                     f"map_Pm ../textures/{os.path.basename(src_texture)}\n"
            #                 )
            #             # 可以添加更多纹理类型映射

            #         except Exception as e:
            #             print(f"复制{tex_type}贴图失败: {e}")

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
            if len(connection) == 0:
                continue
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


# 使用示例
if __name__ == "__main__":
    usd_file = "D:\project\SmileX\capture-resource-python\Lightwheel_Oven036/Oven036.usd"  # 替换为实际USD文件路径
    urdf_dir = "D:\project\SmileX\capture-resource-python\Lightwheel_Oven036/output/"  # 替换为输出路径

    converter = UsdToUrdfConverter()
    converter.convert(usd_file, urdf_dir)
