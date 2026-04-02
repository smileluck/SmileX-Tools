# UV 多项目管理指南

## 简介

UV 是 Rust 编写的超高速 Python 包管理器，支持多项目管理工作流。本文档介绍在 SmileX 项目中使用 UV 进行多项目管理的常用命令。

## 项目结构

```
python/
├── .python-version          # 全局 Python 版本配置
├── pyproject.toml           # 根项目配置
├── uv.lock                  # 锁定文件
├── capture/                 # 爬虫模块
├── hardware/                # 硬件模块
└── pdf-password/            # PDF 密码模块
```

## 常用命令

### 1. 初始化子项目

在已有目录下创建新的 UV 项目：

```bash
# 为 pdf-password 模块创建项目
uv init --project .\pdf-password\

# 为 hardware 模块创建项目
uv init --project .\hardware\

# 为 capture 模块创建项目
uv init --project .\capture\
```

### 2. 添加依赖

向指定子项目添加依赖包：

```bash
# 为 pdf-password 添加 pyhanko 库
uv add pyhanko --project .\pdf-password\

# 为 pdf-password 添加多个依赖
uv add pyhanko pdfplumber --project .\pdf-password\

# 为 capture 添加 playwright
uv add playwright --project .\capture\

# 添加开发依赖
uv add pytest --dev --project .\pdf-password\
```

### 3. 安装依赖

安装指定项目的依赖：

```bash
# 安装 pdf-password 的依赖
uv sync --project .\pdf-password\

# 安装所有项目的依赖
uv sync --project .\capture\
uv sync --project .\hardware\
```

### 4. 运行脚本

在指定项目环境中运行 Python 脚本：

```bash
# 运行 pdf-password 模块的 main.py
uv run --project .\pdf-password\ python main.py

# 在 capture 项目环境中运行脚本
uv run --project .\capture\ python some_script.py
```

### 5. 移除依赖

从指定项目移除依赖：

```bash
# 从 pdf-password 移除某个依赖
uv remove pyhanko --project .\pdf-password\
```

### 6. 查看项目信息

```bash
# 查看 pdf-password 项目的依赖树
uv tree --project .\pdf-password\

# 查看所有项目的依赖情况
uv tree --project .\capture\
uv tree --project .\hardware\
```

### 7. 更新依赖

更新指定项目的依赖包：

```bash
# 更新 pdf-password 的所有依赖
uv lock --project .\pdf-password\
uv sync --project .\pdf-password\

# 更新特定包
uv add pyhanko@latest --project .\pdf-password\
```

### 8. 虚拟环境管理

```bash
# 为特定项目创建虚拟环境
uv venv --project .\pdf-password\

# 激活虚拟环境 (Windows PowerShell)
.\pdf-password\.venv\Scripts\Activate.ps1

# 激活虚拟环境 (Windows CMD)
.\pdf-password\.venv\Scripts\activate.bat
```

## 工作流程示例

### 新增一个功能模块

```bash
# 1. 创建项目目录
mkdir new-module
cd new-module

# 2. 初始化为 UV 项目
uv init --project .\new-module\

# 3. 添加所需依赖
uv add requests beautifulsoup4 --project .\new-module\

# 4. 编写代码后运行
uv run --project .\new-module\ python main.py

# 5. 同步确保依赖锁定
uv sync --project .\new-module\
```

### 跨项目共享依赖

如果多个项目需要相同的依赖，可以在根目录的 `pyproject.toml` 中声明：

```bash
# 在根目录添加共享依赖
uv add pytest --project .\

# 子项目继承使用
uv sync --project .\capture\
```

## 注意事项

1. **项目标识**: `--project` 参数指定了项目根目录的 `pyproject.toml` 位置
2. **锁定文件**: 每个子项目可以有独立的 `uv.lock`，也可以共享根目录的锁定文件
3. **Python 版本**: 建议在每个子项目的 `pyproject.toml` 中指定 `requires-python` 版本
4. **依赖冲突**: 不同子项目可以使用不同版本的相同依赖，互不影响

## 常见问题

### Q: 如何查看当前项目的配置？

```bash
uv show --project .\pdf-password\
```

### Q: 如何导出依赖列表？

```bash
uv pip freeze --project .\pdf-password\
```

### Q: 如何清理并重新安装依赖？

```bash
# 删除锁文件和已安装包
rm .\pdf-password\uv.lock
rm -rf .\pdf-password\.venv

# 重新安装
uv sync --project .\pdf-password\
```
