
from django.db import models
import hashlib
import json
from django.utils import timezone

class CachedRoute(models.Model):
    """Модель для кэширования результатов маршрутов"""
    hash_key = models.CharField(max_length=64, unique=True, db_index=True)
    route_data = models.JSONField()  
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField() 

    def __str__(self):
        return f"Кэш от {self.created_at.strftime('%d.%m %H:%M')}"

    def save(self, *args, **kwargs):
        if not self.hash_key:
            self.hash_key = hashlib.md5(str(timezone.now()).encode()).hexdigest()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Кэшированный маршрут"
        verbose_name_plural = "Кэшированные маршруты"
        ordering = ['-created_at']

class ApiLog(models.Model):
    """Лог всех запросов к внешним API"""
    PROVIDER_CHOICES = [
        ('2gis_route', '2GIS (Маршруты)'),
        ('tomtom_geocode', 'TomTom (Геокод)'),
        ('tomtom_route', 'TomTom (Маршруты)'),
        ('stub', 'Заглушка'),
    ]
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    request_params = models.TextField(blank=True)  
    response_status = models.IntegerField()  
    response_time_ms = models.FloatField() 
    timestamp = models.DateTimeField(auto_now_add=True)
    was_cached = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)

    def __str__(self):
        return f"{self.get_provider_display()} - {self.response_status}"

class SearchHistory(models.Model):
    """Анонимная история поисковых запросов"""
    start_query = models.CharField(max_length=255)
    end_query = models.CharField(max_length=255)
    start_coords = models.CharField(max_length=50, blank=True)  # "56.838011,60.597465"
    end_coords = models.CharField(max_length=50, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    is_successful = models.BooleanField(default=True)
    routes_count = models.IntegerField(default=0) 
    travel_mode = models.CharField(
        max_length=20,
        default='public',
        verbose_name="Тип маршрута"
    )
    
    transport_types = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Типы транспорта"
    )
    
    max_transfers = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        verbose_name="Макс. пересадок"
    )
    def __str__(self):
        return f"{self.start_query} -> {self.end_query}"