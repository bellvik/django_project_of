# core/views.py
from django.shortcuts import render, redirect
from django.conf import settings
from django.http import JsonResponse
from datetime import datetime
import time

# Импорт моделей
from .models import SearchHistory, CachedRoute, ApiLog

# Импорт форм
from .forms import RouteSearchForm

# Импорт сервисов
from .services.geocoding_service import StubGeocodingService, TomTomGeocodingService
from .services.routing_service import StubRoutingService, TomTomRoutingService, TwoGisRoutingService
from .services.cached_routing_service import CachedRoutingService
from .services.composite_routing_service import CompositeRoutingService
from .services.traffic_service import StubTrafficService


def home(request):
    """
    Главная страница приложения. Обрабатывает поиск маршрутов.
    """
    routes = []
    form = RouteSearchForm()
    geocoded_points = {}
    error_message = None
    selected_mode = 'car'  # Режим по умолчанию

    if request.method == 'GET' and 'start_point' in request.GET:
        form = RouteSearchForm(request.GET)
        
        if form.is_valid():
            start_query = form.cleaned_data['start_point']
            end_query = form.cleaned_data['end_point']

            
            # Получаем выбранный режим передвижения
            selected_mode = request.GET.get('travel_mode', 'car')
            
            # 1. ГЕОКОДИРОВАНИЕ с использованием TomTom API
            if getattr(settings, 'USE_REAL_API', False):
                geocoder = TomTomGeocodingService(api_key=settings.TOMTOM_API_KEY)
            else:
                geocoder = StubGeocodingService()
            
            start_results = geocoder.geocode(start_query)
            end_results = geocoder.geocode(end_query)

            if not start_results['results']:
                error_message = f'Не удалось найти адрес: "{start_query}". Попробуйте уточнить запрос.'
            elif not end_results['results']:
                error_message = f'Не удалось найти адрес: "{end_query}". Попробуйте уточнить запрос.'
            else:
                start_best = start_results['results'][0]
                end_best = end_results['results'][0]

                geocoded_points = {
                    'start': {
                        'address': start_best['address'],
                        'lat': start_best['lat'],
                        'lon': start_best['lon'],
                        'source': start_results.get('source', 'unknown')
                    },
                    'end': {
                        'address': end_best['address'],
                        'lat': end_best['lat'],
                        'lon': end_best['lon'],
                        'source': end_results.get('source', 'unknown')
                    }
                }

                # 2. МАРШРУТИЗАЦИЯ с композитным сервисом
                try:
                    if getattr(settings, 'USE_REAL_API', False):
                        print(f"[DEBUG] Используем TomTom напрямую, режим: {selected_mode}")
                        
                        # 1. Создаем реальный TomTom сервис с нужным режимом
                        tomtom_service = TomTomRoutingService(
                            api_key=settings.TOMTOM_API_KEY,
                            travel_mode=selected_mode  # передаем режим сюда
                        )
                        
                        # 2. Сразу оборачиваем его в кэширующий сервис (минуя CompositeRoutingService)
                        routing_service = CachedRoutingService(
                            routing_service=tomtom_service,  # передаем реальный TomTom сервис
                            provider_name=f"tomtom_{selected_mode}"
                        )
                        
                    else:
                        print(f"[DEBUG] Используем заглушку")
                        # Для заглушки используем StubRoutingService
                        stub_service = StubRoutingService()
                        routing_service = CachedRoutingService(
                            routing_service=stub_service,
                            provider_name="stub"
                        )
                    
                    # Оборачиваем в кэширующий сервис
                    cached_service = CachedRoutingService(
                        routing_service=routing_service,
                        provider_name=f"tomtom_{selected_mode}" if getattr(settings, 'USE_REAL_API', False) else "stub"
                    )
                    
                    # Получаем маршруты (с кэшированием)
                    routes_data = cached_service.get_routes(
                        geocoded_points['start']['lat'],
                        geocoded_points['start']['lon'],
                        geocoded_points['end']['lat'],
                        geocoded_points['end']['lon']
                    )

                    # 3. УЧЕТ ПРОБОК (только для автомобильного режима)
                    
                    
                    # Для пеших и велосипедных маршрутов не учитываем пробки
                     # Коэффициент пробок = 1 (без пробок)

                    # 4. ОБРАБОТКА РЕЗУЛЬТАТОВ
                    if routes_data and 'result' in routes_data:
                        for route in routes_data['result']:
                            
                            route['total_time'] = route.get('total_time', 0)  # Время уже включает пробки
                            route['traffic_delay'] = route.get('traffic_delay', 0)
                            
                            # Добавляем информацию о режиме передвижения
                            mode_display = {
                                'car': {'name': '🚗 На машине', 'icon': '🚗'},
                                'pedestrian': {'name': '🚶 Пешком', 'icon': '🚶'},
                                'bicycle': {'name': '🚲 На велосипеде', 'icon': '🚲'}
                            }.get(selected_mode, {'name': 'На машине', 'icon': '🚗'})
                            
                            
                           
                            
                            route['start_address'] = geocoded_points['start']['address']
                            route['end_address'] = geocoded_points['end']['address']
                            route['travel_mode'] = selected_mode
                            route['mode_display'] = mode_display['name']
                            route['mode_icon'] = mode_display['icon']
                            route['source'] = routes_data.get('source', 'unknown')
                            
                            # Добавляем информацию о пробках в детали (только для авто)
                            for segment in route.get('segments', []):
                                if segment['type'] == 'transport' or segment['type'] == 'walk':
                                    if 'details' not in segment:
                                        segment['details'] = {}
                                   
                            
                            routes.append(route)

                    # 5. СОХРАНЕНИЕ ИСТОРИИ ПОИСКА с указанием режима
                    SearchHistory.objects.create(
                        start_query=start_query,
                        end_query=end_query,
                        start_coords=f"{geocoded_points['start']['lat']},{geocoded_points['start']['lon']}",
                        end_coords=f"{geocoded_points['end']['lat']},{geocoded_points['end']['lon']}",
                        is_successful=bool(routes),
                        routes_count=len(routes)
                    )

                except Exception as e:
                    error_message = f'Ошибка при поиске маршрута: {str(e)}'
                    print(f"Ошибка маршрутизации: {e}")

    # Передаем выбранный режим в контекст для сохранения в форме
    context = {
        'form': form,
        'routes': routes,
        'geocoded_points': geocoded_points,
        'error_message': error_message,
        'total_routes': len(routes),
        'selected_mode': selected_mode,
        'use_real_api': getattr(settings, 'USE_REAL_API', False),
    }

    return render(request, 'core/home.html', context)


