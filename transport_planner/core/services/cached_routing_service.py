import hashlib
import json
import time
from datetime import timedelta
from django.utils import timezone
from core.models import CachedRoute, ApiLog

class CachedRoutingService:
    """Обертка для любого сервиса маршрутизации с кэшированием"""
    
    def __init__(self, routing_service, provider_name="stub"):
        self.routing_service = routing_service
        self.provider_name = provider_name
    
    def get_routes(self, start_lat, start_lon, end_lat, end_lon):
        
        cache_key_data = f"{start_lat}:{start_lon}:{end_lat}:{end_lon}"
        if hasattr(self.routing_service, 'travel_mode'):
            cache_key_data += f":{self.routing_service.travel_mode}"
        hash_key = hashlib.md5(cache_key_data.encode()).hexdigest()
        print(f"[DEBUG CachedRoutingService] Ключ кэша: {hash_key}")
        print(f"[DEBUG CACHE KEY] Формируем ключ из данных: {cache_key_data}")
        
       
        cache_expiry = timezone.now() - timedelta(minutes=30)
        print(f"[DEBUG CachedRoutingService] Ищем кэш старше: {cache_expiry}")
        try:
            print(f"[DEBUG CachedRoutingService] Выполняем запрос к БД...")
            cached = CachedRoute.objects.filter(
                hash_key=hash_key, 
                expires_at__gt=timezone.now()
            ).first()
            print(f"[DEBUG CachedRoutingService] Результат запроса к БД: {cached}")
            
            if cached:
                print(f"[DEBUG CachedRoutingService] ✅ Данные из кэша: {cached.route_data is not None}")
                ApiLog.objects.create(
                    provider=self.provider_name,
                    request_params=cache_key_data,
                    response_status=200,
                    response_time_ms=5,  
                    was_cached=True
                )
                print(f"✅ Данные получены из кэша: {hash_key[:8]}...")
                return cached.route_data
            else:
                print(f"[DEBUG CachedRoutingService] ❌ Не найдено в кэше.")
        except Exception as e:
            print(f"⚠️ Ошибка при чтении кэша: {e}")
            print(f"    Тип ошибки: {type(e).__name__}")
            print(f"    Сообщение: {e}")
            import traceback
        

        start_time = time.time()
        try:
  
            route_data = self.routing_service.get_routes(
                start_lat, start_lon, end_lat, end_lon
            )
            response_time = (time.time() - start_time) * 1000  
            

            try:
                CachedRoute.objects.create(
                    hash_key=hash_key,
                    route_data=route_data,
                    expires_at=timezone.now() + timedelta(minutes=30)
                )
                print(f"💾 Данные сохранены в кэш: {hash_key[:8]}...")
            except Exception as e:
                print(f"⚠️ Не удалось сохранить в кэш: {e}")
            

            ApiLog.objects.create(
                provider=self.provider_name,
                request_params=cache_key_data,
                response_status=200,
                response_time_ms=response_time,
                was_cached=False
            )
            
            return route_data
            
        except Exception as e:

            response_time = (time.time() - start_time) * 1000
            ApiLog.objects.create(
                provider=self.provider_name,
                request_params=cache_key_data,
                response_status=500,
                response_time_ms=response_time,
                was_cached=False,
                error_message=str(e)
            )
            raise