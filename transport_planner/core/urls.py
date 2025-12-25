from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('api/autocomplete/', views.autocomplete_api, name='autocomplete'),
    path('admin/clear-cache/', views.clear_cache_view, name='clear_cache'),
    path('api/status/', views.api_status, name='api_status'),
]