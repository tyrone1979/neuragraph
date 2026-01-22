#service/result/loader.py
from pathlib import Path
from typing import Dict, Any
import json
from logging import getLogger
logger = getLogger(__name__)


def _get_path(name):
    path = Path(__file__).resolve().parent.parent.parent / "result" / name
    path.mkdir(parents=True, exist_ok=True)
    return path


class ResultLoader:
    @staticmethod
    def load(id:str) -> Dict[str, Any] | None:
        try:
            path=_get_path(id)
            cfg_path = path  / "states.json"
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            # 确保配置中有id字段
            cfg["id"] = id
            return cfg
        except FileNotFoundError as e:
            logger.error(e)
            return None
