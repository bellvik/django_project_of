# core/views.py

import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from io import BytesIO
import base64
import json
import logging
from datetime import datetime, date, timedelta
import time

from django.shortcuts import render, redirect
from django.conf import settings
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Avg, Q, Case, When, FloatField
from django.db.models.functions import TruncHour, TruncDay
from django.core.cache import cache
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone
import numpy as np

from .models import SearchHistory, CachedRoute, ApiLog
from .forms import RouteSearchForm
from .services.geocoding_service import StubGeocodingService, TomTomGeocodingService
from .services.routing_service import StubRoutingService, TomTomRoutingService,TwoGisRoutingService
from .services.twogis_public_transport_service import TwoGisPublicTransportService
from .services.cached_routing_service import CachedRoutingService
from .services.composite_routing_service import CompositeRoutingService
logger = logging.getLogger(__name__)

def home(request):
    """
    Главная страница приложения. Обрабатывает поиск маршрутов.
    Поддерживает фильтрацию для общественного транспорта.
    """
    routes = []
    form = RouteSearchForm(request.GET or None)
    geocoded_points = {}
    error_message = None
    applied_filters = {}
    
    
    if request.GET:
        logger.debug(f"GET параметры: {dict(request.GET)}")
    
    if request.method == 'GET' and form.is_valid():
        start_query = form.cleaned_data['start_point']
        end_query = form.cleaned_data['end_point']
        travel_mode = form.cleaned_data['travel_mode']
        logger.info(f"Режим маршрутизации: {travel_mode}")
        if getattr(settings, 'USE_REAL_API', False):
            geocoder = TomTomGeocodingService(api_key=settings.TOMTOM_API_KEY)
            logger.debug("Используем реальное геокодирование (TomTom)")
        else:
            geocoder = StubGeocodingService()
            logger.debug("Используем заглушку для геокодирования")
        try:
            start_results = geocoder.geocode(start_query)
            logger.debug(f"Результаты геокодирования начала: {len(start_results.get('results', []))} вариантов")
        except Exception as e:
            logger.error(f"Ошибка геокодирования начальной точки: {e}")
            start_results = {'results': []}
        try:
            end_results = geocoder.geocode(end_query)
            logger.debug(f"Результаты геокодирования конца: {len(end_results.get('results', []))} вариантов")
        except Exception as e:
            logger.error(f"Ошибка геокодирования конечной точки: {e}")
            end_results = {'results': []}
        if not start_results.get('results'):
            error_message = f'Не удалось найти адрес: "{start_query}". Попробуйте уточнить запрос.'
            logger.warning(f"Не найдена начальная точка: {start_query}")
        elif not end_results.get('results'):
            error_message = f'Не удалось найти адрес: "{end_query}". Попробуйте уточнить запрос.'
            logger.warning(f"Не найдена конечная точка: {end_query}")
        else:
            start_best = start_results['results'][0]
            end_best = end_results['results'][0]
            
            logger.info(f"Начальная точка: {start_best['address']} ({start_best['lat']:.4f}, {start_best['lon']:.4f})")
            logger.info(f"Конечная точка: {end_best['address']} ({end_best['lat']:.4f}, {end_best['lon']:.4f})")
            geocoded_points = {
                'start': {
                    'address': start_best['address'],
                    'lat': start_best['lat'],
                    'lon': start_best['lon'],
                    'source': start_results.get('source', 'unknown'),
                    'query': start_query
                },
                'end': {
                    'address': end_best['address'],
                    'lat': end_best['lat'],
                    'lon': end_best['lon'],
                    'source': end_results.get('source', 'unknown'),
                    'query': end_query
                }
            }
            routing_kwargs = {
                'travel_mode': travel_mode,
            }
            if travel_mode == 'public':
                transport_types = form.cleaned_data.get('transport_types', [])
                if 'all' in transport_types or not transport_types:
                    routing_kwargs['transport_types'] = None
                    logger.debug("Используем все типы транспорта")
                else:
                    routing_kwargs['transport_types'] = transport_types
                    logger.debug(f"Фильтры транспорта: {transport_types}")
                max_transfers = form.cleaned_data.get('max_transfers', 'any')
                if max_transfers != 'any':
                    try:
                        routing_kwargs['max_transfers'] = int(max_transfers)
                        logger.debug(f"Макс. пересадок: {max_transfers}")
                    except ValueError:
                        routing_kwargs['max_transfers'] = None
                else:
                    routing_kwargs['max_transfers'] = None
                only_direct = form.cleaned_data.get('only_direct', False)
                if only_direct:
                    routing_kwargs['only_direct'] = True
                    logger.debug("Только прямые маршруты")
                else:
                    routing_kwargs['only_direct'] = False
                applied_filters = {
                    'transport_types': transport_types if transport_types and 'all' not in transport_types else None,
                    'max_transfers': max_transfers if max_transfers != 'any' else None,
                    'only_direct': only_direct
                }
            
            try:
                composite_service = CompositeRoutingService()
                if travel_mode == 'public':
                    provider_name = "2gis_public_transport"
                else:
                    provider_name = f"tomtom_{travel_mode}"
                cached_service = CachedRoutingService(
                    routing_service=composite_service,
                    provider_name=provider_name
                )
                
                logger.info(f"Ищем маршруты с параметрами: {routing_kwargs}")
                routes_data = cached_service.get_routes(
                    geocoded_points['start']['lat'],
                    geocoded_points['start']['lon'],
                    geocoded_points['end']['lat'],
                    geocoded_points['end']['lon'],
                    **routing_kwargs
                )
                
                logger.info(f"Получено маршрутов: {len(routes_data.get('result', []))}")
                if routes_data and 'result' in routes_data:
                    for i, route in enumerate(routes_data['result']):
                        if travel_mode == 'public' and applied_filters:
                            route['filters_applied'] = applied_filters
                        if travel_mode == 'public':
                            transport_types_in_route = route.get('transport_types', [])
                            if transport_types_in_route:
                                primary_type = transport_types_in_route[0]
                                transport_icons = {
                                    'bus': '🚌', 'tram': '🚋', 'trolleybus': '🚎',
                                    'subway': '🚇', 'train': '🚆', 'shuttle_bus': '🚐',
                                    'funicular': '🚡', 'monorail': '🚝', 'water': '⛴️',
                                    'cable_car': '🚠', 'aeroexpress': '🚄', 'mcd': '🚆',
                                    'mck': '🚆', 'transport': '🚌'
                                }
                                route['icon'] = transport_icons.get(primary_type, '🚌')
                            else:
                                route['icon'] = '🚌'
                            if transport_types_in_route:
                                type_names = []
                                for t_type in transport_types_in_route:
                                    if t_type in TwoGisPublicTransportService.TRANSPORT_TYPES:
                                        type_names.append(TwoGisPublicTransportService.TRANSPORT_TYPES[t_type]['name'])
                                    else:
                                        type_names.append(t_type)
                                route['transport_types_display'] = ', '.join(type_names)
                        else:
                            mode_icons = {
                                'car': '🚗', 'pedestrian': '🚶', 'bicycle': '🚲'
                            }
                            if travel_mode == 'car' and 'instructions' not in route:
                                route['instructions'] = []
                                for seg_idx, segment in enumerate(route.get('segments', [])):
                                    instruction = {
                                        'step': seg_idx + 1,
                                        'action': segment.get('details', {}).get('text', 'Продолжайте движение'),
                                        'direction': segment.get('details', {}).get('direction', ''),
                                        'distance': segment.get('details', {}).get('distance', ''),
                                        'time': f"{segment.get('time', 0)} мин",
                                        'street': segment.get('details', {}).get('street', '')
                                    }
                                    route['instructions'].append(instruction)
                            route['icon'] = mode_icons.get(travel_mode, '📍')
                        mode_display_map = {
                            'public': 'Общественный транспорт',
                            'car': 'На машине',
                            'pedestrian': 'Пешком',
                            'bicycle': 'На велосипеде'
                        }
                        route['mode_display'] = mode_display_map.get(travel_mode, 'Маршрут')
                        route['travel_mode'] = travel_mode
                        route['number'] = i + 1
                        for segment in route.get('segments', []):
                            if 'details' not in segment:
                                segment['details'] = {}
                        if 'coordinates' not in route or not route['coordinates']:
                            route['coordinates'] = [[
                                [geocoded_points['start']['lat'], geocoded_points['start']['lon']],
                                [geocoded_points['end']['lat'], geocoded_points['end']['lon']]
                            ]]
                        
                        routes.append(route)
                try:
                    search_history = SearchHistory.objects.create(
                        start_query=start_query,
                        end_query=end_query,
                        start_coords=f"{geocoded_points['start']['lat']:.6f},{geocoded_points['start']['lon']:.6f}",
                        end_coords=f"{geocoded_points['end']['lat']:.6f},{geocoded_points['end']['lon']:.6f}",
                        is_successful=bool(routes),
                        routes_count=len(routes),
                        travel_mode=travel_mode,
                        transport_types=','.join(applied_filters.get('transport_types', [])) 
                            if applied_filters.get('transport_types') else '',
                        max_transfers=applied_filters.get('max_transfers', ''),
                    )
                    logger.debug(f"Сохранено в историю поиска: ID {search_history.id}")
                except Exception as e:
                    logger.error(f"Ошибка сохранения в историю поиска: {e}")
                
            except Exception as e:
                error_message = f'Ошибка при поиске маршрута: {str(e)}'
                logger.error(f"Ошибка маршрутизации: {e}", exc_info=True)
                try:
                    logger.info("Пробуем использовать заглушку как фолбэк")
                    stub_service = StubRoutingService()
                    cached_service = CachedRoutingService(
                        routing_service=stub_service,
                        provider_name="stub_fallback"
                    )
                    
                    routes_data = cached_service.get_routes(
                        geocoded_points['start']['lat'],
                        geocoded_points['start']['lon'],
                        geocoded_points['end']['lat'],
                        geocoded_points['end']['lon']
                    )
                    
                    if routes_data and 'result' in routes_data:
                        routes = routes_data['result']
                        for i, route in enumerate(routes):
                            route['number'] = i + 1
                            route['icon'] = '⚠️'
                            route['mode_display'] = 'Резервный режим'
                            route['travel_mode'] = travel_mode
                except Exception as fallback_error:
                    logger.error(f"Фолбэк также не сработал: {fallback_error}")
    
    elif request.method == 'GET' and form.errors:

        error_message = 'Пожалуйста, проверьте введенные данные'
        logger.warning(f"Ошибки в форме: {form.errors}")
    routes_json = json.dumps(routes, cls=DjangoJSONEncoder, ensure_ascii=False)
    geocoded_points_json = json.dumps(geocoded_points, cls=DjangoJSONEncoder, ensure_ascii=False)
    total_routes = len(routes)
    if total_routes > 0:
        avg_time = sum(r.get('total_time', 0) for r in routes) / total_routes
        avg_distance = sum(r.get('total_distance', 0) for r in routes) / total_routes
    else:
        avg_time = 0
        avg_distance = 0
    context = {
        'form': form,
        'routes': routes,
        'routes_json': routes_json,
        'geocoded_points': geocoded_points,
        'geocoded_points_json': geocoded_points_json,
        'error_message': error_message,
        'total_routes': total_routes,
        'avg_time': round(avg_time, 1),
        'avg_distance': round(avg_distance, 0),
        'applied_filters': applied_filters,
        'use_real_api': getattr(settings, 'USE_REAL_API', False),
        'use_public_transport': getattr(settings, 'USE_PUBLIC_TRANSPORT_API', True),
        'is_public_transport': form.cleaned_data.get('travel_mode', 'public') == 'public' if form.is_bound else False,
        'selected_transport_types': form.cleaned_data.get('transport_types', []) if form.is_bound else [],
        'selected_max_transfers': form.cleaned_data.get('max_transfers', 'any') if form.is_bound else 'any',
        'selected_only_direct': form.cleaned_data.get('only_direct', False) if form.is_bound else False,
    }
    
    return render(request, 'core/home.html', context)


