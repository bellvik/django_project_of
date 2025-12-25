# core/services/traffic_service.py
from abc import ABC, abstractmethod
from datetime import datetime

class BaseTrafficService(ABC):
    @abstractmethod
    def get_traffic_coefficient(self, point: str, time: datetime):
        pass

class StubTrafficService(BaseTrafficService):
    """Заглушка. Возвращает фиксированные коэффициенты в зависимости от уровня."""
    def get_traffic_coefficient(self, point, time):

        level_map = {
            'light': 1.0,
            'medium': 1.3,
            'heavy': 1.7
        }
        return level_map.get(point, 1.3)