from django.contrib import admin
from .models import CachedRoute, ApiLog, SearchHistory
import json
from django.utils import timezone

@admin.register(CachedRoute)
class CachedRouteAdmin(admin.ModelAdmin):
    list_display = ('hash_key_short', 'created_at', 'expires_at')
    list_filter = ('created_at',)
    search_fields = ('hash_key',)
    readonly_fields = ('hash_key', 'route_data_prettified', 'created_at')
    
    def hash_key_short(self, obj):
        return f"{obj.hash_key[:12]}..." if obj.hash_key else "-"
    hash_key_short.short_description = "Хэш ключ"
    
    def route_data_prettified(self, obj):
        return json.dumps(obj.route_data, indent=2, ensure_ascii=False)
    route_data_prettified.short_description = "Данные маршрута (форматированные)"

@admin.register(ApiLog)
class ApiLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'provider', 'response_status', 'response_time_ms', 'was_cached', 'error_short')
    list_filter = ('provider', 'was_cached', 'timestamp')
    search_fields = ('request_params', 'error_message')
    readonly_fields = ('timestamp',)
    
    def error_short(self, obj):
        if obj.error_message:
            return obj.error_message[:50] + "..." if len(obj.error_message) > 50 else obj.error_message
        return ""
    error_short.short_description = "Ошибка"

@admin.register(SearchHistory)
class SearchHistoryAdmin(admin.ModelAdmin):
    list_display = ('start_query', 'end_query', 'timestamp', 'is_successful', 'routes_count')
    list_filter = ('is_successful', 'timestamp')
    search_fields = ('start_query', 'end_query')
