from pxr import Usd, UsdGeom, UsdPhysics, Gf, UsdShade, Sdf
import xml.etree.ElementTree as ET
import os
import numpy as np
from xml.dom import minidom


class UsdToUrdfConverter:
    def __init__(self):
        self.urdf_root = ET.Element("robot")
        self.link_id_counter = 0
        self.joint_id_counter = 0
        self.transform_stack = []
        self.visited_links = set()

    def convert(self, usd_file_path, output_file_path):
        """主转换函数：解析USD并生成URDF"""
        meshes_dir, materials_dir, textures_dir = self._create_mkdir(output_file_path)

        try:
            # 解析USD文件
            links, joints, stage = self.parse_usd_file(usd_file_path)

            # 导出网格
            self.export_meshes(stage, links, output_file_path)

            # 创建URDF结构
            urdf_path = self.create_urdf_structure(links, joints, output_file_path)

            print(f"成功导出URDF文件到: {urdf_path}")
            print(f"模型文件保存在: {meshes_dir}")
            print(f"材质保存在: {materials_dir}")
            print(f"纹理保存在: {textures_dir}")

        except Exception as e:
            print(f"转换过程中发生错误: {e}")

    def parse_usd_file(self, usd_path):
        """解析USD文件，提取关节和链接信息"""
        stage = Usd.Stage.Open(usd_path)
        if not stage:
            raise ValueError(f"无法打开USD文件: {usd_path}")

        # 存储链接和关节信息
        links = {}
        joints = []

        # 遍历所有primitives
        for prim in stage.TraverseAll():
            if prim.IsA(UsdGeom.Mesh):
                link_name = prim.GetName()

                # 获取兄弟节点
                siblings = prim.GetParent().GetAllChildren()

                # 获取mesh路径和变换
                mesh_prim = UsdGeom.Mesh(prim)
                mesh_path = str(mesh_prim.GetPrim().GetPath())  # 修正此处

                # 获取变换矩阵
                xform = UsdGeom.Xformable(prim)
                if not xform:
                    print(f"  警告: Mesh {mesh_path} 不是Xformable类型")
                    continue

                # 获取所有XformOp
                xform_ops = xform.GetOrderedXformOps()
                if not xform_ops:
                    print(f"  此Mesh没有定义XformOp")
                    continue

                print(f"  XformOp数量: {len(xform_ops)}")

                links[link_name] = {
                    "mesh_path": mesh_path,
                    # "translation": translation,
                    # "scale": scale,
                    # "rotation": rotation,
                    # "visual_mesh": None,  # 后续填充
                    "collision_mesh": None,  # 后续填充
                }
                # 遍历并打印每个XformOp的信息
                for i, op in enumerate(xform_ops):
                    op_type = op.GetOpType()
                    op_name = op.GetName()

                    op_value = op.Get()

                    links[link_name][op_name] = op_value
                    print(f"  XformOp #{i+1}:")
                    print(f"    类型: {_get_op_type_name(op_type)} ({op_type})")
                    print(f"    名称: {op_name}")
                    print(f"    默认时间的值: {op_value}")

                # 检查是否为碰撞体
                is_collision, collisions = _check_if_collision(siblings)
                print(f"  是否为碰撞体: {is_collision}")

                if is_collision:
                    # 获取碰撞体信息
                    collision_info = _get_collision_info(collisions)
                    if collision_info:
                        print("  碰撞体信息:")
                        for key, value in collision_info.items():
                            print(f"    {key}: {value}")
                    else:
                        print("  碰撞体信息: 无详细信息")

        # 遍历所有primitives
        for prim in stage.Traverse():
            if _is_joint(prim):
                joint_info = self._extract_joint_info(prim)
                if not joint_info:
                    return
                joint_name = prim.GetName()

                # 从遍历过程中收集的joint信息创建关节数据
                # 注意：在实际应用中，这些信息应该直接在_traverse_prim中收集
                # 这里只是为了保持与现有代码结构兼容
                for i, (parent_link, child_link) in enumerate(
                    zip(links.keys(), list(links.keys())[1:])
                ):
                    joints.append(
                        {
                            "name": joint_name,
                            "type": "fixed",
                            "parent": parent_link,
                            "child": child_link,
                            "origin_xyz": [0, 0, 0],
                            "origin_rpy": [0, 0, 0],
                        }
                    )

        return links, joints, stage

    def export_meshes(self, stage, links, output_dir):
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
                if bound_materials and isinstance(
                    bound_materials[0][0], UsdShade.Material
                ):
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

    def _get_joint_limit_info(self, joint):
        """获取关节的限制信息"""
        limit_info = {}

        # 获取旋转关节的限制
        if isinstance(joint, UsdPhysics.RevoluteJoint):
            lower_limit_attr = joint.GetLowerLimitAttr()
            upper_limit_attr = joint.GetUpperLimitAttr()

            if lower_limit_attr and upper_limit_attr:
                lower_limit = lower_limit_attr.Get()
                upper_limit = upper_limit_attr.Get()
                if lower_limit is not None and upper_limit is not None:
                    limit_info["lower"] = lower_limit
                    limit_info["upper"] = upper_limit
                    # 设置默认的effort和velocity
                    limit_info["effort"] = 100.0
                    limit_info["velocity"] = 1.0

        # 获取棱柱关节的限制
        elif isinstance(joint, UsdPhysics.PrismaticJoint):
            lower_limit_attr = joint.GetLowerLimitAttr()
            upper_limit_attr = joint.GetUpperLimitAttr()

            if lower_limit_attr and upper_limit_attr:
                lower_limit = lower_limit_attr.Get()
                upper_limit = upper_limit_attr.Get()
                if lower_limit is not None and upper_limit is not None:
                    limit_info["lower"] = lower_limit
                    limit_info["upper"] = upper_limit
                    # 设置默认的effort和velocity
                    limit_info["effort"] = 100.0
                    limit_info["velocity"] = 1.0

        return limit_info if limit_info else None

    def _get_child_prim(self, joint_prim):
        """获取关节连接的子prim"""
        # 在USD中，关节通常有一个body0和body1关系，分别连接到父体和子体
        joint = UsdPhysics.Joint(joint_prim)
        if not joint:
            return None

        # 获取body1（子体）关系
        body1_rel = joint.GetBody1Rel()
        if not body1_rel.HasTargets():
            return None

        targets = body1_rel.GetTargets()
        if not targets:
            return None

        # 获取第一个目标prim
        child_prim = self.stage.GetPrimAtPath(targets[0])
        return child_prim if child_prim.IsValid() else None

    def _get_joint_type(self, joint):
        """确定关节类型"""
        # 检查是否为特定类型的关节
        if UsdPhysics.RevoluteJoint(joint):
            return "revolute"
        elif UsdPhysics.PrismaticJoint(joint):
            return "prismatic"
        elif UsdPhysics.SphericalJoint(joint):
            return "spherical"
        elif UsdPhysics.FixedJoint(joint):
            return "fixed"
        elif UsdPhysics.D6Joint(joint):
            # D6关节比较复杂，可以根据配置映射到不同的URDF类型
            return "continuous"  # 默认作为continuous处理，可根据需要调整
        else:
            return "fixed"  # 默认作为fixed处理
    def _get_origin_transform(self, prim):
            """获取prim的变换信息作为origin"""
            xformable = UsdGeom.Xformable(prim)
            if not xformable:
                return None
                
            # 获取局部变换矩阵
            transform = xformable.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
            
            # 提取平移
            translation = Gf.GetTranslates(transform)[0]
            xyz = [translation[0] * self.scale, translation[1] * self.scale, translation[2] * self.scale]
            
            # 提取旋转（转换为RPY）
            rotation = Gf.Rotation(transform.ExtractRotationMatrix())
            quat = rotation.GetQuat()
            rpy = self._quat_to_rpy(quat)
            
            return {"xyz": xyz, "rpy": rpy}
    def _extract_joint_info(self, prim):
        """从USD prim中提取关节信息"""
        joint = UsdPhysics.Joint(prim)
        if not joint:
            return None

        joint_info = {
            "name": prim.GetName(),
            "type": self._get_joint_type(joint),
            "parent": None,  # 将在后面设置
            "child": None,  # 将在后面设置
            "origin": self._get_origin_transform(prim),
            "axis": None,
            "limit": None,
        }

        # 获取关节轴
        axis_attr = joint.GetAxisAttr()
        if axis_attr:
            joint_info["axis"] = axis_attr.Get()

        # 获取关节限制（如果是revolute或prismatic关节）
        if joint_info["type"] in ["revolute", "prismatic"]:
            limit_info = self._get_joint_limit_info(joint)
            if limit_info:
                joint_info["limit"] = limit_info

        return joint_info

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
            link = self._create_link(link_name, prim, local_transform)

            # 创建Joint（非根节点时）
            if not is_root and parent_link:
                joint_name = self._generate_joint_name(prim_path)
                self._create_joint(joint_name, parent_link, link, local_transform)

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

        return link_name

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


