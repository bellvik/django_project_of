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
        # Вместо сложной логики просто маппинг выбора пользователя
        # Это значение будет передано из формы
        level_map = {
            'light': 1.0,
            'medium': 1.3,
            'heavy': 1.7
        }
        # По умолчанию возвращаем средний коэффициент
        return level_map.get(point, 1.3)