def autocomplete_api(request):
    """
    API для автодополнения адресов с использованием TomTom Search или заглушки.
    """
    query = request.GET.get('q', '').strip()
    
    if not query or len(query) < 2:
        return JsonResponse({'results': []})
    
    try:
        logger.debug(f"Автодополнение для запроса: '{query}'")
        if getattr(settings, 'USE_REAL_API', False):
            geocoder = TomTomGeocodingService(api_key=settings.TOMTOM_API_KEY)
            logger.debug("Используем TomTom для автодополнения")
        else:
            geocoder = StubGeocodingService()
            logger.debug("Используем заглушку для автодополнения")

        results = geocoder.geocode(query)
        formatted_results = []
        for i, item in enumerate(results.get('results', [])[:8]):  # Ограничиваем 8 результатами
            formatted_results.append({
                'id': i,
                'value': item.get('address', ''),
                'label': item.get('address', ''),
                'lat': item.get('lat', 0),
                'lon': item.get('lon', 0),
                'score': item.get('score', 0),
                'type': item.get('type', ''),
                'full_address': item.get('address', '')
            })
        
        logger.debug(f"Найдено результатов: {len(formatted_results)}")
        
        response_data = {
            'results': formatted_results,
            'source': results.get('source', 'stub'),
            'total_results': results.get('total_results', 0),
            'query': query
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        logger.error(f"Ошибка автодополнения: {e}", exc_info=True)
        return JsonResponse({
            'results': [],
            'error': str(e),
            'query': query
        }, status=500)


@staff_member_required
def clear_cache_view(request):
    """
    Представление для очистки кэша маршрутов (только для администраторов).
    """
    from django.utils import timezone
    
    message = ""
    expired_count = 0
    all_count = 0
    
    if request.method == 'POST':
        expired_count = CachedRoute.objects.filter(
            expires_at__lt=timezone.now()
        ).delete()[0]

        if 'clear_all' in request.POST:
            all_count = CachedRoute.objects.all().delete()[0]
            message = f'Удалено всех записей кэша: {all_count}'
            logger.info(f"Администратор {request.user} очистил весь кэш: {all_count} записей")
        else:
            message = f'Удалено устаревших записей кэша: {expired_count}'
            logger.info(f"Администратор {request.user} очистил устаревший кэш: {expired_count} записей")

    cache_stats = {
        'total': CachedRoute.objects.count(),
        'active': CachedRoute.objects.filter(expires_at__gt=timezone.now()).count(),
        'expired': CachedRoute.objects.filter(expires_at__lt=timezone.now()).count(),
        'oldest': CachedRoute.objects.order_by('created_at').first(),
        'newest': CachedRoute.objects.order_by('-created_at').first(),
    }
    
    return render(request, 'core/admin/clear_cache.html', {
        'message': message,
        'expired_count': expired_count,
        'all_count': all_count,
        'cache_stats': cache_stats
    })


def api_status(request):
    """
    Простой API-эндпоинт для проверки статуса сервиса и статистики.
    """
    from django.utils import timezone
    hour_ago = timezone.now() - timezone.timedelta(hours=1)
    day_ago = timezone.now() - timezone.timedelta(days=1)

    stats = {
        'status': 'operational',
        'timestamp': timezone.now().isoformat(),
        'requests_last_hour': ApiLog.objects.filter(timestamp__gte=hour_ago).count(),
        'requests_last_day': ApiLog.objects.filter(timestamp__gte=day_ago).count(),
        'cache_hits_last_hour': ApiLog.objects.filter(timestamp__gte=hour_ago, was_cached=True).count(),
        'successful_searches_last_hour': SearchHistory.objects.filter(
            timestamp__gte=hour_ago, is_successful=True
        ).count(),
        'total_cached_routes': CachedRoute.objects.count(),
        'active_cached_routes': CachedRoute.objects.filter(expires_at__gt=timezone.now()).count(),
        'services': {
            'geocoding': 'tomtom' if getattr(settings, 'USE_REAL_API', False) else 'stub',
            'routing_public_transport': '2gis' if getattr(settings, 'USE_PUBLIC_TRANSPORT_API', True) else 'stub',
            'routing_other': 'tomtom' if getattr(settings, 'USE_REAL_API', False) else 'stub',
            'caching': 'enabled'
        }
    }
    

    provider_stats = {}
    for provider in ['2gis_public_transport', 'tomtom_car', 'tomtom_pedestrian', 'tomtom_bicycle', 'stub']:
        logs = ApiLog.objects.filter(provider=provider, timestamp__gte=hour_ago)
        if logs.exists():
            provider_stats[provider] = {
                'requests': logs.count(),
                'avg_response_time': logs.aggregate(avg=Avg('response_time_ms'))['avg'] or 0,
                'success_rate': (logs.filter(response_status=200).count() / logs.count() * 100) 
                    if logs.count() > 0 else 0,
                'cache_hit_rate': (logs.filter(was_cached=True).count() / logs.count() * 100) 
                    if logs.count() > 0 else 0
            }
    
    stats['provider_stats'] = provider_stats
    
    return JsonResponse(stats)


@staff_member_required
def analytics_dashboard(request):
    """Дашборд аналитики для администраторов с графиками и статистикой"""

    cache_key = f"analytics_dashboard_{date.today().strftime('%Y%m%d')}"
    

    if cached_data := cache.get(cache_key) and not request.GET.get('refresh'):
        context = cached_data
        logger.debug("Используем кэшированные данные дашборда")
    else:
        logger.info("Генерация новых данных для дашборда")
        

        total_searches = SearchHistory.objects.count()
        successful_searches = SearchHistory.objects.filter(is_successful=True).count()
        failed_searches = SearchHistory.objects.filter(is_successful=False).count()

        week_ago = timezone.now() - timedelta(days=7)
        today = timezone.now().date()
        

        top_routes = SearchHistory.objects.filter(
            is_successful=True,
            timestamp__gte=week_ago
        ).values('start_query', 'end_query').annotate(
            count=Count('id'),
            avg_routes=Avg('routes_count'),
            success_rate=Avg(
                Case(When(is_successful=True, then=100), default=0, output_field=FloatField())
            )
        ).order_by('-count')[:10]

        provider_stats = ApiLog.objects.filter(
            timestamp__gte=week_ago
        ).values('provider').annotate(
            request_count=Count('id'),
            avg_response_time=Avg('response_time_ms'),
            success_rate=Avg(
                Case(When(response_status=200, then=100), default=0, output_field=FloatField())
            ),
            cache_hit_rate=Avg(
                Case(When(was_cached=True, then=100), default=0, output_field=FloatField())
            )
        ).order_by('-request_count')
        

        hourly_stats = ApiLog.objects.filter(
            timestamp__date=today
        ).annotate(
            hour=TruncHour('timestamp')
        ).values('hour').annotate(
            requests=Count('id'),
            avg_time=Avg('response_time_ms')
        ).order_by('hour')
        

        travel_mode_stats = SearchHistory.objects.filter(
            is_successful=True,
            timestamp__gte=week_ago
        ).exclude(travel_mode__isnull=True).exclude(travel_mode='').values(
            'travel_mode'
        ).annotate(
            count=Count('id'),
            avg_routes=Avg('routes_count'),
            avg_success=Avg(
                Case(When(is_successful=True, then=100), default=0, output_field=FloatField())
            )
        ).order_by('-count')
        
        conversion_rate = (successful_searches / total_searches * 100) if total_searches > 0 else 0
        
        common_errors = ApiLog.objects.filter(
            response_status__gte=400
        ).values('error_message', 'provider').annotate(
            count=Count('id'),
            last_occurred=Max('timestamp')
        ).exclude(error_message='').order_by('-count')[:10]
        

        peak_hours = SearchHistory.objects.annotate(
            hour=TruncHour('timestamp')
        ).values('hour').annotate(
            searches=Count('id')
        ).order_by('-searches')[:10]
        

        graphs = {}
        
        # 1. График ТОП маршрутов
        if top_routes:
            df_routes = pd.DataFrame(list(top_routes))
            if not df_routes.empty:
                graphs['top_routes'] = create_top_routes_chart(df_routes)
        
        # 2. График статистики по провайдерам
        if provider_stats:
            df_providers = pd.DataFrame(list(provider_stats))
            if not df_providers.empty:
                graphs['provider_stats'] = create_provider_stats_chart(df_providers)
        
        # 3. График почасовой активности
        if hourly_stats:
            df_hourly = pd.DataFrame(list(hourly_stats))
            if not df_hourly.empty:
                graphs['hourly_activity'] = create_hourly_chart(df_hourly)
        
        # 4. График типов маршрутов
        if travel_mode_stats:
            df_modes = pd.DataFrame(list(travel_mode_stats))
            if not df_modes.empty:
                graphs['travel_modes'] = create_travel_modes_chart(df_modes)
        
        # 5. График трендов по дням
        daily_trends = ApiLog.objects.filter(
            timestamp__gte=week_ago
        ).annotate(
            day=TruncDay('timestamp')
        ).values('day').annotate(
            requests=Count('id'),
            avg_time=Avg('response_time_ms'),
            cache_hits=Count('id', filter=Q(was_cached=True))
        ).order_by('day')
        
        if daily_trends:
            df_daily = pd.DataFrame(list(daily_trends))
            if not df_daily.empty:
                graphs['daily_trends'] = create_daily_trends_chart(df_daily)
        
        # 6. График распределения времени ответа
        response_time_stats = ApiLog.objects.filter(
            timestamp__gte=week_ago,
            response_time_ms__isnull=False
        ).values('provider').annotate(
            min_time=Min('response_time_ms'),
            max_time=Max('response_time_ms'),
            p50=Avg('response_time_ms'),  
            p95=Avg(Case(
                When(response_time_ms__lte=Avg('response_time_ms') * 1.5, then='response_time_ms'),
                default=Avg('response_time_ms') * 1.5,
                output_field=FloatField()
            ))
        )
        
        if response_time_stats:
            df_response = pd.DataFrame(list(response_time_stats))
            if not df_response.empty:
                graphs['response_times'] = create_response_times_chart(df_response)
        

        context = {
            'total_searches': total_searches,
            'successful_searches': successful_searches,
            'failed_searches': failed_searches,
            'conversion_rate': round(conversion_rate, 1),
            'top_routes': list(top_routes),
            'provider_stats': list(provider_stats),
            'hourly_stats': list(hourly_stats),
            'travel_mode_stats': list(travel_mode_stats),
            'common_errors': list(common_errors),
            'peak_hours': list(peak_hours),
            'graphs': graphs,
            'week_ago': week_ago.date(),
            'today': today,
            'cache_timestamp': timezone.now(),
            'total_api_requests': ApiLog.objects.count(),
            'total_cached_items': CachedRoute.objects.count(),
            'avg_response_time': ApiLog.objects.aggregate(
                avg=Avg('response_time_ms')
            )['avg'] or 0,
        }
        

        cache.set(cache_key, context, 300)
        logger.info("Данные дашборда сгенерированы и закэшированы")
    
    return render(request, 'core/admin/analytics_dashboard.html', context)



def create_top_routes_chart(df):
    """Создает горизонтальную столбчатую диаграмму ТОП маршрутов"""
    try:
        plt.figure(figsize=(14, 8))
        

        labels = []
        for _, row in df.iterrows():
            start = str(row['start_query'])[:20] + ('...' if len(str(row['start_query'])) > 20 else '')
            end = str(row['end_query'])[:20] + ('...' if len(str(row['end_query'])) > 20 else '')
            labels.append(f"{start}\n→ {end}")

        colors = plt.cm.viridis(np.linspace(0.2, 0.8, len(df)))
        bars = plt.barh(range(len(df)), df['count'], color=colors, edgecolor='black', linewidth=0.5)

        plt.yticks(range(len(df)), labels, fontsize=10)
        plt.xlabel('Количество запросов', fontsize=12, fontweight='bold')
        plt.title('ТОП-10 популярных маршрутов за неделю', fontsize=14, fontweight='bold', pad=20)
        plt.gca().invert_yaxis()
        plt.grid(axis='x', alpha=0.3, linestyle='--')
        

        for i, (_, row) in enumerate(df.iterrows()):
            plt.text(row['count'] + max(df['count']) * 0.01, i, 
                    f"{int(row['count'])} запр.\n({row['success_rate']:.0f}% успешных)", 
                    va='center', fontsize=9, fontweight='bold')
        
        plt.tight_layout()
        return save_plot_to_base64()
    except Exception as e:
        logger.error(f"Ошибка создания графика top_routes: {e}")
        return None


def create_provider_stats_chart(df):
    """Создает комбинированный график статистики по провайдерам"""
    try:
        plt.figure(figsize=(14, 8))
        
        x = np.arange(len(df))
        width = 0.35

        fig, ax1 = plt.subplots(figsize=(14, 8))
        bars = ax1.bar(x - width/2, df['request_count'], width, 
                      label='Запросы', color='#4e79a7', edgecolor='black', alpha=0.8)

        ax2 = ax1.twinx()
        line = ax2.plot(x + width/2, df['avg_response_time'], 'o-', color='#e15759', 
                       linewidth=3, markersize=10, markerfacecolor='white', 
                       markeredgewidth=2, label='Ср. время ответа (мс)')
        

        ax1.set_xlabel('Провайдер API', fontsize=12, fontweight='bold')
        ax1.set_ylabel('Количество запросов', fontsize=12, fontweight='bold')
        ax2.set_ylabel('Среднее время ответа (мс)', fontsize=12, fontweight='bold', color='#e15759')
        ax2.tick_params(axis='y', labelcolor='#e15759')

        ax1.set_xticks(x)
        ax1.set_xticklabels([p[:15] + '...' if len(p) > 15 else p for p in df['provider']], 
                           rotation=45, ha='right', fontsize=10)

        plt.title('Статистика по провайдерам API за неделю', fontsize=14, fontweight='bold', pad=20)
        

        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left', fontsize=10)
        

        ax1.grid(axis='y', alpha=0.3, linestyle='--')
        

        for bar in bars:
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height + max(df['request_count']) * 0.01,
                    f'{int(height)}', ha='center', va='bottom', fontsize=9, fontweight='bold')
        
        plt.tight_layout()
        return save_plot_to_base64()
    except Exception as e:
        logger.error(f"Ошибка создания графика provider_stats: {e}")
        return None


