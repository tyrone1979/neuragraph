from typing import Dict
from logging import getLogger
from service.meta.loader import MetaLoader
from service.entity.entity import Entity,EntityLoader
from pydantic import create_model, Field
from langchain_core.tools import StructuredTool
import re

logger = getLogger(__name__)



class ToolLoader(EntityLoader):

    @staticmethod
    def load(id:str,**extra_params):
        meta=MetaLoader.load("tools",id)
        name = meta.get("name", id)
        description = meta.get("description", "No description")
        parameters =meta.get("parameters", {"type": "object", "properties": {}, "required": []})
        code = meta.get("code")
        if not code:
            raise ValueError("Missing 'code' field")
        # 1. 动态创建输入 schema
        InputSchema = _create_input_schema(id, parameters)
        # 2. 从 code 提取函数
        func = _exec_code_to_func(code)
        # 3. 创建 StructuredTool
        return StructuredTool.from_function(func=func,name=name,description=description,args_schema=InputSchema,)

    @staticmethod
    def loads() -> Dict[str, Entity]:
        tool_registry = {}
        tool_meta_s=MetaLoader.loads("tools")

        for tool_meta in tool_meta_s:
            tool_id = tool_meta['id']
            try:
                tool_registry[tool_id] = ToolLoader.load(tool_id)
            except Exception as e:
                print(f"[ERROR] Failed to load tool {e}")

        return tool_registry

    @staticmethod
    def load_by_ids(tool_ids: list) -> list:
        tools = []
        for id in tool_ids:
            tools.append(ToolLoader.load(id))
        return tools


def _create_input_schema(tool_id: str, parameters: dict):
    """
    根据 JSON Schema 动态创建 Pydantic 输入模型
    """
    properties = parameters.get("properties", {})
    required = parameters.get("required", [])

    fields = {}
    for prop_name, prop_schema in properties.items():
        prop_type = prop_schema.get("type", "string")
        description = prop_schema.get("description", "")

        # 类型映射
        type_map = {
            "string": str,
            "integer": int,
            "number": float,
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        python_type = type_map.get(prop_type, str)

        # 默认值处理
        default = ... if prop_name in required else None

        fields[prop_name] = (python_type, Field(default=default, description=description))

    # 动态创建模型
    model_name = re.sub(r'\W|^(?=\d)', '_', tool_id.capitalize() + "Input")
    return create_model(model_name, **fields)


def _exec_code_to_func(code: str):
    """
    从 code 字符串中提取 def func(...) 的函数
    危险操作！仅用于完全可信的内部工具
    """
    local_ns = {}
    try:
        exec(code, globals(), local_ns)
        func = local_ns.get("func")
        if callable(func):
            return func
        else:
            raise ValueError("Code must define a callable named 'func'")
    except Exception as e:
        raise RuntimeError(f"Failed to execute tool code: {e}")
