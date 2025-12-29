# core/views.py
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from io import BytesIO
import base64
from django.shortcuts import render, redirect
from django.conf import settings
from django.http import JsonResponse
from datetime import datetime, date, timedelta
import time
from django.core.serializers.json import DjangoJSONEncoder
import json
# Импорт моделей
from .models import SearchHistory, CachedRoute, ApiLog
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Avg, Q
from django.db.models.functions import TruncHour, TruncDay
from django.core.cache import cache
from django.db.models import Case, When, FloatField
from django.utils import timezone
# Импорт форм
from .forms import RouteSearchForm
import numpy as np
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
                        routes_count=len(routes),
                        travel_mode=selected_mode
                    )

                except Exception as e:
                    error_message = f'Ошибка при поиске маршрута: {str(e)}'
                    print(f"Ошибка маршрутизации: {e}")
    routes_json = json.dumps(routes, cls=DjangoJSONEncoder, ensure_ascii=False)
    geocoded_points_json = json.dumps(geocoded_points, cls=DjangoJSONEncoder, ensure_ascii=False)
    # Передаем выбранный режим в контекст для сохранения в форме
    context = {
        'form': form,
        'routes': routes,
        'routes_json': routes_json, 
        'geocoded_points': geocoded_points,
        'geocoded_points_json': geocoded_points_json,
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
@staff_member_required
def analytics_dashboard(request):
    """Дашборд аналитики для администраторов"""
    
    # Используем кэширование для тяжёлых запросов (5 минут)
    cache_key = f"analytics_{date.today().strftime('%Y%m%d')}"
    cached_data = cache.get(cache_key)
    
    if cached_data and not request.GET.get('refresh'):
        context = cached_data
    else:
        # 1. Базовые метрики из SearchHistory
        total_searches = SearchHistory.objects.count()
        successful_searches = SearchHistory.objects.filter(is_successful=True).count()
        failed_searches = SearchHistory.objects.filter(is_successful=False).count()
        
        # 2. Статистика API из ApiLog за последние 7 дней
        week_ago = timezone.now() - timedelta(days=7)
        api_logs = ApiLog.objects.filter(timestamp__gte=week_ago)
        
        # 3. ТОП-10 популярных маршрутов
        top_routes = SearchHistory.objects.filter(
            is_successful=True
        ).values('start_query', 'end_query').annotate(
            count=Count('id'),
            avg_routes=Avg('routes_count')
        ).order_by('-count')[:10]
        
        # 4. Статистика по провайдерам
        provider_stats = ApiLog.objects.filter(
            timestamp__gte=week_ago
        ).values('provider').annotate(
            request_count=Count('id'),
            avg_response_time=Avg('response_time_ms'),
            success_rate=Avg(Case(
                When(response_status=200, then=100),
                default=0,
                output_field=FloatField()
            )),
            cache_hit_rate=Avg(Case(
                When(was_cached=True, then=100),
                default=0,
                output_field=FloatField()
            ))
        ).order_by('-request_count')
        
        # 5. Почасовая статистика за сегодня
        today = timezone.now().date()
        hourly_stats = ApiLog.objects.filter(
            timestamp__date=today
        ).annotate(
            hour=TruncHour('timestamp')
        ).values('hour').annotate(
            requests=Count('id'),
            avg_time=Avg('response_time_ms')
        ).order_by('hour')
        
        # 6. Статистика по типам маршрутов
        travel_mode_stats = SearchHistory.objects.filter(
            is_successful=True,
            timestamp__gte=week_ago
        ).extra(
            select={'travel_mode': "SUBSTRING(start_query FROM 'travel_mode=([^&]+)')"}
        ).values('travel_mode').annotate(
            count=Count('id')
        ).exclude(travel_mode__isnull=True)
        travel_mode_stats = []
        
        # 7. Конверсия (успешные поиски / всего)
        conversion_rate = (successful_searches / total_searches * 100) if total_searches > 0 else 0
        
        # 8. Самые частые ошибки
        common_errors = ApiLog.objects.filter(
            response_status__gte=400
        ).values('error_message').annotate(
            count=Count('id')
        ).exclude(error_message='').order_by('-count')[:5]
        
        # 9. Пиковые часы активности
        peak_hours = SearchHistory.objects.annotate(
            hour=TruncHour('timestamp')
        ).values('hour').annotate(
            searches=Count('id')
        ).order_by('-searches')[:5]
        
        # 10. Генерация графиков
        graphs = {}
        
        # График 1: ТОП маршрутов
        if top_routes:
            df_routes = pd.DataFrame(list(top_routes))
            if not df_routes.empty:
                graphs['top_routes'] = create_top_routes_chart(df_routes)
        
        # График 2: Статистика по провайдерам
        if provider_stats:
            df_providers = pd.DataFrame(list(provider_stats))
            if not df_providers.empty:
                graphs['provider_stats'] = create_provider_stats_chart(df_providers)
        
        # График 3: Почасовая активность
        if hourly_stats:
            df_hourly = pd.DataFrame(list(hourly_stats))
            if not df_hourly.empty:
                graphs['hourly_activity'] = create_hourly_chart(df_hourly)
        
        # График 4: Типы маршрутов
        if travel_mode_stats:
            df_modes = pd.DataFrame(list(travel_mode_stats))
            if not df_modes.empty:
                graphs['travel_modes'] = create_travel_modes_chart(df_modes)
        
        # График 5: Тренды по дням
        daily_trends = ApiLog.objects.filter(
            timestamp__gte=week_ago
        ).annotate(
            day=TruncDay('timestamp')
        ).values('day').annotate(
            requests=Count('id'),
            avg_time=Avg('response_time_ms')
        ).order_by('day')
        
        if daily_trends:
            df_daily = pd.DataFrame(list(daily_trends))
            if not df_daily.empty:
                graphs['daily_trends'] = create_daily_trends_chart(df_daily)
        
        # Собираем контекст
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
        }
        
        # Кэшируем на 5 минут
        cache.set(cache_key, context, 300)
    
    return render(request, 'core/admin/analytics_dashboard.html', context)


