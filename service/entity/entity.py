from logging import getLogger
from typing import Dict, Any, TypedDict, TypeVar, Iterator
from langgraph.types import Checkpointer
T = TypeVar("T", bound=TypedDict)
logger = getLogger(__name__)

class Entity:
    def __init__(self, meta: Dict[str, Any],
                 checkpointer: Checkpointer = None):
        self.metadata= meta
        self.checkpointer = checkpointer


    @classmethod
    def invoke(self, state: T) -> Dict[str, Any]:
        pass

    @classmethod
    async def ainvoke(self, state: T,**kwargs):
        pass

    @classmethod
    def stream(self, state: T,**kwargs) -> Iterator[dict[str, Any] | Any]:
        pass

    @classmethod
    def astream_events(self, input, config):
        pass

    @classmethod
    def get_state(self, config):
        pass

    @classmethod
    def get_state_history(self, config):
        pass

class EntityLoader:

    @staticmethod
    def load(id:str,**extra_params) -> Entity:
        pass

    @staticmethod
    def loads() -> Dict[str,Entity]:
        pass

