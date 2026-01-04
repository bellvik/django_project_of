import hashlib
import json
import time
from datetime import timedelta
from django.utils import timezone
from core.models import CachedRoute, ApiLog
import logging

logger = logging.getLogger(__name__)

class CachedRoutingService:
    """Обертка для любого сервиса маршрутизации с кэшированием"""
    
    def __init__(self, routing_service, provider_name="stub"):
        self.routing_service = routing_service
        self.provider_name = provider_name
    
    def get_routes(self, start_lat, start_lon, end_lat, end_lon, **kwargs):
        """
        Получение маршрутов с кэшированием.
        Поддерживает передачу дополнительных параметров:
        - travel_mode: режим передвижения ('public', 'car', 'pedestrian', 'bicycle')
        - transport_types: список типов транспорта
        - max_transfers: максимальное количество пересадок
        - only_direct: только прямые маршруты
        """
        cache_key_data = f"{start_lat}:{start_lon}:{end_lat}:{end_lon}"
        if kwargs:
            sorted_kwargs = sorted(kwargs.items())
            for key, value in sorted_kwargs:
                if value is not None:
                    if isinstance(value, list):
                        value = sorted(value)
                    cache_key_data += f":{key}:{value}"
        
        hash_key = hashlib.md5(cache_key_data.encode()).hexdigest()
        logger.debug(f"[CachedRoutingService] Ключ кэша: {hash_key[:8]}...")
        logger.debug(f"[CachedRoutingService] Данные для ключа: {cache_key_data}")
        cache_expiry = timezone.now() - timedelta(minutes=30)
        logger.debug(f"[CachedRoutingService] Ищем кэш старше: {cache_expiry}")
        
        try:
            cached = CachedRoute.objects.filter(
                hash_key=hash_key, 
                expires_at__gt=timezone.now()
            ).first()
            
            if cached:
                logger.debug(f"[CachedRoutingService] ✅ Данные из кэша")
                ApiLog.objects.create(
                    provider=self.provider_name,
                    request_params=cache_key_data,
                    response_status=200,
                    response_time_ms=5,  
                    was_cached=True
                )
                return cached.route_data
            else:
                logger.debug(f"[CachedRoutingService] ❌ Не найдено в кэше.")
        except Exception as e:
            logger.error(f"Ошибка при чтении кэша: {e}")
        start_time = time.time()
        try:
            route_data = self.routing_service.get_routes(
                start_lat, start_lon, end_lat, end_lon, **kwargs
            )
            response_time = (time.time() - start_time) * 1000
            try:
                CachedRoute.objects.update_or_create(
                    hash_key=hash_key,
                    defaults={
                        'route_data': route_data,
                        'expires_at': timezone.now() + timedelta(minutes=30)
                    }
                )
                logger.debug(f"💾 Данные сохранены/обновлены в кэш: {hash_key[:8]}...")
            except Exception as e:
                logger.error(f"⚠️ Не удалось сохранить в кэш: {e}")
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
            logger.error(f"Ошибка при получении маршрутов: {e}")
            raise