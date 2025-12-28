# core/services/composite_routing_service.py
from django.conf import settings
from core.models import ApiLog
import time

class CompositeRoutingService:
    """Упрощенный сервис: использует TomTom, если включен, иначе заглушку"""
    
    def __init__(self, primary_service, fallback_service):
        self.primary_service = primary_service 
        self.fallback_service = fallback_service  
    
    def get_routes(self, start_lat, start_lon, end_lat, end_lon):
        start_time = time.time()
        
        
        if getattr(settings, 'USE_REAL_API', False):
            print(f"[DEBUG] USE_REAL_API=True, используем только TomTom")
            try:
                result = self.fallback_service.get_routes(
                    start_lat, start_lon, end_lat, end_lon
                )
                response_time = (time.time() - start_time) * 1000
                
               
                ApiLog.objects.create(
                    provider='tomtom_route',
                    request_params=f"{start_lat},{start_lon}->{end_lat},{end_lon}",
                    response_status=200,
                    response_time_ms=response_time,
                    was_cached=False
                )
                return result
                
            except Exception as tomtom_error:
                print(f"[DEBUG] TomTom API упал: {tomtom_error}")
                
                ApiLog.objects.create(
                    provider='tomtom_route',
                    request_params=f"{start_lat},{start_lon}->{end_lat},{end_lon}",
                    response_status=500,
                    response_time_ms=(time.time() - start_time) * 1000,
                    was_cached=False,
                    error_message=str(tomtom_error)
                )
                
                print(f"[DEBUG] Переключаемся на заглушку")
                return self.primary_service.get_routes(start_lat, start_lon, end_lat, end_lon)
        
       
        print(f"[DEBUG] USE_REAL_API=False, используем заглушку")
        try:
            result = self.primary_service.get_routes(start_lat, start_lon, end_lat, end_lon)
            response_time = (time.time() - start_time) * 1000
            
            ApiLog.objects.create(
                provider='stub',
                request_params=f"{start_lat},{start_lon}->{end_lat},{end_lon}",
                response_status=200,
                response_time_ms=response_time,
                was_cached=False
            )
            return result
            
        except Exception as stub_error:
            print(f"[DEBUG] Заглушка тоже упала: {stub_error}")
            raise Exception("Все сервисы маршрутизации недоступны")