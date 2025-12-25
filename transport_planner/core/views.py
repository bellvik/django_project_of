# core/views.py
from django.shortcuts import render, redirect
from django.conf import settings
from django.http import JsonResponse
from datetime import datetime
import time


from .models import SearchHistory, CachedRoute, ApiLog


from .forms import RouteSearchForm


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

    if request.method == 'GET' and 'start_point' in request.GET:
        form = RouteSearchForm(request.GET)

        if form.is_valid():
            start_query = form.cleaned_data['start_point']
            end_query = form.cleaned_data['end_point']
            traffic_level = form.cleaned_data['traffic_level']
            

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


                try:
                    if getattr(settings, 'USE_REAL_API', False):
                       
                        tomtom_service = TomTomRoutingService(api_key=settings.TOMTOM_API_KEY)
                        twogis_service = TwoGisRoutingService(api_key=getattr(settings, 'TWOGIS_DEMO_KEY', ''))
                        
                        
                        routing_service = CompositeRoutingService(
                            primary_service=twogis_service,
                            fallback_service=tomtom_service
                        )
                    else:
                        routing_service = StubRoutingService()
                    
                  
                    cached_service = CachedRoutingService(
                        routing_service=routing_service,
                        provider_name="composite_route"
                    )
                    
                    routes_data = cached_service.get_routes(
                        geocoded_points['start']['lat'],
                        geocoded_points['start']['lon'],
                        geocoded_points['end']['lat'],
                        geocoded_points['end']['lon']
                    )

                   
                    traffic_service = StubTrafficService()
                    traffic_coef = traffic_service.get_traffic_coefficient(
                        traffic_level,
                        datetime.now()
                    )

                    
                    if routes_data and 'result' in routes_data:
                        for route in routes_data['result']:
                            base_time = route.get('total_time', 0)
                            adjusted_time = base_time * traffic_coef
                            
                            route['adjusted_time'] = round(adjusted_time, 1)
                            route['traffic_coef'] = traffic_coef
                            route['base_time'] = base_time
                            route['start_address'] = geocoded_points['start']['address']
                            route['end_address'] = geocoded_points['end']['address']
                            route['source'] = routes_data.get('source', 'unknown')
                            
                          
                            for segment in route.get('segments', []):
                                if segment['type'] == 'transport':
                                    if 'details' not in segment:
                                        segment['details'] = {}
                                    segment['details']['traffic_coef'] = traffic_coef
                            
                            routes.append(route)

                  
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

    context = {
        'form': form,
        'routes': routes,
        'geocoded_points': geocoded_points,
        'error_message': error_message,
        'total_routes': len(routes),
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
    
    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect('home')
    
    message = ""
    expired_count = 0
    
    if request.method == 'POST':
        expired_count = CachedRoute.objects.filter(
            expires_at__lt=timezone.now()
        ).delete()[0]
        
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