# Вспомогательные функции для создания графиков
def create_top_routes_chart(df):
    """Создает график ТОП маршрутов"""
    plt.figure(figsize=(14, 8))
    
    # Создаем подписи
    labels = []
    for _, row in df.iterrows():
        start = str(row['start_query'])[:15] + ('...' if len(str(row['start_query'])) > 15 else '')
        end = str(row['end_query'])[:15] + ('...' if len(str(row['end_query'])) > 15 else '')
        labels.append(f"{start}\n→ {end}")
    
    bars = plt.barh(range(len(df)), df['count'], color=plt.cm.viridis(np.linspace(0.2, 0.8, len(df))))
    plt.yticks(range(len(df)), labels, fontsize=9)
    plt.xlabel('Количество запросов', fontsize=12)
    plt.title('ТОП-10 популярных маршрутов', fontsize=14, fontweight='bold', pad=20)
    plt.gca().invert_yaxis()
    
    # Добавляем значения
    for i, (_, row) in enumerate(df.iterrows()):
        plt.text(row['count'] + max(df['count']) * 0.01, i, 
                f"{row['count']} запр.", 
                va='center', fontsize=10, fontweight='bold')
    
    plt.tight_layout()
    return save_plot_to_base64()


def create_provider_stats_chart(df):
    """Создает график статистики по провайдерам"""
    plt.figure(figsize=(12, 6))
    
    x = range(len(df))
    width = 0.35
    
    # Запросы
    bars1 = plt.bar(x, df['request_count'], width, label='Запросы', color='#4e79a7')
    
    # Среднее время ответа (на втором графике)
    ax2 = plt.gca().twinx()
    bars2 = ax2.plot(x, df['avg_response_time'], 'o-', color='#e15759', 
                    linewidth=3, markersize=8, label='Время ответа (мс)')
    
    plt.gca().set_xticks(x)
    plt.gca().set_xticklabels(df['provider'], rotation=45, ha='right')
    plt.gca().set_ylabel('Количество запросов', fontsize=12)
    ax2.set_ylabel('Среднее время ответа (мс)', fontsize=12)
    plt.title('Статистика по провайдерам API', fontsize=14, fontweight='bold', pad=20)
    
    # Легенда
    lines1, labels1 = plt.gca().get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    plt.gca().legend(lines1 + lines2, labels1 + labels2, loc='upper left')
    
    plt.tight_layout()
    return save_plot_to_base64()


