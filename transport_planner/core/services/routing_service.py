# core/services/routing_service.py
from abc import ABC, abstractmethod
import json
from datetime import datetime, timedelta
import requests

class BaseRoutingService(ABC):
    """Абстрактный класс для всех сервисов маршрутизации (и заглушек, и реальных)."""
    @abstractmethod
    def get_routes(self, start_point: str, end_point: str):
        pass

class StubRoutingService(BaseRoutingService):
    """Заглушка. Возвращает фиктивные маршруты в формате, похожем на 2GIS API."""
    def get_routes(self, start_point, end_point):
        # Имитируем задержку сети
        import time
        time.sleep(0.5)

        # Фиктивные данные, структурно похожие на ответ реального API
        stub_response = {
            "result": [
                {
                    "id": "route_1",
                    "total_time": 25,  # минуты
                    "total_distance": 5400,  # метры
                    "segments": [
                        {
                            "type": "walk",
                            "time": 5,
                            "details": {"text": "до остановки 'Цирк'"}
                        },
                        {
                            "type": "transport",
                            "time": 15,
                            "details": {"route_name": "Автобус 21", "stops": ["Цирк", "Гринвич"]}
                        },
                        {
                            "type": "walk",
                            "time": 5,
                            "details": {"text": "до конечной точки"}
                        }
                    ]
                },
                # Можно добавить второй фиктивный маршрут
            ]
        }
        return stub_response
# core/services/routing_service.py (добавляем в конец файла)


class TomTomRoutingService(BaseRoutingService):
    def __init__(self, api_key):
        self.api_key = api_key

    def get_routes(self, start_point, end_point):
        """
        Получает маршрут от TomTom API.
        Важно: start_point и end_point - это пока строки, но для MVP
        используем заранее заданные координаты Екатеринбурга.
        """
        try:
            # ВАЖНО: Формируем URL по правильному шаблону.
            # Координаты являются частью пути, а не параметрами.
            locations = "56.838011,60.597465:56.837814,60.613200"  # Ж/д вокзал -> Цирк
            url = f"https://api.tomtom.com/routing/1/calculateRoute/{locations}/json"
            
            # Параметры запроса
            params = {
                'key': self.api_key,
                'traffic': 'true',
                'travelMode': 'car',
                'routeType': 'fastest'  # ВАЖНО: Обязательный параметр
            }
            
            response = requests.get(url, params=params)
            print(f"TomTom API Status: {response.status_code}")
            
            if response.status_code == 200:
                api_data = response.json()
                # Преобразуем ответ TomTom в наш формат
                return self._parse_tomtom_response(api_data)
            else:
                print(f"Ошибка TomTom API: {response.status_code}, Текст: {response.text}")
                # При ошибке API возвращаем заглушку, чтобы сайт не падал
                return self._get_fallback_response()
                
        except requests.exceptions.RequestException as e:
            print(f"Ошибка подключения к TomTom: {e}")
            return self._get_fallback_response()
    
    def _parse_tomtom_response(self, api_data):
        """
        Преобразует сложный ответ TomTom API в простой формат для нашего шаблона.
        """
        # Инициализируем структуру, как у StubRoutingService
        parsed_response = {"result": []}
        
        # Проверяем, есть ли маршруты в ответе
        if 'routes' in api_data and len(api_data['routes']) > 0:
            route = api_data['routes'][0]  # Берём первый (оптимальный) маршрут
            summary = route['summary']
            
            # Основные данные маршрута
            route_data = {
                "id": "tomtom_route_1",
                "total_time": summary['travelTimeInSeconds'] // 60,  # Переводим секунды в минуты
                "total_distance": summary['lengthInMeters'],
                "traffic_delay": summary.get('trafficDelayInSeconds', 0) // 60,
                "segments": []  # У TomTom нет готового разбиения на пешие/транспортные сегменты
            }
            
            # ВАЖНО: TomTom не возвращает сегменты (walk/transport) в нужном нам виде.
            # Для MVP создадим один условный "автомобильный" сегмент.
            # В реальном проекте здесь нужна сложная логика анализа geometry.
            route_data["segments"].append({
                "type": "transport",
                "time": route_data["total_time"],  # Всё время приходится на поездку
                "details": {
                    "route_name": "Автомобильный маршрут (TomTom)",
                    "note": "Время включает пробки. Детали сегментов недоступны в этом MVP."
                }
            })
            
            parsed_response["result"].append(route_data)
            
        return parsed_response
    
    def _get_fallback_response(self):
        """Возвращает заглушку в случае ошибки"""
        stub_service = StubRoutingService()
        return stub_service.get_routes("", "")
