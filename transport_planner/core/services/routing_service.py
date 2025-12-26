
from abc import ABC, abstractmethod
import requests
from django.conf import settings
import time

class BaseRoutingService(ABC):
    """Абстрактный класс для всех сервисов маршрутизации"""
    @abstractmethod
    def get_routes(self, start_lat: float, start_lon: float, end_lat: float, end_lon: float):
        pass


class StubRoutingService(BaseRoutingService):
    """Заглушка. Возвращает фиктивные маршруты в формате, похожем на 2GIS API."""
    
    def get_routes(self, start_lat, start_lon, end_lat, end_lon):
        
        import time
        time.sleep(0.5)

       
        stub_response = {
            "result": [
                {
                    "id": "route_1",
                    "total_time": 25,
                    "total_distance": 5400,
                    "segments": [
                        {
                            "type": "walk",
                            "time": 5,
                            "details": {"text": f"от ({start_lat:.5f}, {start_lon:.5f})"}
                        },
                        {
                            "type": "transport",
                            "time": 15,
                            "details": {
                                "route_name": "Автобус 21",
                                "stops": ["Цирк", "Гринвич"],
                                "transport_type": "bus"
                            }
                        },
                        {
                            "type": "walk",
                            "time": 5,
                            "details": {"text": f"до ({end_lat:.5f}, {end_lon:.5f})"}
                        }
                    ]
                }
            ],
            "source": "stub"
        }
        return stub_response


class TomTomRoutingService(BaseRoutingService):
    """Реальный сервис маршрутизации через TomTom API"""
    
    def __init__(self, api_key, travel_mode='car'):
        self.api_key = api_key
        # 'car', 'pedestrian', 'bicycle', 'truck'
        self.travel_mode = travel_mode
    
    def get_routes(self, start_lat, start_lon, end_lat, end_lon):
        print(f"[DEBUG TOMTOM] Вызван с параметрами: mode={self.travel_mode}, coords=({start_lat},{start_lon})->({end_lat},{end_lon})")
        try:
            locations = f"{start_lat},{start_lon}:{end_lat},{end_lon}"
            url = f"https://api.tomtom.com/routing/1/calculateRoute/{locations}/json"
            
            params = {
                'key': self.api_key,
                'traffic': 'true' if self.travel_mode == 'car' else 'false', # Пробки только для авто
                'travelMode': self.travel_mode, # Ключевой параметр!
                'routeType': 'fastest',
                'instructionsType': 'text'
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            api_data = response.json()
            
            # Передаем travel_mode для корректного парсинга
            return self._parse_tomtom_response(api_data, self.travel_mode)
            
        except requests.exceptions.RequestException as e:
            print(f"Ошибка TomTom Routing API: {e}")
            raise Exception(f"TomTom Routing API недоступен: {e}")

    def _parse_tomtom_response(self, api_data, travel_mode):
        """Преобразует ответ TomTom API в наш формат с учетом типа маршрута"""
        print(f"[DEBUG TOMTOM RESPONSE] Сырой ответ API для режима '{travel_mode}': {api_data}")
        parsed_response = {
            "result": [],
            "source": "tomtom",
            "travel_mode": travel_mode  # Добавляем информацию о типе маршрута
        }
        
        if 'routes' in api_data and len(api_data['routes']) > 0:
            route = api_data['routes'][0]
            summary = route['summary']
            
            travel_time = summary.get('travelTimeInSeconds', 0)
            traffic_delay = summary.get('trafficDelayInSeconds', 0) if travel_mode == 'car' else 0
            total_time_seconds = travel_time + traffic_delay
            total_time_minutes = total_time_seconds // 60
            
            # Настройка отображения в зависимости от типа маршрута
            mode_info = {
                'car': {'icon': '🚗', 'name': 'Автомобиль', 'segment_type': 'transport'},
                'pedestrian': {'icon': '🚶', 'name': 'Пешком', 'segment_type': 'walk'},
                'bicycle': {'icon': '🚲', 'name': 'Велосипед', 'segment_type': 'transport'}
            }
            info = mode_info.get(travel_mode, mode_info['car'])
            
            route_data = {
                "id": f"tomtom_{travel_mode}_route",
                "total_time": total_time_minutes,
                "total_distance": summary.get('lengthInMeters', 0),
                "travel_mode": travel_mode,
                "icon": info['icon'],
                "segments": []  # TomTom не делит маршрут на сегменты как 2GIS
            }
            
            # Создаем один основной сегмент
            segment_details = {
                "route_name": f"Маршрут на {info['name'].lower()}",
                "distance": f"{summary.get('lengthInMeters', 0) / 1000:.1f} км",
                "note": "Построено с учетом карт TomTom"
            }
            
            if travel_mode == 'car' and traffic_delay > 0:
                segment_details["traffic_info"] = f"Пробки: +{traffic_delay // 60} мин"
            
            route_data["segments"].append({
                "type": info['segment_type'],  # 'walk' или 'transport'
                "time": total_time_minutes,
                "details": segment_details
            })
            
            # Для пеших маршрутов добавляем информацию о пешеходной доступности
            if travel_mode == 'pedestrian':
                route_data["pedestrian_friendly"] = True
                route_data["segments"][0]["details"]["note"] = "Пешеходный маршрут, учтены тротуары и переходы"
            
            parsed_response["result"].append(route_data)
        
        return parsed_response

def create_tomtom_service(api_key, mode='car'):
    """Фабрика для создания TomTom сервиса с нужным режимом передвижения"""
    mode = mode.lower()
    valid_modes = ['car', 'pedestrian', 'bicycle', 'truck']
    
    if mode not in valid_modes:
        mode = 'car'  # fallback
    
    return TomTomRoutingService(api_key=api_key, travel_mode=mode)

class TwoGisRoutingService(BaseRoutingService):
    """Сервис маршрутизации через 2GIS API (оставляем заглушкой)"""
    
    def __init__(self, api_key):
        self.api_key = api_key
    
    def get_routes(self, start_lat, start_lon, end_lat, end_lon):
        # Здесь будет реальная реализация 2GIS API
        # Пока оставляем заглушку
        stub_service = StubRoutingService()
        return stub_service.get_routes(start_lat, start_lon, end_lat, end_lon)