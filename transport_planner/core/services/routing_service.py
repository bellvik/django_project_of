import json
from abc import ABC, abstractmethod
import requests
from django.conf import settings
import time

class BaseRoutingService(ABC):
    """Абстрактный класс для всех сервисов маршрутизации"""
    @abstractmethod
    def get_routes(self, start_lat: float, start_lon: float, 
                   end_lat: float, end_lon: float, **kwargs):
        pass


class StubRoutingService(BaseRoutingService):
    """Заглушка. Возвращает фиктивные маршруты."""
    
    def get_routes(self, start_lat, start_lon, end_lat, end_lon, **kwargs):
        import time
        time.sleep(0.5)
        travel_mode = kwargs.get('travel_mode', 'car')
        transport_types = kwargs.get('transport_types', ['bus'])
        max_transfers = kwargs.get('max_transfers')
        only_direct = kwargs.get('only_direct', False)
        if travel_mode == 'pedestrian':
            total_time = 40
        elif travel_mode == 'bicycle':
            total_time = 20
        elif travel_mode == 'car':
            total_time = 15
        else:  
            total_time = 30
        
        stub_response = {
            "result": [
                {
                    "id": "stub_route_1",
                    "total_time": total_time,
                    "total_distance": 5400,
                    "travel_mode": travel_mode,
                    "transport_types": transport_types,
                    "transfer_count": 0 if only_direct else 1,
                    "mode_display": "Заглушка",
                    "icon": "🚗" if travel_mode == 'car' else "🚌",
                    "segments": [
                        {
                            "type": "walk",
                            "time": 5,
                            "details": {"text": f"от ({start_lat:.5f}, {start_lon:.5f})"}
                        },
                        {
                            "type": "transport",
                            "time": total_time - 10,
                            "details": {
                                "route_name": f"Маршрут {'без пересадок' if only_direct else 'с 1 пересадкой'}",
                                "transport_type": transport_types[0] if transport_types else 'bus',
                                "transport_name": "Автобус",
                                "stops": ["Цирк", "Гринвич"]
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
        self.default_travel_mode = travel_mode
    def _get_mode_icon(self, mode):
        icons = {'car': '🚗', 'pedestrian': '🚶', 'bicycle': '🚲'}
        return icons.get(mode, '📍')
    
    def _get_mode_name(self, mode):
        names = {'car': 'автомобиле', 'pedestrian': 'пешком', 'bicycle': 'велосипеде'}
        return names.get(mode, 'транспорте')
    
    def get_routes(self, start_lat: float, start_lon: float, 
                   end_lat: float, end_lon: float, **kwargs):
        travel_mode = kwargs.get('travel_mode', self.default_travel_mode)
        
        print(f"[DEBUG TOMTOM] Вызван с параметрами: mode={travel_mode}, coords=({start_lat},{start_lon})->({end_lat},{end_lon})")
        print(f"[DEBUG TOMTOM] Дополнительные параметры: {kwargs}")
        
        try:
            locations = f"{start_lat},{start_lon}:{end_lat},{end_lon}"
            url = f"https://api.tomtom.com/routing/1/calculateRoute/{locations}/json"
            
            params = {
                'key': self.api_key,
                'traffic': 'true' if travel_mode == 'car' else 'false',
                'travelMode': travel_mode, 
                'routeType': 'fastest',
                'instructionsType': 'text',
                'language': 'ru-RU',
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            api_data = response.json()
            return self._parse_tomtom_response(api_data, travel_mode)
            
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
    """Сервис маршрутизации через 2GIS API для автомобильных маршрутов"""
    
    def __init__(self, api_key=None):
        self.api_key = api_key or getattr(settings, 'TWOGIS_ROUTING_API_KEY', '')
    
    def get_routes(self, start_lat, start_lon, end_lat, end_lon, **kwargs):
        """
        Получение автомобильных маршрутов через 2GIS API.
        Пока это заглушка, но может быть расширена до реального API.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        travel_mode = kwargs.get('travel_mode', 'car')
        if travel_mode != 'car':
            logger.warning(f"TwoGisRoutingService не поддерживает режим '{travel_mode}', используем 'car'")
            travel_mode = 'car'
        
        logger.info(f"TwoGisRoutingService: автомобильный маршрут от ({start_lat}, {start_lon}) до ({end_lat}, {end_lon})")
        if self.api_key and len(self.api_key) > 10:
            logger.debug("Ключ 2GIS Routing API найден, но используем заглушку")
            return self._get_stub_routes(start_lat, start_lon, end_lat, end_lon)
        else:
            logger.debug("2GIS Routing API ключ не настроен, используем заглушку")
            return self._get_stub_routes(start_lat, start_lon, end_lat, end_lon)
    
    def _get_stub_routes(self, start_lat, start_lon, end_lat, end_lon):
        """Заглушка для 2GIS Routing API"""
        import time
        time.sleep(0.2)  

        coordinates = []
        num_points = 15
        for i in range(num_points + 1):
            ratio = i / num_points
            lat = start_lat + (end_lat - start_lat) * ratio
            lon = start_lon + (end_lon - start_lon) * ratio

            import random
            lat += random.uniform(-0.002, 0.002)
            lon += random.uniform(-0.002, 0.002)
            coordinates.append([lat, lon])
        

        import math
        distance = int(math.sqrt((end_lat - start_lat)**2 + (end_lon - start_lon)**2) * 111000)  # примерный расчет
        base_time = max(10, int(distance / 500))  
        
        traffic_delay = random.randint(5, 15)
        
        stub_response = {
            "result": [
                {
                    "id": "2gis_car_route_1",
                    "total_time": base_time + traffic_delay,
                    "total_distance": distance,
                    "travel_mode": "car",
                    "transport_types": ["car"],
                    "transfer_count": 0,
                    "crossing_count": 0,
                    "total_transfers": 0,
                    "traffic_delay": traffic_delay,
                    "mode_display": "На машине (2GIS)",
                    "icon": "🚗",
                    "coordinates": [coordinates],
                    "segments": [
                        {
                            "type": "transport",
                            "time": base_time + traffic_delay,
                            "details": {
                                "route_name": "Автомобильный маршрут",
                                "transport_type": "car",
                                "transport_name": "Автомобиль",
                                "note": f"С учётом пробок в Екатеринбурге (+{traffic_delay} мин)"
                            }
                        }
                    ],
                    "instructions": [
                        {
                            "step": 1,
                            "action": "Начните движение на автомобиле",
                            "details": "Двигайтесь по основному маршруту",
                            "time": f"{base_time + traffic_delay} мин",
                            "distance": f"{distance} м",
                            "traffic": f"Задержка из-за пробок: +{traffic_delay} мин"
                        }
                    ],
                    "source": "2gis_routing_stub"
                }
            ],
            "source": "2gis_routing_stub"
        }
        
        return stub_response
    
    def _call_real_2gis_api(self, start_lat, start_lon, end_lat, end_lon, travel_mode='car'):
        """
        Реальный вызов 2GIS Routing API.
        :param travel_mode: 'car', 'truck', 'taxi', 'bicycle', 'scooter', 'motorcycle', 'emergency', 'pedestrian'[citation:3]
        """
        if not self.api_key:
            raise Exception("Ключ 2GIS Routing API не настроен в settings.TWOGIS_ROUTING_API_KEY")

        url = "https://routing.api.2gis.com/carrouting/6.0.0/global"
        params = {'key': self.api_key}

       
        payload = {
            "points": [
                {
                    "lat": start_lat,
                    "lon": start_lon,
                    "type": "walking"  
                },
                {
                    "lat": end_lat,
                    "lon": end_lon,
                    "type": "walking"
                }
            ],
            "locale": "ru",
            "transport": travel_mode, 
            "route_mode": "fastest",  
            "traffic_mode": "jam"      
        }
        try:
            headers = {'Content-Type': 'application/json'}
            response = requests.post(url, params=params, headers=headers, 
                                     data=json.dumps(payload), timeout=10)
            response.raise_for_status()
            api_data = response.json()
            return self._parse_routing_response(api_data, travel_mode)

        except requests.exceptions.RequestException as e:
            raise Exception(f"2GIS Routing API недоступен: {e}")