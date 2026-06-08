from logging import getLogger
try:
    from langgraph.types import Checkpointer
except ImportError:
    Checkpointer = None
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain.agents import create_agent
from langchain.messages import AIMessage
from pathlib import Path
import json
import csv
import re
from typing_extensions import get_type_hints
from typing import Dict, Any, List, get_type_hints, Iterator
from service.entity.tool import ToolLoader
from utils.conversion import (
    convert_to_list,
    parse_entity_list,
    parse_hypernym_list,
    parse_plan_json,
    parse_relation_triples,
    T,
    jsonify_state,
)
from service.entity.entity import Entity, EntityLoader
from service.meta.loader import MetaLoader
from service.meta.agent_version import AgentVersionStore
from utils.graphutils import create_graph
from plugin.plugin_loader import get_plugin
from plugin.plugin_client import is_available, run_pgm, sandbox_enabled
from plugin.sandbox_manifest import resolve_sandbox
from dataclasses import dataclass


logger = getLogger(__name__)


def _escape_json_literal_braces(text: str) -> str:
    """
    Escape JSON literal braces in prompt templates so ChatPromptTemplate
    does not treat keys like {"evidence_sentence": ...} as variables.
    Keep normal placeholders such as {text}/{head}/{tail} unchanged.
    """
    if not isinstance(text, str) or "{" not in text:
        return text
    # opening brace before a quoted key: {"key": ...} -> {{"key": ...}
    text = re.sub(r'(?<!\{)\{(?=\s*")', "{{", text)
    # closing brace after a quoted value/key segment -> ..."} -> ..."}}
    text = re.sub(r'(?<=")\}(?!\})', "}}", text)
    return text


def _llm_extra_body(llm_info: dict) -> dict | None:
    """OpenAI-compatible extra_body (e.g. disable Kimi thinking / reasoning)."""
    extra = dict(llm_info.get("extra_body") or {})
    meta = llm_info.get("metadata") or {}
    if isinstance(meta.get("extra_body"), dict):
        extra = {**meta["extra_body"], **extra}
    model_name = (llm_info.get("model") or "").lower()
    base_url = (llm_info.get("base_url") or "").lower()
    if "moonshot" in base_url or "kimi" in model_name:
        thinking = extra.get("thinking") if isinstance(extra.get("thinking"), dict) else {}
        if thinking.get("type") != "enabled":
            extra["thinking"] = {"type": "disabled"}
    return extra or None


def _build_chat_openai(llm_info: dict) -> ChatOpenAI:
    kwargs: dict = {
        "model": llm_info["model"],
        "base_url": llm_info["base_url"],
        "api_key": llm_info["api_key"],
        "temperature": llm_info.get("temperature", 0),
    }
    if llm_info.get("max_tokens") is not None:
        kwargs["max_tokens"] = llm_info["max_tokens"]
    extra_body = _llm_extra_body(llm_info)
    if extra_body:
        kwargs["extra_body"] = extra_body
    return ChatOpenAI(**kwargs)