def _is_joint(prim):
    """检查prim是否表示关节"""
    # 检查是否应用了PhysicsJoint API
    # return UsdPhysics.Joint(prim) is not None
    joint_types = [
        UsdPhysics.RevoluteJoint,
        UsdPhysics.PrismaticJoint,
        UsdPhysics.SphericalJoint,
        UsdPhysics.FixedJoint,
        # UsdPhysics.D6Joint
    ]
    for joint_type in joint_types:
        if joint_type(prim):
            return True
    return False


def _check_if_collision(prims):
    """检查prim 数组是否为碰撞体"""

    for prim in prims:

        # 方法1: 检查是否应用了CollisionAPI
        if UsdPhysics.CollisionAPI(prim):
            return True, prim

        # 方法2: 检查是否为CollisionMesh类型
        if prim.GetTypeName() == "Scope" and prim.GetName() == "Collisions":
            return True, prim

        # 方法3: 检查primvars中是否有 collisionPurpose
        if prim.HasAttribute("primvars:collisionPurpose"):
            return True, prim

    return False


def _get_collision_info(prim):
    """获取碰撞体的详细信息"""
    info = {}

    # 检查是否有CollisionAPI
    collision_api = UsdPhysics.CollisionAPI(prim)
    if collision_api:
        # 获取几何类型
        geom_type_attr = collision_api.GetCollisionGeometryTypeAttr()
        if geom_type_attr:
            geom_type = geom_type_attr.Get()
            info["几何类型"] = geom_type

        # 获取碰撞层
        layer_attr = collision_api.GetCollisionLayerAttr()
        if layer_attr:
            layer = layer_attr.Get()
            info["碰撞层"] = layer

    # 检查是否有 collisionPurpose primvar
    if prim.HasAttribute("primvars:collisionPurpose"):
        purpose_attr = prim.GetAttribute("primvars:collisionPurpose")
        if purpose_attr:
            purpose = purpose_attr.Get()
            info["碰撞用途"] = purpose

    # 获取物理材质信息
    if prim.HasRelationship("physics:material"):
        material_rel = prim.GetRelationship("physics:material")
        targets = material_rel.GetTargets()
        if targets:
            info["物理材质"] = [str(t) for t in targets]

    return info


