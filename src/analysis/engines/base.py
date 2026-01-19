from abc import ABC, abstractmethod

from ...models.tables import LoveDailyRef


class BaseMetricEngine(ABC):
    @abstractmethod
    def calculate(self, data: LoveDailyRef) -> float:
        """计算原始分值"""
        pass
