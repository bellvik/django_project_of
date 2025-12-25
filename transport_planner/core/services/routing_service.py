
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
    
    def __init__(self, api_key):
        self.api_key = api_key
    
    def get_routes(self, start_lat, start_lon, end_lat, end_lon):
        try:
            
            locations = f"{start_lat},{start_lon}:{end_lat},{end_lon}"
            url = f"https://api.tomtom.com/routing/1/calculateRoute/{locations}/json"
            
            
            params = {
                'key': self.api_key,
                'traffic': 'true',
                'travelMode': 'car',
                'routeType': 'fastest',
                'vehicleMaxSpeed': 90,
                'vehicleWeight': 1600,
                'instructionsType': 'text'
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            api_data = response.json()
            return self._parse_tomtom_response(api_data, start_lat, start_lon, end_lat, end_lon)
            
        except requests.exceptions.RequestException as e:
            print(f"Ошибка TomTom Routing API: {e}")
            raise Exception(f"TomTom Routing API недоступен: {e}")
    
    def _parse_tomtom_response(self, api_data, start_lat, start_lon, end_lat, end_lon):
        """Преобразует ответ TomTom API в наш формат"""
        parsed_response = {
            "result": [],
            "source": "tomtom"
        }
        
        if 'routes' in api_data and len(api_data['routes']) > 0:
            route = api_data['routes'][0]
            summary = route['summary']
            
            
            travel_time = summary.get('travelTimeInSeconds', 0)
            traffic_delay = summary.get('trafficDelayInSeconds', 0)
            total_time_seconds = travel_time + traffic_delay
            total_time_minutes = total_time_seconds // 60
            
            
            route_data = {
                "id": "tomtom_route_1",
                "total_time": total_time_minutes,
                "total_distance": summary.get('lengthInMeters', 0),
                "traffic_delay": traffic_delay // 60,
                "travel_mode": "car",
                "segments": []
            }
            
            
            route_data["segments"].append({
                "type": "walk",
                "time": 2,  
                "details": {
                    "text": f"От точки начала до автомобиля",
                    "note": "Предполагаемое время"
                }
            })
            

            route_data["segments"].append({
                "type": "transport",
                "time": total_time_minutes - 4, 
                "details": {
                    "route_name": "Автомобильный маршрут",
                    "transport_type": "car",
                    "distance": f"{summary.get('lengthInMeters', 0) / 1000:.1f} км",
                    "traffic_info": f"Пробки: +{traffic_delay // 60} мин" if traffic_delay > 0 else "Без пробок",
                    "note": "Построено с учетом текущей ситуации на дорогах"
                }
            })
            route_data["segments"].append({
                "type": "walk",
                "time": 2,
                "details": {
                    "text": f"От автомобиля до точки назначения",
                    "note": "Предполагаемое время"
                }
            })
            
            parsed_response["result"].append(route_data)
        
        return parsed_response


class TwoGisRoutingService(BaseRoutingService):
    """Сервис маршрутизации через 2GIS API (оставляем заглушкой)"""
    
    def __init__(self, api_key):
        self.api_key = api_key
    
    def get_routes(self, start_lat, start_lon, end_lat, end_lon):
        # Здесь будет реальная реализация 2GIS API
        # Пока оставляем заглушку
        stub_service = StubRoutingService()
        return stub_service.get_routes(start_lat, start_lon, end_lat, end_lon)