def _get_op_type_name(op_type):
    """将XformOpType枚举值转换为可读的字符串"""
    type_names = {
        UsdGeom.XformOp.TypeTranslate: "Translate",
        UsdGeom.XformOp.TypeRotateXYZ: "RotateXYZ",
        UsdGeom.XformOp.TypeRotateXZY: "RotateXZY",
        UsdGeom.XformOp.TypeRotateYXZ: "RotateYXZ",
        UsdGeom.XformOp.TypeRotateYZX: "RotateYZX",
        UsdGeom.XformOp.TypeRotateZXY: "RotateZXY",
        UsdGeom.XformOp.TypeRotateZYX: "RotateZYX",
        UsdGeom.XformOp.TypeScale: "Scale",
        UsdGeom.XformOp.TypeTransform: "Transform",
        UsdGeom.XformOp.TypeOrient: "Orient",
    }
    return type_names.get(op_type, f"Unknown Type ({op_type})")


# 使用示例
if __name__ == "__main__":
    usd_file = "D:\project\SmileX\capture-resource-python\Lightwheel_Oven036/Oven036.usd"  # 替换为实际USD文件路径
    urdf_dir = "D:\project\SmileX\capture-resource-python\Lightwheel_Oven036/output/"  # 替换为输出路径

    converter = UsdToUrdfConverter()
    converter.convert(usd_file, urdf_dir)
