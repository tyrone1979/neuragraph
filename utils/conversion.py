import json
import re
from typing import Dict, Any, List, TypedDict, get_type_hints, TypeVar,Iterator
T = TypeVar("T", bound=TypedDict)

def convert_to_list(raw: str) -> list:
    """
    将各种格式的字符串转换为列表

    支持以下格式：
    1. 标准JSON列表：'["one","two"]'
    2. 不完整JSON列表：'["one","two"' -> 补全为 '["one","two"]'
    3. 代码块中的JSON：'```json["one","two"]```' -> 提取并解析
    4. 纯文本按行分割：'one\ntwo' -> ['one', 'two']
    5. 单引号列表："['one','two']" -> 转换为双引号后解析
    6. 混合格式等
    """
    if not raw:
        return []

    # 先尝试直接解析
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # 预处理：去除常见的代码块标记
    cleaned = raw.strip()

    # 移除常见的代码块标记
    code_block_patterns = [
        r'^```(?:json)?\s*',  # 开头的 ``` 或 ```json
        r'\s*```$',  # 结尾的 ```
        r'^`\s*',  # 开头的 `
        r'\s*`$',  # 结尾的 `
    ]

    for pattern in code_block_patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)

    cleaned = cleaned.strip()

    # 尝试解析清理后的字符串
    if cleaned:
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

    # 处理不完整的JSON
    if cleaned.startswith('[') and not cleaned.endswith(']'):
        # 尝试补全闭合的括号和引号
        fixed_json = cleaned

        # 统计未闭合的括号
        open_brackets = fixed_json.count('[')
        close_brackets = fixed_json.count(']')
        open_braces = fixed_json.count('{')
        close_braces = fixed_json.count('}')
        open_quotes = fixed_json.count('"')

        # 补全缺失的括号
        brackets_to_add = open_brackets - close_brackets
        for _ in range(brackets_to_add):
            fixed_json += ']'

        braces_to_add = open_braces - close_braces
        for _ in range(braces_to_add):
            fixed_json += '}'

        # 如果引号数量是奇数，添加一个引号
        if open_quotes % 2 == 1:
            fixed_json += '"'

        try:
            return json.loads(fixed_json)
        except json.JSONDecodeError:
            pass

    # 尝试处理单引号格式的列表
    if cleaned.startswith('[') and cleaned.endswith(']') and "'" in cleaned:
        # 将单引号转换为双引号，但要避免转义内部的内容
        try:
            # 使用 ast.literal_eval 处理Python风格的列表
            import ast
            return ast.literal_eval(cleaned)
        except (SyntaxError, ValueError):
            # 简单的单引号替换（不完美但能处理简单情况）
            double_quoted = re.sub(r"(?<!\\)'", '"', cleaned)
            double_quoted = double_quoted.replace('\\"', '"')
            try:
                return json.loads(double_quoted)
            except json.JSONDecodeError:
                pass

    # 尝试处理用逗号分隔的列表格式
    if cleaned.startswith('[') and cleaned.endswith(']'):
        # 提取括号内的内容
        content = cleaned[1:-1].strip()
        if content:
            # 尝试按逗号分割，并去除引号
            items = []
            in_quotes = False
            current_item = ''

            for char in content:
                if char == '"' and not in_quotes:
                    in_quotes = True
                elif char == '"' and in_quotes:
                    in_quotes = False
                    if current_item:
                        items.append(current_item)
                        current_item = ''
                elif char == ',' and not in_quotes and current_item:
                    items.append(current_item.strip())
                    current_item = ''
                else:
                    current_item += char

            if current_item.strip():
                items.append(current_item.strip())

            if items:
                return items

    # 最后尝试按行分割
    lines = raw.strip().split('\n')

    # 清理每行的内容
    result = []
    for line in lines:
        line = line.strip()
        # 移除空行
        if line:
            # 移除可能的列表标记（如 1., 2., - 等）
            line = re.sub(r'^[-\*•]\s*', '', line)
            line = re.sub(r'^\d+[\.\)]\s*', '', line)
            # 移除代码块标记
            line = re.sub(r'^`+|`+$', '', line)
            result.append(line.strip())

    return result




def jsonify_state(state: T) -> T:
    """把 TypedDict 中值是 JSON 字符串的字段就地转成对象/list"""
    # 只拿出 TypedDict 声明的键
    for key in state:
        val = state.get(key)  # TypedDict 按 dict 方式取值
        if not isinstance(val, str):
            continue
        try:
            parsed = json.loads(val.strip())
            # 只处理 []  [{}]  {}
            if isinstance(parsed, (list, dict)):
                state[key] = parsed  # 写回 TypedDict
        except json.JSONDecodeError as e:
                continue

        except Exception as e:
            # 其他意外错误
            print(f"[ERROR] Unexpected error for key '{key}': {type(e).__name__}: {e}")
            continue
    return state