def _message_content_to_str(content: Any) -> str:
    """Normalize AIMessage.content (str or multimodal blocks) for SSE."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                parts.append(
                    str(block.get("text") or block.get("content") or block)
                )
            else:
                parts.append(str(block))
        return "".join(parts)
    return str(content)


def _extract_agent_stream_text(chunk: Any) -> str:
    """Pull displayable text from LangGraph/LangChain agent stream chunks."""
    if isinstance(chunk, str):
        return chunk
    if isinstance(chunk, tuple) and len(chunk) == 2:
        chunk = chunk[1]
    if not isinstance(chunk, dict):
        return ""
    for node_key in ("model", "agent", "tools"):
        block = chunk.get(node_key)
        if not isinstance(block, dict):
            continue
        messages = block.get("messages") or []
        if not messages:
            continue
        msg = messages[-1]
        if isinstance(msg, AIMessage):
            return _message_content_to_str(msg.content)
        if hasattr(msg, "content"):
            return _message_content_to_str(getattr(msg, "content", ""))
    return ""


def _strip_reasoning_from_messages(messages: list) -> list:
    """Remove Kimi reasoning_content from history so follow-up calls do not 400."""
    cleaned = []
    for msg in messages:
        if isinstance(msg, AIMessage):
            ak = dict(getattr(msg, "additional_kwargs", None) or {})
            ak.pop("reasoning_content", None)
            rc = getattr(msg, "response_metadata", None) or {}
            if isinstance(rc, dict) and "reasoning_content" in rc:
                rc = {k: v for k, v in rc.items() if k != "reasoning_content"}
            cleaned.append(
                AIMessage(
                    content=msg.content,
                    additional_kwargs=ak,
                    tool_calls=getattr(msg, "tool_calls", None) or [],
                    id=getattr(msg, "id", None),
                    response_metadata=rc if rc else {},
                )
            )
        else:
            cleaned.append(msg)
    return cleaned


class AgentEntity(Entity):
    def __init__(self,  meta: Dict[str, Any], checkpointer: Checkpointer = None):
        super().__init__(meta,checkpointer)
        self.template = None
        self.id = meta.get("id")
        self.name=meta.get("name", "").strip()
        self.type: str | None = meta.get("type").strip()
        self.template_name = meta.get("prompt_template", {})  # 默认为空字符串
        self.inputs: List[str] = meta.get("inputs", [])
        self.persistence: Dict[str, Any] = meta.get("persistence") or {}
        self.outputs: Dict[str, str] = meta.get("outputs", {})

        self.idx: str | None = meta.get("idx")
        self.engine: str | None = (meta.get("engine") or "").strip() or None
        self.sandbox: str | None = meta.get("sandbox")
        self.process = meta.get("process", None)
        self.meta = meta
        self.default_labels = meta.get("default_labels")
        if self.type=="PGM":
            self.agent = create_graph(self,self.checkpointer)
        if self.type == "LLM":
            # 获取 llm_url 和 model，如果不存在则提供默认值或处理逻辑
            llm_model_id = meta.get("model", "").strip()  # 默认为空字符串
            llm_info = MetaLoader.load("llms",llm_model_id)
            if llm_info is None:
                raise ValueError(f"LLM config '{llm_model_id}' not found for agent '{self.id}'")
            llm_type = llm_info.get('type', '')
            if llm_type=='ollama':
                self.model= ChatOllama(
                    model=llm_info['model'],  # ollama list 里看到的模型名
                    base_url=llm_info['base_url'],  # 注意带 /v1
                    temperature=llm_info['temperature'],
                )
            elif llm_type in ('custom', 'openai'):
                self.model = _build_chat_openai(llm_info)
            else:
                raise ValueError(f"Unknown LLM type '{llm_type}' for agent '{self.id}'")

            system_prompt = _escape_json_literal_braces(self.template_name["system"])
            human_prompt = _escape_json_literal_braces(self.template_name["human"])
            self.template = ChatPromptTemplate(
                [("system", system_prompt),
                 ("human", human_prompt)]
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
        out = {}
        for k in self.inputs:
            if k not in state:
                continue
            v = state[k]
            if isinstance(v, (dict, list)):
                out[k] = json.dumps(v, ensure_ascii=False)
            else:
                out[k] = v
        return out

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
        typ = self.outputs.get("type", "str").lower()
        parse_as = self.outputs.get("parse_as") or self.meta.get("output_parse")
        if self.type=='LLM':
            if typ == "list":
                parse_as = (
                    parse_as
                    or ("entity_list" if name in ("filtered_entities", "entities") else None)
                )
                if parse_as == "entity_list":
                    parsed = parse_entity_list(result)
                    if not parsed and isinstance(state, dict):
                        parsed = parse_entity_list(state.get("entities"))
                    return {name: parsed}
                if parse_as == "hypernym_list":
                    parsed = parse_hypernym_list(result)
                    return {name: parsed}
                if name == "hypernyms":
                    parsed = parse_hypernym_list(result)
                    if parsed:
                        return {name: parsed}
                if parse_as == "relation_triples" or name == "triples":
                    parsed = parse_relation_triples(result)
                    return {name: parsed}
                if isinstance(result, list):
                    if result and all(isinstance(x, dict) for x in result):
                        parsed = parse_entity_list(result)
                        if parsed:
                            return {name: parsed}
                    return {name: result}
                return {name: convert_to_list(result)}
            if name == "plan_json" or parse_as == "plan_json":
                parsed = parse_plan_json(result)
                return {name: json.dumps(parsed, ensure_ascii=False)}
            if typ == "dict" and isinstance(result, str):
                try:
                    import ast
                    parsed = json.loads(result.strip())
                except json.JSONDecodeError:
                    try:
                        parsed = ast.literal_eval(result.strip())
                    except (SyntaxError, ValueError):
                        parsed = result
                return {name: parsed}
            if name == "synonyms" and isinstance(result, str):
                text = result.strip()
                if not text:
                    return {name: text}
                return {name: text}
            return {name: result}
        elif self.type == "PGM":
            if isinstance(result, dict) and "error" in result:
                if typ == "list":
                    return {name: []}
                if typ == "dict":
                    return {name: {}}
                return {name: None}
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
    def invoke(self, state: T, **kwargs) -> Dict[str, Any]:
        config = kwargs.get("config")
        if isinstance(state, dict):
            state = jsonify_state(dict(state))
        # 2. 无 LLM 分支
        if self.type == "PGM":
            result = self.execute_process(self.process, state)
            out = self._build_output_dict(result, state)
            if isinstance(state, dict) and state.get("error") and "error" not in out:
                out["error"] = state["error"]
            #self._persistence("", state["doc_id"], out)
            return out

        if self.type=="LLM":
            base_dict = {k: state[k] for k in self.inputs if k in state}
            if "labels" in self.inputs and "labels" not in base_dict:
                default_labels = getattr(self, "default_labels", None) or (
                    (self.meta or {}).get("default_labels")
                )
                if default_labels:
                    base_dict["labels"] = default_labels
            prompt_value = self.template.invoke(base_dict)
            if self.tools:
                messages = _strip_reasoning_from_messages(prompt_value.to_messages())
                if config:
                    agent_out = self.agent.invoke({"messages": messages}, config=config)
                else:
                    agent_out = self.agent.invoke({"messages": messages})
                out_messages = agent_out.get("messages", []) if isinstance(agent_out, dict) else []
                ai_msg = next(
                    (m for m in reversed(out_messages) if isinstance(m, AIMessage)),
                    None,
                )
                result = ai_msg.content if ai_msg else ""
            else:
                ai_msg = self.model.invoke(prompt_value)
                result = ai_msg.content if ai_msg and hasattr(ai_msg, "content") else ""
            return self._build_output_dict(result, state)
        return {}


    def stream(self, state: T,**kwargs) -> Iterator[dict[str, Any] | Any]:
        """
        流式运行 LLM：返回一个 Python generator，
        每次 yield 一段 chunk，用于 Flask SSE 或 chunked response。
        """
        state=jsonify_state(state)
        # ---------- 探针结束 ----------
        if self.type == "PGM":
            result = self.invoke(state)
            # 一次性 yield 整块 JSON，调用方按需要解析
            yield json.dumps(result, ensure_ascii=False) + '\n'
            return

        if self.type=="LLM":
            base_dict = {k: state[k] for k in self.inputs if k in state}
            if "labels" in self.inputs and "labels" not in base_dict:
                default_labels = getattr(self, "default_labels", None) or (
                    (self.meta or {}).get("default_labels")
                )
                if default_labels:
                    base_dict["labels"] = default_labels
            prompt_value = self.template.invoke(base_dict)
            # ---------- 5. 逐 chunk 推流 ----------
            try:
                emitted = False
                if self.tools:
                    config = kwargs.get("config")
                    messages = _strip_reasoning_from_messages(prompt_value.to_messages())
                    for chunk in self.agent.stream({"messages": messages}, config=config):
                        text = _extract_agent_stream_text(chunk)
                        if text:
                            emitted = True
                            yield f"{text}\n"
                else:
                    for chunk in self.model.stream(prompt_value):
                        text = _message_content_to_str(
                            getattr(chunk, "content", chunk)
                        )
                        if text:
                            emitted = True
                            yield f"{text}\n"
                if not emitted:
                    result = self.invoke(state, config=kwargs.get("config"))
                    out_name = (self.outputs or {}).get("name")
                    payload = result.get(out_name) if out_name and isinstance(result, dict) else result
                    if payload is None and isinstance(result, dict):
                        payload = {k: v for k, v in result.items() if k not in state}
                    if isinstance(payload, (dict, list)):
                        yield json.dumps(payload, ensure_ascii=False) + "\n"
                    elif payload is not None:
                        yield f"{payload}\n"
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
            agent_meta = {"sandbox": self.sandbox, "engine": self.engine}
            sandbox_id = resolve_sandbox(
                cleaned_code, meta=agent_meta, engine=self.engine
            )
            if sandbox_enabled() and sandbox_id:
                if not is_available(sandbox_id, force_check=True):
                    state = dict(state)
                    state["error"] = (
                        f"Plugin sandbox '{sandbox_id}' is not running. "
                        f"Run: .\\sandbox\\setup_venv.ps1 -Name {sandbox_id} then .\\start.ps1"
                    )
                    return state
                try:
                    from plugin.plugin_client import run_pgm

                    return run_pgm(cleaned_code, state, sandbox_id)
                except Exception as e:
                    state = dict(state)
                    state["error"] = f"Sandbox execution error: {str(e)}"
                    return state

            exec_globals = get_plugin("exec_globals")
            if not exec_globals:
                state = dict(state)
                state["error"] = "exec_globals not available (enable PLUGIN_SANDBOX or PLUGIN_SANDBOX=0)"
                return state
            exec_globals = dict(exec_globals)
            exec_globals["__result__"] = None
            exec_globals["state"] = state
            exec_globals["get_plugin"] = get_plugin
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


    async def astream_events(self,inputs, config):
        if self.type=="LLM":
            values = self.template.invoke(inputs)
        else:
            values = inputs
        return self.agent.astream_events(values, config=config)


    def get_state(self, config):
        original_state  = self.agent.get_state(config)
        if not original_state or not original_state.values:
            return None
        try:
            from langgraph.checkpoint.base import CheckpointMetadata
        except ImportError:
            CheckpointMetadata = dict

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
        if 'messages' in messages:
            # 遍历 messages 列表，找到所有 AIMessage 并更新 content
            for  message in messages['messages']:
                if isinstance(message, AIMessage):
                    state.values = message.content
                    return state
        else:
            state.values=messages

        return state



    def get_state_history(self,config):
        return self.agent.get_state_history(config)


class AgentLoader(EntityLoader):
    _version_store = AgentVersionStore()

    @staticmethod
    def load(id: str,**extra_params) -> AgentEntity | None:
        checkpointer: Checkpointer = extra_params.get("checkpointer")
        meta=MetaLoader.load("agents",id)
        if meta:
            return AgentEntity(meta, checkpointer=checkpointer)
        return None

    @staticmethod
    def load_version(id: str, version: str, **extra_params) -> AgentEntity | None:
        """Load a historical agent version snapshot as an executable AgentEntity."""
        checkpointer: Checkpointer = extra_params.get("checkpointer")
        payload = AgentLoader._version_store.load_version(id, version)
        if not payload:
            return None
        content = payload.get("content") or {}
        if not isinstance(content, dict):
            return None
        # keep runtime id aligned with agent filename id
        content = dict(content)
        content["id"] = id
        return AgentEntity(content, checkpointer=checkpointer)

