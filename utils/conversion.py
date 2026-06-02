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


_ENTITY_KEYS = frozenset({"text", "id", "label"})


def normalize_entity_record(item: Any) -> dict[str, Any] | None:
    """Normalize one entity dict to {text, id, label}."""
    if not isinstance(item, dict):
        return None
    text = (item.get("text") or item.get("name") or "").strip()
    eid = (item.get("id") or item.get("mesh") or item.get("mesh_id") or "").strip()
    label = (item.get("label") or item.get("type") or "").strip()
    if not text or not eid:
        return None
    return {"text": text, "id": eid, "label": label}


def parse_entity_list(raw: Any) -> list[dict[str, Any]]:
    """
    Parse LLM output into [{text, id, label}, ...].
    Ignores chain-of-thought lines; prefers the last JSON array of entity objects.
    """
    if raw is None:
        return []
    if isinstance(raw, list):
        if raw and all(isinstance(x, dict) for x in raw):
            out = [normalize_entity_record(x) for x in raw]
            return [e for e in out if e]
        if raw and all(isinstance(x, str) for x in raw):
            raw = "\n".join(raw)
        elif not raw:
            return []
    if not isinstance(raw, str):
        return []

    text = raw.strip()
    if not text:
        return []

    candidates: list[str] = []

    for block in re.findall(r"```(?:json)?\s*([\s\S]*?)\s*```", text, flags=re.IGNORECASE):
        block = block.strip()
        if block.startswith("["):
            candidates.append(block)

    i = 0
    while i < len(text):
        if text[i] != "[":
            i += 1
            continue
        depth = 0
        for j in range(i, len(text)):
            ch = text[j]
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    snippet = text[i : j + 1]
                    if '"text"' in snippet and '"id"' in snippet:
                        candidates.append(snippet)
                    i = j + 1
                    break
        else:
            break

    for candidate in reversed(candidates):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            try:
                import ast
                parsed = ast.literal_eval(candidate)
            except (SyntaxError, ValueError):
                continue
        if not isinstance(parsed, list):
            continue
        out = [normalize_entity_record(x) for x in parsed]
        out = [e for e in out if e]
        if out:
            return out

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            out = [normalize_entity_record(x) for x in parsed]
            return [e for e in out if e]
    except json.JSONDecodeError:
        pass

    return []


def parse_hypernym_list(raw: Any) -> list[dict[str, str]]:
    """
    Parse hypernym_identify LLM output: JSON rows or ``entity→hypernym`` lines.
    Ignores format hints like ``text,type,mesh``.
    """
    if raw is None:
        return []
    if isinstance(raw, list):
        if raw and all(isinstance(x, dict) for x in raw):
            out: list[dict[str, str]] = []
            for item in raw:
                row = _normalize_hypernym_row(item)
                if row:
                    out.append(row)
            return out
        if raw and all(isinstance(x, str) for x in raw):
            raw = "\n".join(raw)
        elif not raw:
            return []
    if not isinstance(raw, str):
        return []

    text = raw.strip()
    if not text or text.lower() in ("type", "text,type,mesh", "text, type, mesh"):
        return []

    for block in re.findall(r"```(?:json)?\s*([\s\S]*?)\s*```", text, flags=re.IGNORECASE):
        block = block.strip()
        if block.startswith("["):
            try:
                parsed = json.loads(block)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, list):
                out = [_normalize_hypernym_row(x) for x in parsed]
                return [r for r in out if r]
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            out = [_normalize_hypernym_row(x) for x in parsed]
            return [r for r in out if r]
    except json.JSONDecodeError:
        pass

    rows: list[dict[str, str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.lower() in ("type", "text,type,mesh"):
            continue
        for sep in ("→", "->", "=>"):
            if sep in line:
                left, right = line.split(sep, 1)
                rows.append({"entity": left.strip(), "hypernym": right.strip()})
                break
    return rows


def parse_plan_json(raw: Any) -> dict[str, Any]:
    """Extract refiner plan JSON; default to empty modifications when model returns prose."""
    if isinstance(raw, dict):
        if "modifications" in raw:
            return raw
        return {"modifications": []}
    if raw is None:
        return {"modifications": []}
    if not isinstance(raw, str):
        return {"modifications": []}

    text = raw.strip()
    if not text:
        return {"modifications": []}

    for block in re.findall(r"```(?:json)?\s*([\s\S]*?)\s*```", text, flags=re.IGNORECASE):
        try:
            obj = json.loads(block.strip())
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "modifications" in obj:
            return obj

    for match in re.finditer(r'\{[^{}]*"modifications"\s*:', text):
        start = match.start()
        depth = 0
        for j in range(start, len(text)):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[start : j + 1])
                    except json.JSONDecodeError:
                        break
                    if isinstance(obj, dict) and "modifications" in obj:
                        return obj
                    break

    try:
        obj = json.loads(text)
        if isinstance(obj, dict) and "modifications" in obj:
            return obj
    except json.JSONDecodeError:
        pass

    lower = text.lower()
    if "modifications" in lower and ("[]" in text or "no safe change" in lower or "no actionable" in lower):
        return {"modifications": []}
    return {"modifications": []}


def parse_relation_triples(raw: Any) -> list[str]:
    """Parse head | verb | tail lines from relation_from_tree_llm output."""
    if raw is None:
        return []
    if isinstance(raw, list):
        out: list[str] = []
        for item in raw:
            if isinstance(item, str) and "|" in item:
                out.append(item.strip())
            elif isinstance(item, dict):
                head = (item.get("head") or item.get("subject") or "").strip()
                pred = (item.get("predicate") or item.get("verb") or "").strip()
                tail = (item.get("tail") or item.get("object") or "").strip()
                if head and pred and tail:
                    out.append(f"{head} | {pred} | {tail}")
        return out
    if not isinstance(raw, str):
        return []

    lines: list[str] = []
    for line in raw.splitlines():
        line = line.strip().strip("`")
        if not line or line.lower().startswith("here is"):
            continue
        if line.upper() == "NONE":
            continue
        if "|" in line:
            lines.append(line)
    if lines:
        return lines
    for item in convert_to_list(raw):
        if isinstance(item, str) and "|" in item:
            lines.append(item.strip())
    return lines


def _normalize_hypernym_row(item: Any) -> dict[str, str] | None:
    if not isinstance(item, dict):
        return None
    entity = (
        item.get("entity")
        or item.get("head")
        or item.get("text")
        or ""
    ).strip()
    hypernym = (item.get("hypernym") or item.get("tail") or "").strip()
    if entity and hypernym:
        return {"entity": entity, "hypernym": hypernym}
    return None


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