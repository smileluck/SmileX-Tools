from pxr import Usd, UsdGeom, UsdPhysics, Gf
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
        
    def convert(self, usd_file_path, urdf_output_path):
        """主转换函数：解析USD并生成URDF"""
        # 打开USD文件
        stage = Usd.Stage.Open(usd_file_path)
        if not stage:
            raise ValueError(f"无法打开USD文件: {usd_file_path}")
            
        # 从根节点开始遍历
        root_prim = stage.GetPseudoRoot()
        self._traverse_prim(root_prim, parent_link=None, is_root=True)
        
        # 生成XML文件
        tree = ET.ElementTree(self.urdf_root)
        tree.write(urdf_output_path, encoding="utf-8", xml_declaration=True)
        print(f"URDF已保存至: {urdf_output_path}")
    
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
        return prim.IsA(UsdGeom.Mesh) or prim.IsA(UsdGeom.Cylinder) or \
               prim.IsA(UsdGeom.Sphere) or prim.IsA(UsdGeom.Cone)
    
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
        inertia.append(ET.SubElement(inertia, "inertia", 
                                    ixx="0.1", ixy="0.0", ixz="0.0",
                                    iyy="0.1", iyz="0.0", izz="0.1"))
        
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
        cylinder_element = ET.SubElement(parent, "cylinder", 
                                        radius=f"{radius}", length=f"{height}")
    
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
        cone_element = ET.SubElement(parent, "cone", 
                                    radius=f"{radius}", length=f"{height}")
    
    def _create_joint(self, joint_name, parent_link, child_link, transform):
        """创建URDF Joint节点"""
        joint = ET.SubElement(self.urdf_root, "joint", 
                             name=joint_name, type="fixed")  # 默认为固定关节
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
            transform[0][0], transform[0][1], transform[0][2],
            transform[1][0], transform[1][1], transform[1][2],
            transform[2][0], transform[2][1], transform[2][2]
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
# 使用示例
if __name__ == "__main__":
    usd_file = "D:\project\SmileX\capture-resource-python\Lightwheel_Refrigerator044/Refrigerator044.usd"  # 替换为实际USD文件路径
    urdf_file = "D:\project\SmileX\capture-resource-python\Lightwheel_Refrigerator044/Refrigerator044.urdf"  # 替换为输出路径
    
    converter = UsdToUrdfConverter()
    converter.convert(usd_file, urdf_file)