# NeuraGraph 启动指南

返回 [README](../README.md) · 其他文档见 [doc/](.)

## 快速启动

### 方法 1: 使用启动脚本（推荐）

#### Windows PowerShell:
```powershell
.\start.ps1
```

#### Windows CMD:
```cmd
start.bat
```

### 方法 2: 手动启动

```bash
# 1. 激活虚拟环境
.\venv\Scripts\Activate.ps1

# 2. 设置 PYTHONPATH
$env:PYTHONPATH = "D:\projects\agentic_llmre"

# 3. 启动应用
python -m ui.app
```

## 访问地址

启动成功后，访问: **http://localhost:5001**

## 常见问题

### 1. ModuleNotFoundError: No module named 'ui'

**问题**: Python 无法找到 ui 模块

**解决方案**:
```powershell
# 设置 PYTHONPATH
$env:PYTHONPATH = "D:\projects\agentic_llmre"
```

### 2. ModuleNotFoundError: No module named 'flask_cors'

**问题**: flask-cors 未安装

**解决方案**:
```bash
pip install flask-cors
```

### 3. __init___.py 文件名错误

**问题**: 文件名是 `__init___.py` 而不是 `__init__.py`

**解决方案**:
```powershell
Rename-Item -Path "ui\__init___.py" -NewName "__init__.py"
```

## 依赖安装

如果遇到其他依赖问题：

```bash
pip install -r requirements.txt -i https://pypi.org/simple/ --trusted-host pypi.org
```

## 停止服务

按 `Ctrl+C` 停止服务
