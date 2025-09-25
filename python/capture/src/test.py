import trimesh
# 加载OBJ模型和转换后的MTL材质
mesh = trimesh.load("D:\project\SmileX\capture-resource-python\Lightwheel_Oven036\output\meshes\Oven036_Body001.obj", material="D:\project\SmileX\capture-resource-python\Lightwheel_Oven036\output\materials\Oven036_Body001.mtl")
# 导出为GLB
mesh.export("model_with_material.glb")