from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..core.platform import PlatformManager


class BaseManager(ABC):
    def __init__(self, platform: "PlatformManager") -> None:
        self.platform = platform

    @abstractmethod
    def execute(self, *args: Any, **kwargs: Any) -> Any:
        pass
