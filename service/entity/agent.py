from logging import getLogger
from langgraph.types import Checkpointer
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain.agents import create_agent
from langchain.messages import AIMessage
from pathlib import Path
import json
import csv
from typing_extensions import get_type_hints
from typing import Dict, Any, List, TypedDict, get_type_hints, TypeVar,Iterator
from service.entity.tool import ToolLoader
from utils.conversion import convert_to_list
from service.entity.entity import Entity, EntityLoader
from service.meta.loader import MetaLoader
from plugin.plugin_loader import get_plugin
from dataclasses import dataclass
T = TypeVar("T", bound=TypedDict)
import importlib

logger = getLogger(__name__)

def _jsonify_state(state: T) -> None:
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

        except Exception:
            pass

class AgentEntity(Entity):
    def __init__(self,  meta: Dict[str, Any], checkpointer: Checkpointer = None):
        super().__init__(meta,checkpointer)
        self.template = None
        self.id = meta.get("id")
        self.name=meta.get("name", "").strip()
        self.type: str | None = meta.get("type").strip()
        self.template_name = meta.get("prompt_template", {})  # 默认为空字符串
        self.inputs: List[str] = meta.get("inputs", [])
        self.persistence: Dict[str, Any] = meta.get("persistence", {})
        self.outputs: Dict[str, str] = meta.get("outputs", {})

        self.idx: str | None = meta.get("idx")
        self.process = meta.get("process", None)

        if self.type == "LLM":
            # 获取 llm_url 和 model，如果不存在则提供默认值或处理逻辑
            llm_model_id = meta.get("model", "").strip()  # 默认为空字符串
            llm_info = MetaLoader.load("llms",llm_model_id)
            if llm_info['type']=='ollama':
                self.model= ChatOllama(
                    model=llm_info['model'],  # ollama list 里看到的模型名
                    base_url=llm_info['base_url'],  # 注意带 /v1
                    temperature=llm_info['temperature'],
                )
            elif llm_info['type']=='custom':
                self.model = ChatOpenAI(
                    model=llm_info['model'],  # ollama list 里看到的模型名
                    base_url=llm_info['base_url'],
                    api_key=llm_info['api_key'],
                    temperature=llm_info['temperature'],
                    max_tokens=llm_info['max_tokens']
                )

            self.template = ChatPromptTemplate(
                [("system", self.template_name["system"]),
                 ("human", self.template_name["human"])]
            )

            tool_ids=meta.get('tools',"")
            self.tools=[]
            if tool_ids:
                self.tools=ToolLoader.load_by_ids(tool_ids)
            self.agent=create_agent(self.model,
                                    tools=self.tools,
                                    checkpointer=checkpointer)

    # ---------- 私有辅助 ----------
    def _make_llm_dict(self, state: T) -> Dict[str, Any]:
        """只把 llm_inputs 里出现的字段拿出来给 prompt 用"""
        return {k: state[k] for k in self.inputs if k in state}

    def _build_single(self, state: T, field: str, idx: int) -> T:
        hints = get_type_hints(type(state))
        return type(state)(
            **{k: (state[k][idx] if k == field else state[k]) for k in hints if k in state}
        )

    def _convert_to_type(self, raw: str, typ: str) -> Any:
        if typ == "list":
            try:
                return json.loads(raw)
            except json.JSONDecodeError as e:
                entities = raw.split('\n')
                return entities
        return raw

    def _build_output_dict(self, result: Any, state: T, item=None) -> Dict[str, Any]:
        """单字典 outputs：后处理优先，否则默认解析"""
        if not self.outputs:
            return {}

        name = self.outputs["name"]

        if self.type=='LLM':
            typ = self.outputs.get("type", "str").lower()
            if typ == "list":
                return {name: convert_to_list(result)}
            return {name: result}
        elif self.type=="PGM":
            return {name: result}
        else:
            return state[name]

    def _write_single(self, file_path: Path, name: str, file_type: str, data: Dict[str, Any],
                      columns: List[str] | None) -> None:
        full_name = file_path / f"{name}.{file_type}"
        if file_type == "csv":
            delimiter = "|" if any(isinstance(v, str) and "|" in v for v in data.values()) else ","
            if columns:
                with full_name.open("w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=columns, delimiter=delimiter)
                    writer.writeheader()
                    writer.writerow({c: data.get(c, "") for c in columns})
                return
            with full_name.open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=data.keys(), delimiter=delimiter)
                w.writeheader()
                w.writerow(data)
            return

        if file_type == "json":
            full_name.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        elif file_type == "jsonl":
            with full_name.open("a", encoding="utf-8") as f:
                f.write(json.dumps(data, ensure_ascii=False) + "\n")
        else:
            with full_name.open("w", encoding="utf-8") as f:
                for v in data.values():
                    f.write(f"{v}\n")

    def _persistence(self, dir: str, file_name: str, payload: Dict[str, Any]) -> None:
        if not self.persistence:
            return

        file_path = Path(self.persistence["file_path"].rstrip("/"))
        if dir:
            file_path = file_path / self.name / dir
        file_path.mkdir(parents=True, exist_ok=True)

        file_type = self.persistence["file_type"].lower()
        columns = self.persistence.get("columns")

        # 1. CSV 字符串块模式（仅对过滤后的字段生效）
        if file_type == "csv" and columns:
            sources: List[str] = []
            for v in payload.values():
                if isinstance(v, str):
                    sources.append(v)
                elif isinstance(v, list) and v and isinstance(v[0], str):
                    sources.extend(v)

            if sources:
                full_name = file_path / f"{file_name}.csv"
                with full_name.open("w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f, delimiter=",", quoting=csv.QUOTE_MINIMAL)
                    writer.writerow(columns)
                    for sent_idx, block in enumerate(sources, start=1):
                        lines = block
                        if isinstance(block, str):
                            lines = block.splitlines()
                        for line in lines:
                            line = line.strip()
                            if not line:
                                continue
                            parts = line.split('|')
                            if len(parts) != len(columns):
                                continue
                            writer.writerow([*(p.strip() for p in parts)])
            return

        # 2. 其余格式（list 拆条 / json / jsonl / txt）**仅对过滤后的字段生效**
        list_lens = [len(v) for v in payload.values() if isinstance(v, list)]
        if list_lens:
            length = list_lens[0]
            for idx in range(length):
                single = {k: (v[idx] if isinstance(v, list) else v) for k, v in payload.items()}
                self._write_single(file_path, f"{file_name}_{idx}", file_type, single, columns)
        else:
            self._write_single(file_path, file_name, file_type, payload, columns)

    # ---------- 对外 API ----------
    def invoke(self, state: T) -> Dict[str, Any]:
        # 2. 无 LLM 分支
        if self.type == "PGM":
            result = self.execute_process(self.process, state)
            out = self._build_output_dict(result, state)
            #self._persistence("", state["doc_id"], out)
            return out

        if self.type=="LLM":
            # 3. 构造 LLM 输入（只给 llm_inputs 里出现的字段）
            base_dict = {k: state[k] for k in self.inputs if k in state}
            prompt_value = self.template.invoke(base_dict)
            ai_msg = self.model.invoke(prompt_value)
            if ai_msg and hasattr(ai_msg, 'content'):
                result = ai_msg.content
                out = self._build_output_dict(result, state)
                # self._persistence(state["doc"], state["doc_id"], out)
                return out
        return {}

    def stream(self, state: T,**kwargs) -> Iterator[dict[str, Any] | Any]:
        """
        流式运行 LLM：返回一个 Python generator，
        每次 yield 一段 chunk，用于 Flask SSE 或 chunked response。
        """
        _jsonify_state(state)
        # ---------- 探针结束 ----------
        if self.type=="PGM":
            result = self.invoke(state)
            # 一次性 yield 整块 JSON，调用方按需要解析
            yield json.dumps(result, ensure_ascii=False) + '\n'
            return

        if self.type=="LLM":
            # ---------- 3. 构造 LLM prompt ----------
            base_dict = {k: state[k] for k in self.inputs if k in state}
            prompt_value = self.template.invoke(base_dict)
            # ---------- 5. 逐 chunk 推流 ----------
            try:
                if self.tools:
                    config=kwargs.get("config")
                    for chunk in self.agent.stream(prompt_value,config=config):
                        if isinstance(chunk, dict):
                            if 'model' in chunk and 'messages' in chunk['model']:
                                message = chunk['model']['messages'][-1]
                                if isinstance(message, AIMessage):
                                    yield f"{message.content}\n"
                else:
                    for chunk in self.model.stream(prompt_value):
                        yield f"{chunk.content}\n"
            except Exception as e:
                    yield f"[Stream Error] {str(e)}\n"
                    return

    def execute_process(self, code_string: str, state: dict) -> dict:
        """安全地执行代码（处理缩进问题）"""
        try:
            # 1. 清理代码字符串的缩进
            def normalize_indent(code):
                """标准化代码缩进"""
                lines = code.split('\n')
                if not lines:
                    return code

                # 找到第一行的缩进
                first_line = lines[0]
                initial_indent = len(first_line) - len(first_line.lstrip())

                # 清理每一行的缩进
                cleaned_lines = []
                for line in lines:
                    # 移除与第一行相同的缩进
                    if line.startswith(' ' * initial_indent):
                        line = line[initial_indent:]
                    cleaned_lines.append(line)

                return '\n'.join(cleaned_lines)

            # 清理代码
            cleaned_code = normalize_indent(code_string)

            # 2. 安全的内置函数
            safe_builtins = {
                'range': range, 'len': len, 'str': str, 'int': int,
                'float': float, 'bool': bool, 'list': list, 'dict': dict,
                'set': set, 'tuple': tuple, 'enumerate': enumerate,
                'zip': zip, 'max': max, 'min': min, 'sum': sum,
                'abs': abs, 'round': round, 'sorted': sorted,
                'isinstance':isinstance
            }

            def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
                allowed = {
                    'flair',
                    'flair.data'
                }
                if name not in allowed:
                    raise ImportError(f"Import {name} not allowed")
                return __import__(name, globals, locals, fromlist, level)

            safe_builtins['__import__'] = safe_import
            # 3. 创建执行环境
            exec_globals = {
                '__builtins__': safe_builtins,
                'state': state,
                '__result__': None,
                'get_plugin': get_plugin
            }
            # 4. 直接执行清理后的代码
            exec(cleaned_code, exec_globals)
            # 5. 获取结果
            if '__result__' in exec_globals and exec_globals['__result__'] is not None:
                return exec_globals['__result__']
            else:
                return state


        except IndentationError as e:
            state['error'] = f"Indentation error: {str(e)}"
            return state
        except Exception as e:
            state['error'] = f"Execution error: {str(e)}"
            return state


    async def astream_events(self,input, config):
        prompt_value = self.template.invoke(input)
        return self.agent.astream_events(prompt_value, config=config)



    def get_state(self, config):
        original_state  = self.agent.get_state(config)
        if not original_state or not original_state.values:
            return None
        from langgraph.checkpoint.base import CheckpointMetadata

        @dataclass(slots=True)
        class State:
            values: str
            created_at: str
            next: tuple
            metadata:  CheckpointMetadata

        state=State
        state.created_at=original_state.created_at
        state.next=original_state.next

        messages = original_state.values
        state.metadata=original_state.metadata

        # 遍历 messages 列表，找到所有 AIMessage 并更新 content
        for  message in messages['messages']:
            if isinstance(message, AIMessage):
                state.values = message.content
                return state
        return state



    def get_state_history(self,config):
        return self.agent.get_state_history(config)


class AgentLoader(EntityLoader):

    @staticmethod
    def load(id: str,**extra_params) -> AgentEntity | None:
        checkpointer: Checkpointer = extra_params.get("checkpointer")
        meta=MetaLoader.load("agents",id)
        if meta:
            return AgentEntity(meta, checkpointer=checkpointer)
        return None