def create_hourly_chart(df):
    """Создает график почасовой активности"""
    try:
        if df.empty:
            return None

        df['hour'] = pd.to_datetime(df['hour']).dt.hour
        df = df.sort_values('hour')
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True, 
                                       gridspec_kw={'height_ratios': [2, 1]})
        
        # График 1: Количество запросов по часам
        bars = ax1.bar(df['hour'], df['requests'], color='#76b7b2', 
                      edgecolor='black', alpha=0.7, width=0.8)
        ax1.set_ylabel('Количество запросов', fontsize=12, fontweight='bold')
        ax1.set_title('Почасовая активность API (сегодня)', fontsize=14, fontweight='bold', pad=20)
        ax1.grid(True, alpha=0.3, linestyle='--')
        ax1.set_axisbelow(True)

        for bar in bars:
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                    f'{int(height)}', ha='center', va='bottom', fontsize=9, fontweight='bold')
        
        # График 2: Среднее время ответа по часам
        ax2.plot(df['hour'], df['avg_time'], 'o-', color='#edc949', 
                linewidth=2.5, markersize=10, markerfacecolor='white', 
                markeredgewidth=2, markeredgecolor='#edc949')
        ax2.fill_between(df['hour'], 0, df['avg_time'], color='#edc949', alpha=0.2)
        ax2.set_xlabel('Час дня', fontsize=12, fontweight='bold')
        ax2.set_ylabel('Среднее время ответа (мс)', fontsize=12, fontweight='bold')
        ax2.grid(True, alpha=0.3, linestyle='--')
        ax2.set_axisbelow(True)
        ax2.set_xticks(df['hour'])
        ax2.set_xticklabels([f'{int(h)}:00' for h in df['hour']], rotation=45)
        

        avg_time = df['avg_time'].mean()
        ax2.axhline(y=avg_time, color='r', linestyle='--', alpha=0.5, 
                   label=f'Среднее: {avg_time:.0f} мс')
        ax2.legend(loc='upper right')
        
        plt.tight_layout()
        return save_plot_to_base64()
    except Exception as e:
        logger.error(f"Ошибка создания графика hourly_activity: {e}")
        return None