def create_hourly_chart(df):
    """Создает график почасовой активности"""
    plt.figure(figsize=(14, 6))
    
    df['hour'] = pd.to_datetime(df['hour']).dt.hour
    df = df.sort_values('hour')
    
    # Два графика: запросы и время ответа
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)
    
    # График запросов
    bars = ax1.bar(df['hour'], df['requests'], color='#76b7b2', edgecolor='black')
    ax1.set_ylabel('Количество запросов', fontsize=12)
    ax1.set_title('Почасовая активность API (сегодня)', fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    
    # Добавляем значения на столбцы
    for bar in bars:
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                f'{int(height)}', ha='center', va='bottom', fontsize=9)
    
    # График времени ответа
    ax2.plot(df['hour'], df['avg_time'], 'o-', color='#edc949', 
            linewidth=2, markersize=8, markerfacecolor='white', markeredgewidth=2)
    ax2.set_xlabel('Час дня', fontsize=12)
    ax2.set_ylabel('Среднее время ответа (мс)', fontsize=12)
    ax2.grid(True, alpha=0.3)
    ax2.set_xticks(df['hour'])
    
    plt.tight_layout()
    return save_plot_to_base64()


def create_travel_modes_chart(df):
    """Создает график типов маршрутов"""
    plt.figure(figsize=(10, 8))
    
    # Круговой график
    colors = plt.cm.Set3(np.linspace(0, 1, len(df)))
    wedges, texts, autotexts = plt.pie(
        df['count'], 
        labels=df['travel_mode'],
        autopct='%1.1f%%',
        colors=colors,
        startangle=90,
        textprops={'fontsize': 11}
    )
    
    # Делаем подписи жирнее
    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontweight('bold')
    
    plt.title('Распределение по типам маршрутов', fontsize=14, fontweight='bold', pad=20)
    plt.tight_layout()
    return save_plot_to_base64()


def create_daily_trends_chart(df):
    """Создает график трендов по дням"""
    plt.figure(figsize=(14, 7))
    
    df['day'] = pd.to_datetime(df['day']).dt.strftime('%d.%m')
    df = df.sort_values('day')
    
    # Двойной график
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
    
    # Запросы (столбцы)
    bars = ax1.bar(df['day'], df['requests'], color='#59a14f', alpha=0.7)
    ax1.set_ylabel('Запросов в день', fontsize=12)
    ax1.set_title('Динамика запросов по дням', fontsize=14, fontweight='bold')
    ax1.tick_params(axis='x', rotation=45)
    ax1.grid(True, alpha=0.3, axis='y')
    
    # Время ответа (линия)
    ax2.plot(df['day'], df['avg_time'], 's-', color='#b07aa1', 
            linewidth=2, markersize=8, markerfacecolor='white', markeredgewidth=2)
    ax2.set_xlabel('Дата', fontsize=12)
    ax2.set_ylabel('Ср. время ответа (мс)', fontsize=12)
    ax2.grid(True, alpha=0.3)
    ax2.tick_params(axis='x', rotation=45)
    
    # Добавляем трендовую линию для времени ответа
    if len(df) > 2:
        x_numeric = range(len(df))
        z = np.polyfit(x_numeric, df['avg_time'], 1)
        p = np.poly1d(z)
        ax2.plot(df['day'], p(x_numeric), "r--", alpha=0.5, label='Тренд')
        ax2.legend()
    
    plt.tight_layout()
    return save_plot_to_base64()


def save_plot_to_base64():
    """Сохраняет текущий график в base64"""
    buffer = BytesIO()
    plt.savefig(buffer, format='png', bbox_inches='tight', dpi=100, facecolor='white')
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    plt.close()
    return image_base64