from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.home, name='home'),
    path('api/autocomplete/', views.autocomplete_api, name='autocomplete'),
    path('admin/clear-cache/', views.clear_cache_view, name='clear_cache'),
    path('api/status/', views.api_status, name='api_status'),
    path('admin/analytics/', views.analytics_dashboard, name='analytics_dashboard'),
]
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)