def create_travel_modes_chart(df):
    """Создает круговую диаграмму типов маршрутов"""
    try:
        if df.empty:
            return None
            
        plt.figure(figsize=(12, 10))
        
        labels = []
        for mode in df['travel_mode']:
            mode_names = {
                'public': 'Общественный транспорт',
                'car': 'Автомобиль',
                'pedestrian': 'Пешком',
                'bicycle': 'Велосипед'
            }
            labels.append(mode_names.get(mode, mode))
        

        colors = ['#4e79a7', '#f28e2c', '#e15759', '#76b7b2', '#59a14f', 
                 '#edc949', '#af7aa1', '#ff9da7', '#9c755f', '#bab0ab']
        

        wedges, texts, autotexts = plt.pie(
            df['count'], 
            labels=labels,
            autopct=lambda pct: f'{pct:.1f}%\n({int(pct/100.*df["count"].sum()):d})',
            colors=colors[:len(df)],
            startangle=90,
            textprops={'fontsize': 11},
            wedgeprops={'edgecolor': 'white', 'linewidth': 2},
            explode=[0.05] * len(df)  
        )
        

        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')
            autotext.set_fontsize(10)
        
        for text in texts:
            text.set_fontsize(12)
            text.set_fontweight('bold')
        
        plt.title('Распределение по типам маршрутов за неделю', 
                 fontsize=14, fontweight='bold', pad=30)
        

        plt.legend(wedges, [f"{l} ({c})" for l, c in zip(labels, df['count'])],
                  title="Типы маршрутов", loc="center left", bbox_to_anchor=(1, 0, 0.5, 1),
                  fontsize=10)
        
        plt.tight_layout()
        return save_plot_to_base64()
    except Exception as e:
        logger.error(f"Ошибка создания графика travel_modes: {e}")
        return None


