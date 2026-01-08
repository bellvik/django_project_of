import requests
import json
import logging
from typing import List, Optional, Dict, Any
from django.conf import settings
from .routing_service import BaseRoutingService
import re 

logger = logging.getLogger(__name__)

class TwoGisPublicTransportService(BaseRoutingService):
    """Сервис маршрутизации через 2GIS Public Transport API для Екатеринбурга"""
    
    
    TRANSPORT_TYPES = {
        'bus': {'name': 'Автобус'},
        'tram': {'name': 'Трамвай'},
        'trolleybus': {'name': 'Троллейбус'},
        'shuttle_bus': {'name': 'Маршрутка'},
        'subway': {'name': 'Метро'},
        'train': {'name': 'Электричка'},
    }
    
    def __init__(self, api_key=None):
        self.api_key = api_key or getattr(settings, 'TWOGIS_PUBLIC_TRANSPORT_API_KEY', '')
        self.base_url = getattr(settings, 'TWOGIS_PUBLIC_TRANSPORT_URL', 
                               'https://routing.api.2gis.com/public_transport/2.0')
        
        if not self.api_key:
            logger.warning("2GIS API ключ не настроен. Будет использоваться заглушка.")
    
    def get_routes(self, start_lat: float, start_lon: float, 
                   end_lat: float, end_lon: float,
                   transport_types: Optional[List[str]] = None,
                   max_transfers: Optional[int] = None,
                   only_direct: bool = False,
                   **kwargs) -> Dict[str, Any]:
        """
        Получение маршрутов общественного транспорта.
        
        :param transport_types: Список типов транспорта ['bus', 'tram']
        :param max_transfers: Максимальное количество пересадок
        :param only_direct: Только прямые маршруты (без пересадок)
        :return: Словарь с маршрутами в стандартизированном формате
        """
        logger.info(f"2GIS API: Поиск маршрута ({start_lat:.6f}, {start_lon:.6f}) -> ({end_lat:.6f}, {end_lon:.6f})")
        if not self.api_key:
            logger.warning("API ключ отсутствует, используем заглушку")
            return self._get_enhanced_stub_routes(start_lat, start_lon, end_lat, end_lon, transport_types)
        payload = {
            "locale": "ru",
            "source": {
                "name": "Start",
                "point": {"lat": start_lat, "lon": start_lon}
            },
            "target": {
                "name": "End", 
                "point": {"lat": end_lat, "lon": end_lon}
            },
            "output": "routes"  
        }

        if transport_types:
            valid_types = self._validate_transport_types(transport_types)
            if valid_types:
                payload["transport"] = valid_types
                logger.debug(f"Фильтры транспорта: {valid_types}")
        
        try:
            print(f"URL: {self.base_url}")
            print(f"Payload: {json.dumps(payload, ensure_ascii=False)}")
            response = requests.post(
                f"{self.base_url}?key={self.api_key}",
                headers={
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                data=json.dumps(payload, ensure_ascii=False),
                timeout=15
            )
            
            logger.debug(f"Статус ответа: {response.status_code}")
            raw_response_text = response.text
            logger.debug(f"Тело ответа API (первые 2000 символов):\n{raw_response_text[:2000]}")
            if response.status_code != 200:
                logger.error(f"2GIS API ошибка: {response.status_code} - {response.text[:200]}")
                return self._get_enhanced_stub_routes(start_lat, start_lon, end_lat, end_lon, transport_types)
            api_data = response.json()
            if isinstance(api_data, list) and api_data:
                if 'movements' in api_data[0]:
                    logger.info(f"Получено {len(api_data)} маршрутов от 2GIS API")
            result = self._parse_api_response(api_data, start_lat, start_lon, end_lat, end_lon)
            filtered_result = self._apply_filters(result, max_transfers, only_direct)
            return filtered_result
            
        except requests.exceptions.Timeout:
            logger.error("2GIS API: Таймаут запроса (15 сек)")
            return self._get_enhanced_stub_routes(start_lat, start_lon, end_lat, end_lon, transport_types)
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка 2GIS API: {e}")
            return self._get_enhanced_stub_routes(start_lat, start_lon, end_lat, end_lon, transport_types)
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON: {e}")
            return self._get_enhanced_stub_routes(start_lat, start_lon, end_lat, end_lon, transport_types)
    
    def _validate_transport_types(self, transport_types: List[str]) -> List[str]:
        """Валидация и фильтрация типов транспорта для Екатеринбурга"""
        valid_types = []
        for t_type in transport_types:
            if t_type in self.TRANSPORT_TYPES:
                valid_types.append(t_type)
            else:
                logger.warning(f"Тип транспорта '{t_type}' не поддерживается в Екатеринбурге")
        return valid_types
    
    def _parse_api_response(self, api_data: List[Dict], start_lat: float, start_lon: float,
                           end_lat: float, end_lon: float) -> Dict[str, Any]:
        """Парсинг ответа API в унифицированный формат"""
        result = {
            "result": [],
            "source": "2gis_public_transport",
            "total_routes": len(api_data)
        }
        for idx, route in enumerate(api_data[:5]): 
            try:
                parsed_route = self._parse_single_route(route, idx, start_lat, start_lon, end_lat, end_lon)
                if parsed_route:
                    result["result"].append(parsed_route)
            except Exception as e:
                logger.error(f"Ошибка парсинга маршрута {idx}: {e}")
                continue
        
        return result
    
    def _parse_single_route(self, route: Dict, idx: int, 
                       start_lat: float, start_lon: float,
                       end_lat: float, end_lon: float) -> Optional[Dict[str, Any]]:
        """Полная переработка парсинга маршрута"""
        try:
            total_duration = route.get('total_duration', 0)
            total_distance = route.get('total_distance', 0)
            transfer_count = route.get('transfer_count', 0)
            crossing_count = route.get('crossing_count', 0)
            transport_types_in_route = route.get('transport', [])
            primary_type = transport_types_in_route[0] if transport_types_in_route else 'bus'
            segments = []
            all_coordinates = []
            
            if 'movements' in route:
                for movement in route['movements']:
                    segment = self._parse_movement_segment(movement)
                    if segment:
                        segments.append(segment)
                    
                    # Координаты из геометрии
                    segment_coords = self._extract_coordinates_from_movement(movement)
                    if segment_coords:
                        all_coordinates.extend(segment_coords)
            stops = self._extract_stops_from_route(route)
            segments = self._enrich_with_stops(segments, stops)
            instructions = self._generate_complete_instructions(segments)
            route_data = {
                "id": f"2gis_route_{idx + 1}",
                "total_time": total_duration // 60,
                "total_distance": total_distance,
                "transfer_count": transfer_count,
                "crossing_count": crossing_count,
                "total_transfers": transfer_count + crossing_count,
                "transport_types": transport_types_in_route,
                "transport_types_display": [
                    self.TRANSPORT_TYPES.get(t, {}).get('name', t) 
                    for t in transport_types_in_route
                ],
                "segments": segments,
                "coordinates": [all_coordinates] if all_coordinates else [],
                "instructions": instructions,
                "stops": stops, 
                "icon": self.TRANSPORT_TYPES.get(primary_type, {}).get('icon', '🚌'),
                "mode_display": "Общественный транспорт",
                "travel_mode": "public",
                "source": "2gis_public_transport",
                "start_address": f"{start_lat:.6f}, {start_lon:.6f}",
                "end_address": f"{end_lat:.6f}, {end_lon:.6f}",
                "has_detailed_stops": len(stops) > 0
            }
            return route_data
            
        except Exception as e:
            logger.error(f"Ошибка парсинга маршрута {idx}: {e}", exc_info=True)
            return None

    def _extract_coordinates_from_segment(self, segment: Dict) -> Optional[List[float]]:
        """Извлечение координат из сегмента с приоритетом по источникам данных"""
        details = segment.get('details', {})
        if details.get('from_stop_coords'):
            return details['from_stop_coords']
        if segment.get('geometry') and segment['geometry'].get('coordinates'):
            coords = segment['geometry']['coordinates']
            if coords and len(coords) > 0:
                if isinstance(coords[0], list) and len(coords[0]) >= 2:
                    return [coords[0][1], coords[0][0]]  
        if segment.get('waypoint'):
            waypoint = segment['waypoint']
            if 'location' in waypoint:
                return [waypoint['location']['lat'], waypoint['location']['lon']]
        
        return None

    def _parse_movement_segment(self, movement: Dict) -> Optional[Dict[str, Any]]:
        """
        Парсинг сегмента движения с полной обработкой формата 2GIS API
        Актуально для версии API 2.0 (2025-2026)
        """
        move_type = movement.get('type')
        
        if move_type == 'walkway':
            moving_duration = movement.get('moving_duration', 0) // 60
            distance = movement.get('distance', 0)
            waypoint = movement.get('waypoint', {})
            waypoint_name = waypoint.get('name', '')
            waypoint_comment = waypoint.get('comment', '')
            subtype = waypoint.get('subtype', 'walk')
            if waypoint_comment:
                text = waypoint_comment
            elif waypoint_name:
                text = f"Пройдите {distance} м до {waypoint_name}"
            else:
                text = f"Пройдите {distance} м пешком"
            if subtype == 'start':
                from_stop = "Ваше местоположение"
                to_stop = waypoint_name or "Точка посадки"
            elif subtype == 'finish':
                from_stop = waypoint_name or "Точка высадки"
                to_stop = "Конечный пункт"
            else:
                from_stop = waypoint_name or "Текущая позиция"
                to_stop = "Следующая точка"
            
            return {
                "type": "walk",
                "time": moving_duration,
                "waiting_time": 0,
                "details": {
                    "text": text,
                    "distance": f"{distance} м",
                    "from_stop": from_stop,
                    "to_stop": to_stop,
                    "waypoint_name": waypoint_name,
                    "waypoint_comment": waypoint_comment,
                    "subtype": subtype,
                    "direction": self._generate_walk_direction(waypoint_comment, distance)
                }
            }
            
        elif move_type == 'passage':
            moving_duration = movement.get('moving_duration', 0) // 60
            waiting_duration = movement.get('waiting_duration', 0) // 60
            stops_count = movement.get('stops_count', 0)
            routes = movement.get('routes', [])
            route_info = routes[0] if routes else {}
            route_numbers = []
            if route_info:
                if 'names' in route_info and isinstance(route_info['names'], list):
                    route_numbers = [str(name) for name in route_info['names']]
                elif 'number' in route_info:
                    route_numbers = [str(route_info['number'])]
            primary_route = route_numbers[0] if route_numbers else '?'
            transport_type = route_info.get('subtype', 'bus')
            transport_type_name = route_info.get('subtype_name', 'автобус')
            route_color = route_info.get('color', '#1a73f0')
            if len(route_numbers) > 1:
                route_display = f"{'/'.join(route_numbers)} ({transport_type_name})"
            else:
                route_display = f"{primary_route} ({transport_type_name})"
            waypoint = movement.get('waypoint', {})
            waypoint_name = waypoint.get('name', '')
            waypoint_comment = waypoint.get('comment', '')
            direction = self._generate_transport_direction(
                stops_count, 
                primary_route,
                transport_type_name,
                waypoint_comment
            )
            
            return {
                "type": "transport",
                "time": moving_duration,
                "waiting_time": waiting_duration,
                "details": {
                    "route_numbers": route_numbers,
                    "route_number": primary_route,
                    "route_name": transport_type_name,
                    "route_display": route_display,
                    "route_color": route_color,
                    "transport_type": transport_type,
                    "transport_name": self.TRANSPORT_TYPES.get(transport_type, {}).get('name', transport_type_name),
                    "stops_count": stops_count,
                    "waypoint_name": waypoint_name,
                    "waypoint_comment": waypoint_comment,
                    "from_stop": "",  
                    "to_stop": "",    
                    "from_stop_coords": None,  
                    "to_stop_coords": None,    
                    "direction": direction,
                    "full_description": f"{route_display}: {direction}"
                }
            }
            
        elif move_type == 'crossing':
            moving_duration = movement.get('moving_duration', 0) // 60
            distance = movement.get('distance', 0)
            
            return {
                "type": "walk",
                "time": moving_duration,
                "waiting_time": 0,
                "details": {
                    "text": f"Пересадка между транспортом ({distance} м)",
                    "distance": f"{distance} м",
                    "from_stop": "Место выхода",
                    "to_stop": "Остановка для пересадки",
                    "direction": f"Пройдите {distance} м для пересадки",
                    "subtype": "crossing",
                    "is_transfer": True
                }
            }
        
        return None
    def _generate_complete_instructions(self, segments: List[Dict]) -> List[Dict[str, Any]]:
        """Генерация полных инструкций с остановками"""
        instructions = []
        
        for i, segment in enumerate(segments):
            step_num = i + 1
            details = segment.get('details', {})
            
            if segment['type'] == 'transport':
                instruction = {
                    'step': step_num,
                    'action': f"Садитесь на {details.get('transport_name', 'транспорт')}",
                    'details': f"Маршрут: {details.get('route_display', '')}",
                    'route_info': details.get('route_display', ''),
                    'direction': details.get('direction', ''),
                    'from': details.get('from_stop', 'Остановка'),
                    'to': details.get('to_stop', 'Остановка'),
                    'stops': f"{details.get('stops_count', 0)} остановок",
                    'time': f"{segment['time']} мин в пути",
                    'waiting': f"Ожидание: {segment['waiting_time']} мин" if segment['waiting_time'] > 0 else "Без ожидания",
                    'icon': details.get('transport_icon', '🚌'),
                    'type': 'transport',
                    'has_stops': bool(details.get('from_stop') and details.get('to_stop'))
                }
                
            elif segment['type'] == 'walk':
                instruction = {
                    'step': step_num,
                    'action': "Идите пешком",
                    'details': details.get('text', ''),
                    'direction': details.get('direction', 'Следуйте по маршруту'),
                    'distance': details.get('distance', ''),
                    'time': f"{segment['time']} мин",
                    'from': details.get('from_stop', 'Текущая позиция'),
                    'to': details.get('to_stop', 'Следующая точка'),
                    'icon': '🚶',
                    'type': 'walk',
                    'subtype': details.get('subtype', ''),
                    'is_transfer': details.get('is_transfer', False)
                }
                if details.get('is_transfer'):
                    instruction['action'] = "Перейдите для пересадки"
                    instruction['details'] = "Пеший переход между остановками"
            
            instructions.append(instruction)
        
        return instructions
    
    def _generate_walk_direction(self, comment: str, distance: int) -> str:
        """Генерация направления для пешего участка"""
        if not comment:
            return f"Пройдите {distance} м пешком"
        direction = comment.replace("пешком", "пешком")
        if "м" not in direction and distance > 0:
            direction = f"{direction} ({distance} м)"
        
        return direction
    def _generate_transport_direction(self, stops_count: int, route_number: str, 
                                 transport_type: str, comment: str) -> str:
        """Генерация направления для транспортного участка"""
        if comment:
            return comment
        
        if stops_count == 1:
            return f"Проедьте 1 остановку на {transport_type} №{route_number}"
        elif stops_count > 1:
            return f"Проедьте {stops_count} остановок на {transport_type} №{route_number}"
        else:
            return f"Поездка на {transport_type} №{route_number}"
    def _enrich_with_stops(self, segments: List[Dict], stops: List[Dict]) -> List[Dict]:
        """Обогащение сегментов информацией об остановках"""
        if not stops:
            return segments
        
        stop_index = 0
        enriched_segments = []
        
        for segment in segments:
            segment_type = segment.get('type')
            details = segment.get('details', {})
            
            if segment_type == 'walk':
                if details.get('subtype') == 'start':
                    details['from_stop'] = details.get('from_stop', 'Начало')
                    if stop_index < len(stops):
                        details['to_stop'] = stops[stop_index].get('name', 'Остановка')
                elif details.get('subtype') == 'finish':
                    if stop_index > 0:
                        details['from_stop'] = stops[stop_index-1].get('name', 'Остановка')
                    details['to_stop'] = details.get('to_stop', 'Конец')
                elif details.get('is_transfer'):
                    details['from_stop'] = f"Переход {stop_index+1}"
                    details['to_stop'] = f"Переход {stop_index+2}"
                else:
                    if stop_index < len(stops):
                        details['from_stop'] = stops[stop_index].get('name', 'Остановка')
                        if stop_index + 1 < len(stops):
                            details['to_stop'] = stops[stop_index + 1].get('name', 'Остановка')
                            stop_index += 1
            
            elif segment_type == 'transport':
                if stop_index < len(stops) - 1:
                    from_stop = stops[stop_index]
                    to_stop = stops[stop_index + 1]
                    
                    details['from_stop'] = from_stop.get('name', 'Остановка')
                    details['to_stop'] = to_stop.get('name', 'Остановка')
                    details['from_stop_coords'] = [from_stop.get('lat'), from_stop.get('lon')]
                    details['to_stop_coords'] = [to_stop.get('lat'), to_stop.get('lon')]
                    if details['from_stop'] and details['to_stop']:
                        details['direction'] = (
                            f"{details['transport_name']} №{details['route_number']} "
                            f"от '{details['from_stop']}' до '{details['to_stop']}' "
                        )
                    
                    stop_index += 1
            
            enriched_segments.append(segment)
        
        return enriched_segments
    
    def _extract_coordinates_from_movement(self, movement: Dict) -> List[List[float]]:
        """Извлечение координат пути из сегмента движения (теперь с поддержкой WKT)"""
        coordinates = []
        if 'alternatives' in movement and movement['alternatives']:
            for alternative in movement['alternatives']:
                if 'geometry' in alternative:
                    for geom_item in alternative['geometry']:
                        wkt_string = geom_item.get('selection', '')
                        if wkt_string:
                            coords = self._parse_wkt_linestring(wkt_string)
                            coordinates.extend(coords)
        for stop_key in ['from_stop', 'to_stop']:
            if stop_key in movement and movement[stop_key]:
                stop = movement[stop_key]
                if 'location' in stop:
                    coordinates.append([
                        stop['location']['lat'],
                        stop['location']['lon']
                    ])
        
        return coordinates
    
    def _extract_stops_from_route(self, route: Dict) -> List[Dict]:
        """Извлечение остановок из всего маршрута"""
        stops = []
        waypoints = route.get('waypoints', [])
        for wp in waypoints:
            if wp.get('type') in ['stop', 'station', 'platform', 'entrance']:
                point = wp.get('point', {})
                stops.append({
                    'id': wp.get('id'),
                    'name': wp.get('name', 'Остановка'),
                    'type': wp.get('type'),
                    'lat': point.get('lat'),
                    'lon': point.get('lon'),
                    'order': len(stops)  
                })
        if not stops:
            movements = route.get('movements', [])
            for movement in movements:
                waypoint = movement.get('waypoint', {})
                if waypoint and waypoint.get('subtype') not in ['start', 'finish']:
                    stops.append({
                        'name': waypoint.get('name', ''),
                        'type': 'waypoint',
                        'comment': waypoint.get('comment', ''),
                        'subtype': waypoint.get('subtype'),
                        'order': len(stops)
                    })
        
        return stops
    def _parse_wkt_linestring(self, wkt_string: str) -> List[List[float]]:
        """
        Преобразует WKT LINESTRING в массив координат [[lat, lon], ...].
        Пример: "LINESTRING(60.572251 56.851534, 60.572335 56.851504)"
        """
        coordinates = []
        try:
            match = re.search(r'LINESTRING\((.+?)\)', wkt_string)
            if match:
                points_str = match.group(1)
                points = points_str.split(',')
                for point in points:
                    lon, lat = point.strip().split()
                    coordinates.append([float(lat), float(lon)])
        except Exception as e:
            logger.error(f"Ошибка парсинга WKT: {e}, строка: {wkt_string[:100]}")
        return coordinates
    
    def _generate_realistic_path(self, start_lat: float, start_lon: float,
                                end_lat: float, end_lon: float,
                                segments: List[Dict]) -> List[List[float]]:
        """Генерация реалистичного пути при отсутствии данных от API"""
        coordinates = []
        coordinates.append([start_lat, start_lon])
        lat_step = (end_lat - start_lat) / 4
        lon_step = (end_lon - start_lon) / 4
        
        for i in range(1, 4):
            lat = start_lat + lat_step * i + (0.001 * (i % 2))
            lon = start_lon + lon_step * i + (0.001 * ((i + 1) % 2))
            coordinates.append([lat, lon])
        coordinates.append([end_lat, end_lon])
        
        return coordinates
    
    def _generate_detailed_instructions(self, segments: List[Dict]) -> List[Dict[str, Any]]:
        """Генерация подробных пошаговых инструкций"""
        instructions = []
        
        for i, segment in enumerate(segments):
            step_num = i + 1
            
            if segment['type'] == 'transport':
                details = segment['details']
                instruction = {
                    'step': step_num,
                    'action': f"Садитесь на {details['transport_name']}",
                    'details': f"Остановка: {details['from_stop']}",
                    'direction': details.get('direction', ''),
                    'route_info': details['route_display'],
                    'from': details['from_stop'],
                    'to': details['to_stop'],
                    'stops': f"{details['stops_count']} остановок",
                    'time': f"{segment['time']} мин в пути",
                    'waiting': f"Ожидание: {segment['waiting_time']} мин",
                    'icon': self.TRANSPORT_TYPES.get(details['transport_type'], {}).get('icon', '🚌')
                }
                instructions.append(instruction)
                
            elif segment['type'] == 'walk':
                details = segment['details']
                instruction = {
                    'step': step_num,
                    'action': "Идите пешком",
                    'details': details['text'],
                    'direction': details.get('direction', ''),
                    'distance': details['distance'],
                    'time': f"{segment['time']} мин",
                    'from': details['from_stop'],
                    'to': details['to_stop'],
                    'icon': '🚶'
                }
                instructions.append(instruction)
        
        return instructions
    
    def _apply_filters(self, result: Dict[str, Any], 
                      max_transfers: Optional[int],
                      only_direct: bool) -> Dict[str, Any]:
        """Применение фильтров к результатам"""
        if not result.get('result'):
            return result
        
        filtered_routes = []
        
        for route in result['result']:
            if max_transfers is not None:
                total_transfers = route.get('total_transfers', 0)
                if total_transfers > max_transfers:
                    continue
            if only_direct and route.get('transfer_count', 0) > 0:
                continue
            
            filtered_routes.append(route)
        
        result['result'] = filtered_routes
        result['filtered_routes'] = len(filtered_routes)
        
        return result
    
    def _get_enhanced_stub_routes(self, start_lat: float, start_lon: float,
                                 end_lat: float, end_lon: float,
                                 transport_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """Улучшенная заглушка с реалистичными данными для Екатеринбурга"""
        logger.info("Используем улучшенную заглушку для 2GIS API")
        import random
        coordinates = []
        for i in range(10):
            progress = i / 9.0
            lat = start_lat + (end_lat - start_lat) * progress + random.uniform(-0.002, 0.002)
            lon = start_lon + (end_lon - start_lon) * progress + random.uniform(-0.002, 0.002)
            coordinates.append([lat, lon])
        stub_route = {
            "id": "2gis_stub_1",
            "total_time": random.randint(25, 45),
            "total_distance": random.randint(3500, 8500),
            "transfer_count": random.randint(0, 2),
            "crossing_count": 0,
            "total_transfers": random.randint(0, 2),
            "transport_types": transport_types or ['bus', 'tram'],
            "transport_types_display": [
                self.TRANSPORT_TYPES.get(t, {}).get('name', t) 
                for t in (transport_types or ['bus', 'tram'])
            ],
            "segments": [
                {
                    "type": "walk",
                    "time": 5,
                    "waiting_time": 0,
                    "details": {
                        "text": "Пройдите 400 метров до остановки 'Центральная'",
                        "distance": "400 м",
                        "from_stop": "Ваше местоположение",
                        "to_stop": "Остановка 'Центральная'",
                        "direction": "По улице Ленина до перекрестка"
                    }
                },
                {
                    "type": "transport",
                    "time": 15,
                    "waiting_time": 3,
                    "details": {
                        "route_name": "Проспект Космонавтов - Вокзал",
                        "route_number": "25",
                        "route_display": "25 (Проспект Космонавтов - Вокзал)",
                        "transport_type": "bus",
                        "transport_name": "Автобус",
                        "from_stop": "Остановка 'Центральная'",
                        "to_stop": "Остановка 'ЖД Вокзал'",
                        "stops_count": 8,
                        "direction": "Проедьте 8 остановок по проспекту Ленина"
                    }
                },
                {
                    "type": "walk",
                    "time": 7,
                    "waiting_time": 0,
                    "details": {
                        "text": "Пройдите 600 метров до конечной точки",
                        "distance": "600 м",
                        "from_stop": "Остановка 'ЖД Вокзал'",
                        "to_stop": "Конечный пункт",
                        "direction": "По привокзальной площади"
                    }
                }
            ],
            "coordinates": [coordinates],
            "instructions": [
                {
                    "step": 1,
                    "action": "Идите пешком до остановки",
                    "details": "Остановка 'Центральная'",
                    "direction": "По улице Ленина 400 метров",
                    "distance": "400 м",
                    "time": "5 мин",
                    "from": "Ваше местоположение",
                    "to": "Остановка 'Центральная'",
                    "icon": "🚶"
                },
                {
                    "step": 2,
                    "action": "Садитесь на автобус",
                    "details": "Остановка 'Центральная'",
                    "direction": "Проедьте 8 остановок",
                    "route_info": "25 (Проспект Космонавтов - Вокзал)",
                    "from": "Остановка 'Центральная'",
                    "to": "Остановка 'ЖД Вокзал'",
                    "stops": "8 остановок",
                    "time": "15 мин в пути",
                    "waiting": "Ожидание: 3 мин",
                    "icon": "🚌"
                },
                {
                    "step": 3,
                    "action": "Идите пешком до цели",
                    "details": "Конечный пункт",
                    "direction": "По привокзальной площади",
                    "distance": "600 м",
                    "time": "7 мин",
                    "from": "Остановка 'ЖД Вокзал'",
                    "to": "Конечный пункт",
                    "icon": "🚶"
                }
            ],
            "icon": "🚌",
            "mode_display": "Общественный транспорт (тестовые данные)",
            "travel_mode": "public",
            "source": "stub_2gis_ekb",
            "start_address": f"{start_lat:.6f}, {start_lon:.6f}",
            "end_address": f"{end_lat:.6f}, {end_lon:.6f}"
        }
        
        return {
            "result": [stub_route],
            "source": "stub_2gis_ekb",
            "total_routes": 1,
            "filtered_routes": 1,
            "note": "Используются тестовые данные для Екатеринбурга"
        }