def autocomplete_api(request):
    """API для автодополнения с использованием TomTom Search"""
    query = request.GET.get('q', '').strip()
    
    if not query or len(query) < 2:
        return JsonResponse({'results': []})
    
    try:
        if getattr(settings, 'USE_REAL_API', False):
            geocoder = TomTomGeocodingService(api_key=settings.TOMTOM_API_KEY)
        else:
            geocoder = StubGeocodingService()
        
        results = geocoder.geocode(query)
        
        formatted_results = []
        for item in results['results'][:5]:
            formatted_results.append({
                'value': item['address'],
                'label': item['address'],
                'lat': item['lat'],
                'lon': item['lon'],
                'score': item.get('score', 0),
                'type': item.get('type', '')
            })
        
        return JsonResponse({
            'results': formatted_results,
            'source': results.get('source', 'stub'),
            'total_results': results.get('total_results', 0)
        })
        
    except Exception as e:
        return JsonResponse({
            'results': [],
            'error': str(e)
        }, status=500)


def clear_cache_view(request):
    """
    Представление для очистки кэша (только для администраторов).
    """
    from django.utils import timezone
    
    # Проверяем, является ли пользователь администратором
    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect('home')
    
    message = ""
    expired_count = 0
    
    if request.method == 'POST':
        # Удаляем все устаревшие записи кэша
        expired_count = CachedRoute.objects.filter(
            expires_at__lt=timezone.now()
        ).delete()[0]
        
        # Или удаляем все записи
        if 'clear_all' in request.POST:
            all_count = CachedRoute.objects.all().delete()[0]
            message = f'Удалено всех записей: {all_count}'
        else:
            message = f'Удалено устаревших записей: {expired_count}'
    
    return render(request, 'core/admin/clear_cache.html', {
        'message': message,
        'expired_count': expired_count
    })


def api_status(request):
    """
    Простой API-эндпоинт для проверки статуса сервиса.
    """
    from django.utils import timezone
    
    # Статистика за последний час
    hour_ago = timezone.now() - timezone.timedelta(hours=1)
    
    stats = {
        'status': 'operational',
        'timestamp': timezone.now().isoformat(),
        'requests_last_hour': ApiLog.objects.filter(
            timestamp__gte=hour_ago
        ).count(),
        'cache_hits_last_hour': ApiLog.objects.filter(
            timestamp__gte=hour_ago,
            was_cached=True
        ).count(),
        'total_cached_routes': CachedRoute.objects.count(),
        'active_cached_routes': CachedRoute.objects.filter(
            expires_at__gt=timezone.now()
        ).count(),
        'services': {
            'geocoding': 'tomtom' if getattr(settings, 'USE_REAL_API', False) else 'stub',
            'routing': 'tomtom' if getattr(settings, 'USE_REAL_API', False) else 'stub',
            'traffic': 'stub',
            'caching': 'enabled'
        }
    }
    
    return JsonResponse(stats)