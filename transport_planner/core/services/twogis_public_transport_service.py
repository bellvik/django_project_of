import requests
import json
import logging
from django.conf import settings
from typing import List, Optional
from .routing_service import BaseRoutingService

logger = logging.getLogger(__name__)

class TwoGisPublicTransportService(BaseRoutingService):
    """Сервис маршрутизации через 2GIS Public Transport API"""
    
    
    TRANSPORT_TYPES = {
        'bus': {'name': 'Автобус', 'icon': '🚌'},
        'tram': {'name': 'Трамвай', 'icon': '🚋'},
        'trolleybus': {'name': 'Троллейбус', 'icon': '🚎'},
        'shuttle_bus': {'name': 'Маршрутное такси', 'icon': '🚐'},
        'subway': {'name': 'Метро', 'icon': '🚇'},
        'train': {'name': 'Электропоезд', 'icon': '🚆'},
        'funicular': {'name': 'Фуникулёр', 'icon': '🚡'},
        'monorail': {'name': 'Монорельс', 'icon': '🚝'},
        'water': {'name': 'Водный транспорт', 'icon': '⛴️'},
        'cable_car': {'name': 'Канатная дорога', 'icon': '🚠'},
        'aeroexpress': {'name': 'Аэроэкспресс', 'icon': '🚄'},
        'mcd': {'name': 'МЦД', 'icon': '🚆'},
        'mck': {'name': 'МЦК', 'icon': '🚆'}
    }
    
    def __init__(self, api_key=None):
        self.api_key = api_key or getattr(settings, 'TWOGIS_PUBLIC_TRANSPORT_API_KEY', '')
        self.base_url = getattr(settings, 'TWOGIS_PUBLIC_TRANSPORT_URL', 
                               'https://routing.api.2gis.com/public_transport/2.0')
        
        if not self.api_key:
            logger.warning("2GIS API ключ не настроен. Используйте заглушку.")
    
    def get_routes(self, start_lat: float, start_lon: float, 
                   end_lat: float, end_lon: float,
                   transport_types: Optional[List[str]] = None,
                   max_transfers: Optional[int] = None,
                   **kwargs):
        """
        Получение маршрутов общественного транспорта с фильтрацией
        
        :param transport_types: Список типов транспорта ['tram'] или ['bus', 'tram']
        :param max_transfers: Максимальное количество пересадок (transfer_count + crossing_count)
        """
        logger.info(f"2GIS API: Поиск маршрута от ({start_lat}, {start_lon}) до ({end_lat}, {end_lon})")
        logger.debug(f"Фильтры: transport_types={transport_types}, max_transfers={max_transfers}")
        if not self.api_key:
            logger.warning("2GIS API ключ отсутствует, возвращаем заглушку")
            return self._get_stub_routes(start_lat, start_lon, end_lat, end_lon, transport_types)
        payload = {
            "locale": "ru",
            "source": {
                "name": "Начальная точка",
                "point": {"lat": start_lat, "lon": start_lon}
            },
            "target": {
                "name": "Конечная точка", 
                "point": {"lat": end_lat, "lon": end_lon}
            }
        }
        if transport_types:
            valid_types = [t for t in transport_types if t in self.TRANSPORT_TYPES]
            if valid_types:
                payload["transport"] = valid_types
                logger.debug(f"Применены фильтры транспорта: {valid_types}")
        
        try:
            logger.debug(f"Отправляем запрос к 2GIS API: {self.base_url}")
            logger.debug(f"Полезная нагрузка: {json.dumps(payload, ensure_ascii=False)}")
            
            response = requests.post(
                f"{self.base_url}?key={self.api_key}",
                headers={'Content-Type': 'application/json'},
                data=json.dumps(payload),
                timeout=15
            )
            response.raise_for_status()
            api_data = response.json()
            
            logger.debug(f"Получен ответ от 2GIS API: {len(api_data)} маршрутов")
            filtered_routes = self._filter_routes(api_data, max_transfers)
            result = self._parse_to_our_format(filtered_routes, start_lat, start_lon, end_lat, end_lon)
            
            logger.info(f"Успешно найдено маршрутов: {len(result.get('result', []))}")
            return result
            
        except requests.exceptions.Timeout:
            logger.error("2GIS API: Таймаут запроса (15 сек)")
            raise Exception("2GIS API не отвечает. Попробуйте позже.")
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка 2GIS Public Transport API: {e}")
            return self._get_stub_routes(start_lat, start_lon, end_lat, end_lon, transport_types)
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON от 2GIS API: {e}")
            return self._get_stub_routes(start_lat, start_lon, end_lat, end_lon, transport_types)
    
    def _filter_routes(self, api_data: list, max_transfers: Optional[int]) -> list:
        """Фильтрация маршрутов по количеству пересадок"""
        if not api_data or max_transfers is None:
            return api_data
        
        filtered = []
        for route in api_data:
            total_transfers = route.get('transfer_count', 0) + route.get('crossing_count', 0)
            if total_transfers <= max_transfers:
                filtered.append(route)
        
        logger.debug(f"Фильтрация по пересадкам: из {len(api_data)} осталось {len(filtered)} маршрутов")
        return filtered
    
    def _parse_to_our_format(self, api_routes: list, start_lat, start_lon, end_lat, end_lon) -> dict:
        """Преобразование ответа 2GIS в наш внутренний формат"""
        result = {
            "result": [],
            "source": "2gis_public_transport",
            "total_routes": len(api_routes)
        }
        display_routes = api_routes[:5]  
        
        for idx, route in enumerate(display_routes):
            try:
                route_data = self._parse_single_route(route, idx)
                result["result"].append(route_data)
            except Exception as e:
                logger.error(f"Ошибка парсинга маршрута {idx}: {e}")
                continue
        
        return result
    
    def _parse_single_route(self, route: dict, idx: int) -> dict:
        """Парсинг одного маршрута"""
        total_duration = route.get('total_duration', 0)
        total_distance = route.get('total_distance', 0)
        transfer_count = route.get('transfer_count', 0)
        crossing_count = route.get('crossing_count', 0)
        transport_types = route.get('transport', [])
        main_icon = '🚌'  
        if transport_types:
            first_type = transport_types[0]
            main_icon = self.TRANSPORT_TYPES.get(first_type, {}).get('icon', '🚌')
        segments = []
        coordinates = []
        
        if 'movements' in route:
            for movement in route['movements']:
                segment = self._parse_movement(movement)
                if segment:
                    segments.append(segment)
                if 'geometry' in movement:
                    geom = self._parse_geometry(movement['geometry'])
                    coordinates.extend(geom)
        instructions = self._generate_instructions(route, segments)
        route_data = {
            "id": f"2gis_route_{idx + 1}",
            "total_time": total_duration // 60,  
            "total_distance": total_distance,
            "transfer_count": transfer_count,
            "crossing_count": crossing_count,
            "total_transfers": transfer_count + crossing_count,
            "pedestrian": route.get('pedestrian', False),
            "total_walkway_distance": route.get('total_walkway_distance', ''),
            "transport_types": transport_types,
            "transport_types_display": [self.TRANSPORT_TYPES.get(t, {}).get('name', t) 
                                       for t in transport_types],
            "segments": segments,
            "coordinates": [coordinates] if coordinates else [],
            "instructions": instructions,
            "icon": main_icon,
            "mode_display": "Общественный транспорт",
            "travel_mode": "public",
            "source": "2gis_public_transport"
        }
        
        return route_data
    
    def _parse_movement(self, movement: dict) -> Optional[dict]:
        """Парсинг отдельного перемещения (участка маршрута)"""
        move_type = movement.get('type')
        
        if move_type == 'walkway':
            moving_duration = movement.get('moving_duration', 0) // 60
            distance = movement.get('distance', 0)
            
            return {
                "type": "walk",
                "time": moving_duration,
                "waiting_time": 0,
                "details": {
                    "text": movement.get('waypoint', {}).get('comment', 'Пеший участок'),
                    "distance": f"{distance} м",
                    "from_stop": movement.get('from_stop', {}).get('name', ''),
                    "to_stop": movement.get('to_stop', {}).get('name', '')
                }
            }
        elif move_type == 'passage':
            moving_duration = movement.get('moving_duration', 0) // 60
            waiting_duration = movement.get('waiting_duration', 0) // 60
            transport_type = movement.get('waypoint', {}).get('subtype', 'bus')
            routes_names = movement.get('routes_names', [])
            route_name = ', '.join(routes_names) if routes_names else 'Неизвестный маршрут'
            
            return {
                "type": "transport",
                "time": moving_duration,
                "waiting_time": waiting_duration,
                "details": {
                    "route_name": route_name,
                    "transport_type": transport_type,
                    "transport_name": self.TRANSPORT_TYPES.get(transport_type, {}).get('name', transport_type),
                    "from_stop": movement.get('from_stop', {}).get('name', ''),
                    "to_stop": movement.get('to_stop', {}).get('name', ''),
                    "stops_count": movement.get('stops_count', 0)
                }
            }
        
        return None
    
    def _parse_geometry(self, geometry: dict) -> list:
        """Парсинг геометрии маршрута для отображения на карте"""
        coordinates = []
        if geometry.get('type') == 'LineString':
            coords = geometry.get('coordinates', [])
            for coord in coords:
                if len(coord) >= 2:
                    coordinates.append([coord[1], coord[0]])
        
        return coordinates
    
    def _generate_instructions(self, route: dict, segments: list) -> list:
        """Генерация пошаговых инструкций из данных маршрута"""
        instructions = []
        
        for i, segment in enumerate(segments):
            if segment['type'] == 'transport':
                transport_type = segment['details']['transport_type']
                transport_name = self.TRANSPORT_TYPES.get(transport_type, {}).get('name', transport_type)
                
                instruction = {
                    'step': i + 1,
                    'action': f"Садитесь на {transport_name}",
                    'details': f"Маршрут: {segment['details']['route_name']}",
                    'from': segment['details']['from_stop'],
                    'to': segment['details']['to_stop'],
                    'time': f"{segment['time']} мин в пути",
                    'waiting': f"Ожидание: {segment['waiting_time']} мин"
                }
                instructions.append(instruction)
            elif segment['type'] == 'walk':
                instruction = {
                    'step': i + 1,
                    'action': "Идите пешком",
                    'details': segment['details']['text'],
                    'distance': segment['details']['distance'],
                    'time': f"{segment['time']} мин"
                }
                instructions.append(instruction)
        
        return instructions
    
    def _get_stub_routes(self, start_lat: float, start_lon: float, 
                         end_lat: float, end_lon: float,
                         transport_types: Optional[List[str]] = None):
        """Заглушка для тестирования, когда 2GIS API недоступен"""
        logger.info("Используем заглушку для 2GIS API")
        transport_names = []
        if transport_types:
            for t in transport_types:
                if t in self.TRANSPORT_TYPES:
                    transport_names.append(self.TRANSPORT_TYPES[t]['name'])
        
        main_transport = transport_types[0] if transport_types else 'bus'
        main_icon = self.TRANSPORT_TYPES.get(main_transport, {}).get('icon', '🚌')
        
        stub_response = {
            "result": [
                {
                    "id": "2gis_stub_1",
                    "total_time": 35,
                    "total_distance": 7800,
                    "transfer_count": 1,
                    "crossing_count": 0,
                    "total_transfers": 1,
                    "pedestrian": False,
                    "total_walkway_distance": "1.2 км",
                    "transport_types": transport_types or ['bus', 'tram'],
                    "transport_types_display": transport_names or ['Автобус', 'Трамвай'],
                    "segments": [
                        {
                            "type": "walk",
                            "time": 8,
                            "waiting_time": 0,
                            "details": {
                                "text": "От начальной точки до остановки",
                                "distance": "650 м",
                                "from_stop": "Начальная точка",
                                "to_stop": "Остановка 'Центральная'"
                            }
                        },
                        {
                            "type": "transport",
                            "time": 15,
                            "waiting_time": 5,
                            "details": {
                                "route_name": "Автобус 25",
                                "transport_type": "bus",
                                "transport_name": "Автобус",
                                "from_stop": "Остановка 'Центральная'",
                                "to_stop": "Остановка 'Вокзал'",
                                "stops_count": 8
                            }
                        },
                        {
                            "type": "walk",
                            "time": 7,
                            "waiting_time": 0,
                            "details": {
                                "text": "От остановки до конечной точки",
                                "distance": "550 м",
                                "from_stop": "Остановка 'Вокзал'",
                                "to_stop": "Конечная точка"
                            }
                        }
                    ],
                    "coordinates": [[
                        [start_lat, start_lon],
                        [start_lat + 0.005, start_lon + 0.005],
                        [end_lat - 0.005, end_lon - 0.005],
                        [end_lat, end_lon]
                    ]],
                    "instructions": [
                        {
                            "step": 1,
                            "action": "Идите пешком до остановки",
                            "details": "От начальной точки до остановки 'Центральная'",
                            "distance": "650 м",
                            "time": "8 мин"
                        },
                        {
                            "step": 2,
                            "action": "Садитесь на автобус",
                            "details": "Маршрут: Автобус 25",
                            "from": "Остановка 'Центральная'",
                            "to": "Остановка 'Вокзал'",
                            "time": "15 мин в пути",
                            "waiting": "Ожидание: 5 мин"
                        },
                        {
                            "step": 3,
                            "action": "Идите пешком до цели",
                            "details": "От остановки 'Вокзал' до конечной точки",
                            "distance": "550 м",
                            "time": "7 мин"
                        }
                    ],
                    "icon": main_icon,
                    "mode_display": "Общественный транспорт (заглушка)",
                    "travel_mode": "public",
                    "source": "stub_2gis"
                }
            ],
            "source": "stub_2gis",
            "total_routes": 1
        }
        
        return stub_response