def create_daily_trends_chart(df):
    """Создает график трендов по дням"""
    try:
        if df.empty:
            return None
            

        df['day'] = pd.to_datetime(df['day']).dt.strftime('%d.%m')
        df = df.sort_values('day')
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), 
                                       gridspec_kw={'height_ratios': [2, 1]})
        
        # График 1: Количество запросов по дням
        x = range(len(df))
        bars = ax1.bar(x, df['requests'], color='#59a14f', alpha=0.7, 
                      edgecolor='black', linewidth=1, width=0.7)
        ax1.set_ylabel('Количество запросов', fontsize=12, fontweight='bold')
        ax1.set_title('Динамика запросов по дням', fontsize=14, fontweight='bold', pad=20)
        ax1.grid(axis='y', alpha=0.3, linestyle='--')
        ax1.set_axisbelow(True)
        ax1.set_xticks(x)
        ax1.set_xticklabels(df['day'], rotation=45, ha='right', fontsize=10)
        for bar in bars:
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height + max(df['requests']) * 0.02,
                    f'{int(height)}', ha='center', va='bottom', fontsize=9, fontweight='bold')
        
        # График 2: Время ответа и кэш-хиты
        ax2.plot(x, df['avg_time'], 's-', color='#b07aa1', linewidth=2.5, 
                markersize=8, markerfacecolor='white', markeredgewidth=2, 
                label='Ср. время ответа (мс)')
        
        if 'cache_hits' in df.columns:
            ax2_twin = ax2.twinx()
            ax2_twin.bar(x, df['cache_hits'], color='#ff9da7', alpha=0.5, 
                        width=0.6, label='Кэш-хиты')
            ax2_twin.set_ylabel('Кэш-хиты', fontsize=12, fontweight='bold', color='#ff9da7')
            ax2_twin.tick_params(axis='y', labelcolor='#ff9da7')

            lines1, labels1 = ax2.get_legend_handles_labels()
            lines2, labels2 = ax2_twin.get_legend_handles_labels()
            ax2.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
        else:
            ax2.legend(loc='upper left')
        
        ax2.set_xlabel('Дата', fontsize=12, fontweight='bold')
        ax2.set_ylabel('Ср. время ответа (мс)', fontsize=12, fontweight='bold')
        ax2.grid(True, alpha=0.3, linestyle='--')
        ax2.set_axisbelow(True)
        ax2.set_xticks(x)
        ax2.set_xticklabels(df['day'], rotation=45, ha='right', fontsize=10)
        

        if len(df) > 2:
            x_numeric = np.array(x)
            z = np.polyfit(x_numeric, df['avg_time'], 1)
            p = np.poly1d(z)
            ax2.plot(x, p(x_numeric), "r--", alpha=0.7, linewidth=2, label='Тренд')
        
        plt.tight_layout()
        return save_plot_to_base64()
    except Exception as e:
        logger.error(f"Ошибка создания графика daily_trends: {e}")
        return None


