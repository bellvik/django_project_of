from django.conf import settings
from core.models import ApiLog
import time

class CompositeRoutingService:
    """Композитный сервис, который пытается использовать основной API, 
       а при ошибке переключается на резервный"""
    
    def __init__(self, primary_service, fallback_service):
        self.primary_service = primary_service
        self.fallback_service = fallback_service
    
    def get_routes(self, start_lat, start_lon, end_lat, end_lon):
        start_time = time.time()
        try:
            result = self.primary_service.get_routes(
                start_lat, start_lon, end_lat, end_lon
            )
            response_time = (time.time() - start_time) * 1000
            ApiLog.objects.create(
                provider='2gis_route',
                request_params=f"{start_lat},{start_lon}->{end_lat},{end_lon}",
                response_status=200,
                response_time_ms=response_time,
                was_cached=False
            )
            
            return result
            
        except Exception as primary_error:
            print(f"Основной API недоступен: {primary_error}. Переключаемся на резервный...")
            ApiLog.objects.create(
                provider='2gis_route',
                request_params=f"{start_lat},{start_lon}->{end_lat},{end_lon}",
                response_status=500,
                response_time_ms=(time.time() - start_time) * 1000,
                was_cached=False,
                error_message=str(primary_error)
            )
            try:
                backup_start_time = time.time()
                result = self.fallback_service.get_routes(
                    start_lat, start_lon, end_lat, end_lon
                )
                backup_response_time = (time.time() - backup_start_time) * 1000
                
                ApiLog.objects.create(
                    provider='tomtom_route',
                    request_params=f"{start_lat},{start_lon}->{end_lat},{end_lon}",
                    response_status=200,
                    response_time_ms=backup_response_time,
                    was_cached=False
                )
                
                return result
                
            except Exception as backup_error:
                print(f"Резервный API тоже недоступен: {backup_error}")
                ApiLog.objects.create(
                    provider='tomtom_route',
                    request_params=f"{start_lat},{start_lon}->{end_lat},{end_lon}",
                    response_status=500,
                    response_time_ms=(time.time() - backup_start_time) * 1000,
                    was_cached=False,
                    error_message=str(backup_error)
                )
                
                from .routing_service import StubRoutingService
                stub_service = StubRoutingService()
                return stub_service.get_routes(start_lat, start_lon, end_lat, end_lon)