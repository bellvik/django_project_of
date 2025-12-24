# core/views.py
from django.shortcuts import render
from django.conf import settings
from .forms import RouteSearchForm
from .services.routing_service import StubRoutingService, TomTomRoutingService, TwoGisRoutingService
from .services.traffic_service import StubTrafficService
from datetime import datetime

def home(request):
    routes = []
    form = RouteSearchForm()

    # Обрабатываем данные формы, если пользователь отправил запрос
    if request.method == 'GET' and 'start_point' in request.GET:
        form = RouteSearchForm(request.GET)
        
        if form.is_valid():
            # 1. Получаем данные из формы
            start = form.cleaned_data['start_point']
            end = form.cleaned_data['end_point']
            traffic_level = form.cleaned_data['traffic_level']
            
            # 2. ВЫБОР СЕРВИСА МАРШРУТИЗАЦИИ в зависимости от настройки
            if settings.USE_REAL_API:
                # Вариант А: Используем реальное API TomTom
                #router = TomTomRoutingService(api_key=settings.TOMTOM_API_KEY)
                
                # Вариант Б: ИЛИ проверяем 2GIS (раскомментировать одну из строк):
                 router = TwoGisRoutingService(demo_key=settings.TWOGIS_DEMO_KEY)
            else:
                # Используем заглушку
                router = StubRoutingService()
            
            # 3. Получаем варианты маршрутов от выбранного сервиса
            routes_data = router.get_routes(start, end)
            
            # 4. Используем сервис пробок (пока только заглушка)
            traffic_service = StubTrafficService()
            
            # 5. Корректируем время на основе пробок
            traffic_coef = traffic_service.get_traffic_coefficient(traffic_level, datetime.now())
            
            # 6. Обрабатываем каждый маршрут
            for route in routes_data.get('result', []):
                # Умножаем общее время на коэффициент пробок
                adjusted_time = route['total_time'] * traffic_coef
                route['adjusted_time'] = round(adjusted_time, 1)
                route['traffic_coef'] = traffic_coef
                routes.append(route)
    
    # 7. Передаем данные в шаблон
    return render(request, 'core/home.html', {
        'form': form,
        'routes': routes
    })