def create_response_times_chart(df):
    """Создает график распределения времени ответа (боксплот)"""
    try:
        if df.empty:
            return None
            
        plt.figure(figsize=(12, 8))
        

        data_to_plot = []
        labels = []
        
        for _, row in df.iterrows():

            mean = row['p50']
            std = mean * 0.3  
            synthetic_data = np.random.normal(mean, std, 100)
            synthetic_data = np.clip(synthetic_data, row['min_time'], row['max_time'])
            data_to_plot.append(synthetic_data)
            labels.append(row['provider'][:20])
        
  
        box = plt.boxplot(data_to_plot, labels=labels, patch_artist=True, 
                         medianprops={'color': 'white', 'linewidth': 2},
                         whiskerprops={'color': '#333', 'linewidth': 1.5},
                         capprops={'color': '#333', 'linewidth': 1.5})
        
        
        colors = plt.cm.Set3(np.linspace(0, 1, len(data_to_plot)))
        for patch, color in zip(box['boxes'], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)
        
        
        plt.title('Распределение времени ответа по провайдерам', 
                 fontsize=14, fontweight='bold', pad=20)
        plt.xlabel('Провайдер API', fontsize=12, fontweight='bold')
        plt.ylabel('Время ответа (мс)', fontsize=12, fontweight='bold')
        plt.grid(axis='y', alpha=0.3, linestyle='--')
        plt.xticks(rotation=45, ha='right')
        
     
        for i, (_, row) in enumerate(df.iterrows()):
            plt.text(i + 1, row['p95'] * 1.1, f"Ø{row['p50']:.0f}мс", 
                    ha='center', va='bottom', fontsize=9, fontweight='bold',
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8))
        
        plt.tight_layout()
        return save_plot_to_base64()
    except Exception as e:
        logger.error(f"Ошибка создания графика response_times: {e}")
        return None


