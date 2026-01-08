import json
from abc import ABC, abstractmethod
import requests
from django.conf import settings
import time
import logging

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
    def __init__(self, api_key, travel_mode='car'):
        self.api_key = api_key
        self.default_travel_mode = travel_mode
        self.logger = logging.getLogger(__name__)
    def get_routes(self, start_lat: float, start_lon: float, end_lat: float, end_lon: float, **kwargs):
        travel_mode = kwargs.get('travel_mode', self.default_travel_mode).lower()
        mode_to_tomtom = {
            'car': 'car',
            'pedestrian': 'pedestrian',
            'bicycle': 'bicycle'
        }
        tomtom_travel_mode = mode_to_tomtom.get(travel_mode, 'car')

        self.logger.info(f"[TomTom] Расчет маршрута для режима: {travel_mode} (TomTom: {tomtom_travel_mode})")

        try:
            locations = f"{start_lat},{start_lon}:{end_lat},{end_lon}"
            url = f"https://api.tomtom.com/routing/1/calculateRoute/{locations}/json"

            params = {
                'key': self.api_key,
                'travelMode': tomtom_travel_mode, 
                'routeType': 'fastest',
                'traffic': 'true' if travel_mode == 'car' else 'false',  
                'instructionsType': 'text',
                'language': 'ru-RU',
            }

            
            if travel_mode in ['pedestrian', 'bicycle']:
                params['avoid'] = 'motorways'  

            response = requests.get(url, params=params)
            response.raise_for_status()
            api_data = response.json()
            return self._parse_tomtom_response(api_data, travel_mode)  

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Ошибка TomTom Routing API: {e}")
            raise Exception(f"TomTom Routing API недоступен: {e}")
    def _parse_tomtom_response(self, api_data, travel_mode):
        """Преобразует ответ TomTom API в наш формат."""
        parsed_response = {"result": [], "source": "tomtom"}

        if 'routes' in api_data and api_data['routes']:
            route = api_data['routes'][0]
            summary = route.get('summary', {})
            guidance = route.get('guidance', {})
            route_coordinates = []
            for leg in route.get('legs', []):
                leg_points = [[point.get('latitude'), point.get('longitude')] for point in leg.get('points', [])]
                if leg_points:
                    route_coordinates.append(leg_points)

            mode_info = {
                'car': {'icon': '🚗', 'display': 'На машине', 'type': 'transport'},
                'pedestrian': {'icon': '🚶', 'display': 'Пешком', 'type': 'walk'},
                'bicycle': {'icon': '🚲', 'display': 'На велосипеде', 'type': 'transport'}
            }
            info = mode_info.get(travel_mode, mode_info['car'])
            travel_time = summary.get('travelTimeInSeconds', 0) // 60
            traffic_delay = summary.get('trafficDelayInSeconds', 0) // 60 if travel_mode == 'car' else 0
            total_time = travel_time + traffic_delay
            instructions_list = []
            if guidance and 'instructions' in guidance:
                for step in guidance['instructions']:
                    instruction_text = step.get('message', '')  
                    point_index = step.get('pointIndex')  
                    instructions_list.append({
                        'text': instruction_text,
                        'index': point_index
                    })
            segments = []
            for instr in instructions_list:
                segments.append({
                    "type": "instruction",
                    "time": 0, 
                    "details": {
                        "text": instr['text'],
                        "direction": "Следуйте инструкции",
                        "street": "", 
                        "distance": "" 
                    }
                })

            route_data = {
                "id": f"tomtom_{travel_mode}_route",
                "total_time": total_time,
                "total_distance": summary.get('lengthInMeters', 0),
                "travel_mode": travel_mode,
                "icon": info['icon'],
                "mode_display": info['display'],
                "traffic_delay": traffic_delay,
                "coordinates": route_coordinates,
                "segments": segments,  
                "instructions": instructions_list 
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