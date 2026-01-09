from django.conf import settings
import logging
from .twogis_public_transport_service import TwoGisPublicTransportService
from .routing_service import TomTomRoutingService, StubRoutingService

logger = logging.getLogger(__name__)

class CompositeRoutingService:
    """Композитный сервис маршрутизации с интеллектуальным выбором провайдера"""
    
    def __init__(self):

        self.public_transport_service = TwoGisPublicTransportService()
        self.tomtom_service = TomTomRoutingService(api_key=settings.TOMTOM_API_KEY)
        self.stub_service = StubRoutingService()
        self.use_2gis_public = getattr(settings, 'USE_PUBLIC_TRANSPORT_API', True)
        self.use_2gis_car = getattr(settings, 'USE_2GIS_CAR_ROUTING', True)
        self.use_real_api = getattr(settings, 'USE_REAL_API', True)
    
    def get_routes(self, start_lat, start_lon, end_lat, end_lon, **kwargs):
        """
        Интеллектуальный выбор провайдера маршрутизации
        
        :param kwargs: Может содержать:
          - travel_mode: 'public' (общественный транспорт), 'car', 'pedestrian', 'bicycle'
          - transport_types: список типов транспорта ['tram'] для фильтрации
          - max_transfers: максимальное количество пересадок
          - only_direct: только прямые маршруты
        """
        import logging
        logger = logging.getLogger(__name__)
        
        travel_mode = kwargs.get('travel_mode', 'public')
        logger.info(f"CompositeRoutingService: режим {travel_mode}")
        if travel_mode == 'public':
            if self.use_2gis_public:
                try:
                    logger.info("Используем 2GIS Public Transport API")
                    return self.public_transport_service.get_routes(
                        start_lat, start_lon, end_lat, end_lon, **kwargs
                    )
                except Exception as e:
                    logger.error(f"2GIS Public Transport API ошибка: {e}")
                    try:
                        logger.info("Фолбэк: TomTom (пешком)")
                        kwargs['travel_mode'] = 'pedestrian'
                        return self.tomtom_service.get_routes(
                            start_lat, start_lon, end_lat, end_lon, **kwargs
                        )
                    except Exception as tomtom_error:
                        logger.error(f"TomTom также упал: {tomtom_error}")
                        return self.stub_service.get_routes(
                            start_lat, start_lon, end_lat, end_lon, **kwargs
                        )
            else:
                logger.info("2GIS Public Transport отключен, используем TomTom пешком")
                kwargs['travel_mode'] = 'pedestrian'
                return self.tomtom_service.get_routes(
                    start_lat, start_lon, end_lat, end_lon, **kwargs
                )
        

        elif travel_mode in ['car', 'pedestrian', 'bicycle']:
            logger.info(f"Используем TomTom API для режима {travel_mode}")
            try:
                kwargs['travel_mode'] = travel_mode
                return self.tomtom_service.get_routes(start_lat, start_lon, end_lat, end_lon, **kwargs)
            except Exception as e:
                logger.error(f"TomTom API ошибка: {e}")
                logger.info("Фолбэк на заглушку")
                return self.stub_service.get_routes(start_lat, start_lon, end_lat, end_lon, **kwargs)
        else:
            logger.warning(f"Неизвестный режим {travel_mode}, используем заглушку")
            return self.stub_service.get_routes(start_lat, start_lon, end_lat, end_lon, **kwargs)