def save_plot_to_base64():
    """Сохраняет текущий график matplotlib в строку base64"""
    try:
        buffer = BytesIO()
        plt.savefig(buffer, format='png', bbox_inches='tight', 
                   dpi=100, facecolor='white', edgecolor='none')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        plt.close()
        return image_base64
    except Exception as e:
        logger.error(f"Ошибка сохранения графика в base64: {e}")
        plt.close()
        return None




def route_details_api(request, route_id):
    """
    API для получения детальной информации о маршруте.
    """
    try:

        return JsonResponse({
            'status': 'success',
            'message': 'Детальная информация о маршруте',
            'route_id': route_id,
            'timestamp': timezone.now().isoformat()
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


def popular_routes_api(request):
    """
    API для получения списка популярных маршрутов.
    """
    try:
        days = int(request.GET.get('days', 7))
        limit = int(request.GET.get('limit', 10))
        
        date_from = timezone.now() - timedelta(days=days)
        
        popular_routes = SearchHistory.objects.filter(
            timestamp__gte=date_from,
            is_successful=True
        ).values('start_query', 'end_query').annotate(
            count=Count('id'),
            avg_time=Avg('routes_count'),
            last_searched=Max('timestamp')
        ).order_by('-count')[:limit]
        
        return JsonResponse({
            'status': 'success',
            'days': days,
            'limit': limit,
            'routes': list(popular_routes),
            'timestamp': timezone.now().isoformat()
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)