class TwoGisRoutingService(BaseRoutingService):
    def __init__(self, demo_key):
        self.demo_key = demo_key

    def get_routes(self, start_point, end_point):
        """
        Получает маршрут от 2GIS Public Transport API.
        """
        try:
            url = 'https://routing.api.2gis.com/public_transport/2.0'
            params = {'key': self.demo_key}

            # Тело POST-запроса в формате JSON
            payload = {
                "locale": "ru",
                "source": {
                    "name": "Точка А",
                    "point": {"lat": 56.838011, "lon": 60.597465}  # ЖД вокзал
                },
                "target": {
                    "name": "Точка Б",
                    "point": {"lat": 56.837814, "lon": 60.613200}  # Цирк
                },
                "transport": ["bus", "tram", "trolleybus", "shuttle_bus"]
            }

            headers = {'Content-Type': 'application/json'}
            response = requests.post(url, params=params, json=payload, headers=headers)
            print(f"2GIS API Status: {response.status_code}")

            if response.status_code == 200:
                api_data = response.json()
                return self._parse_twogis_response(api_data)
            else:
                print(f"Ошибка 2GIS API: {response.status_code}, Текст: {response.text}")
                return self._get_fallback_response()

        except requests.exceptions.RequestException as e:
            print(f"Ошибка подключения к 2GIS: {e}")
            return self._get_fallback_response()

    def _parse_twogis_response(self, api_data):
        """
        Преобразует ответ 2GIS в наш единый формат.
        """
        parsed_response = {"result": []}

        # Ответ 2GIS приходит в виде списка вариантов
        if isinstance(api_data, list) and len(api_data) > 0:
            for idx, route_option in enumerate(api_data):
                # Преобразуем секунды в минуты для общего времени
                total_time_min = route_option['total_duration'] // 60 if route_option.get('total_duration') else 0

                # Создаем сегменты на основе движений (movements)
                segments = []
                movements = route_option.get('movements', [])

                for movement in movements:
                    seg_type = 'walk' if movement.get('type') == 'walkway' else 'transport'
                    segment = {
                        "type": seg_type,
                        "time": movement.get('moving_duration', 0) // 60,  # В минуты
                        "details": {}
                    }
                    if seg_type == 'walk':
                        segment["details"]["text"] = movement.get('waypoint', {}).get('comment', 'Пеший участок')
                    else:  # transport
                        # Пытаемся получить номер маршрута
                        routes_info = movement.get('routes', [{}])
                        route_names = routes_info[0].get('names', ['?']) if routes_info else ['?']
                        segment["details"]["route_name"] = f"Маршрут {', '.join(route_names)}"
                        # Можно добавить тип транспорта
                        transport_type = routes_info[0].get('subtype_name', 'транспорт')
                        segment["details"]["transport_type"] = transport_type

                    segments.append(segment)

                # Если движений нет, создаем один общий сегмент
                if not segments:
                    segments.append({
                        "type": "transport",
                        "time": total_time_min,
                        "details": {
                            "route_name": f"Вариант {idx + 1}",
                            "note": "Детали маршрута недоступны."
                        }
                    })

                route_data = {
                    "id": f"twogis_route_{idx}",
                    "total_time": total_time_min,
                    "total_distance": route_option.get('total_distance', 0),
                    "segments": segments
                }
                parsed_response["result"].append(route_data)

        return parsed_response

    def _get_fallback_response(self):
        stub_service = StubRoutingService()
        return stub_service.get_routes("", "")