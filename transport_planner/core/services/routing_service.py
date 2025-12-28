
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
        self.travel_mode = travel_mode
    def _get_mode_icon(self, mode):
        icons = {'car': '🚗', 'pedestrian': '🚶', 'bicycle': '🚲'}
        return icons.get(mode, '📍')
    
    def _get_mode_name(self, mode):
        names = {'car': 'автомобиле', 'pedestrian': 'пешком', 'bicycle': 'велосипеде'}
        return names.get(mode, 'транспорте')
    
    def get_routes(self, start_lat, start_lon, end_lat, end_lon):
        print(f"[DEBUG TOMTOM] Вызван с параметрами: mode={self.travel_mode}, coords=({start_lat},{start_lon})->({end_lat},{end_lon})")
        try:
            locations = f"{start_lat},{start_lon}:{end_lat},{end_lon}"
            url = f"https://api.tomtom.com/routing/1/calculateRoute/{locations}/json"
            
            params = {
                'key': self.api_key,
                'traffic': 'true' if self.travel_mode == 'car' else 'false', # Пробки только для авто
                'travelMode': self.travel_mode, 
                'routeType': 'fastest',
                'instructionsType': 'text',
                'language': 'ru-RU',
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            api_data = response.json()
            return self._parse_tomtom_response(api_data, self.travel_mode)
            
        except requests.exceptions.RequestException as e:
            print(f"Ошибка TomTom Routing API: {e}")
            raise Exception(f"TomTom Routing API недоступен: {e}")

    def _parse_tomtom_response(self, api_data, travel_mode):
        """Преобразует ответ TomTom API в наш формат с координатами для карты."""
    
        parsed_response = {
            "result": [],
            "source": "tomtom",
            "travel_mode": travel_mode
        }

        if 'routes' in api_data and len(api_data['routes']) > 0:
            route = api_data['routes'][0]
            summary = route.get('summary', {})
            route_coordinates = []
            try:
                for leg in route.get('legs', []):
                    leg_points = []
                    for point in leg.get('points', []):
                        if 'latitude' in point and 'longitude' in point:
                            leg_points.append([point['latitude'], point['longitude']])
                    if leg_points:
                        route_coordinates.append(leg_points)
            except Exception as e:
                print(f"⚠️ Не удалось извлечь координаты из TomTom: {e}")
                route_coordinates = [[]]  
            
            
            step_by_step_instructions = []
            guidance = route.get('guidance', {})
            for instruction in guidance.get('instructions', []):
                step = {
                    'street': instruction.get('roadName', ''),
                    'direction': instruction.get('message', ''),
                    'distance': instruction.get('routeOffsetInMeters', 0),
                    'time': instruction.get('travelTimeInSeconds', 0) // 60,
                }
                if step['distance'] > 0 or step['time'] > 0:
                    step_by_step_instructions.append(step)
            
            
            travel_time = summary.get('travelTimeInSeconds', 0)
            traffic_delay = summary.get('trafficDelayInSeconds', 0) if travel_mode == 'car' else 0
            total_time_minutes = (travel_time + traffic_delay) // 60
            
            mode_icons = {'car': '🚗', 'pedestrian': '🚶', 'bicycle': '🚲'}
            mode_names = {'car': 'автомобиле', 'pedestrian': 'пешком', 'bicycle': 'велосипеде'}
            
            route_data = {
                "id": f"tomtom_{travel_mode}_route",
                "total_time": total_time_minutes,
                "total_distance": summary.get('lengthInMeters', 0),
                "travel_mode": travel_mode,
                "icon": mode_icons.get(travel_mode, '📍'),
                "traffic_delay": traffic_delay // 60,
                "coordinates": route_coordinates,  
                "instructions": step_by_step_instructions,
                "segments": [{
                    "type": "transport" if travel_mode in ['car', 'bicycle'] else 'walk',
                    "time": total_time_minutes,
                    "details": {
                        "route_name": f"Маршрут на {mode_names.get(travel_mode, 'транспорте')}",
                        "note": "Пошаговые инструкции доступны ниже."
                    }
                }]
            }
            
            parsed_response["result"].append(route_data)
        
        return parsed_response


def create_tomtom_service(api_key, mode='car'):
    """Фабрика для создания TomTom сервиса с нужным режимом передвижения"""
    mode = mode.lower()
    valid_modes = ['car', 'pedestrian', 'bicycle', 'truck']
    
    if mode not in valid_modes:
        mode = 'car'  
    
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