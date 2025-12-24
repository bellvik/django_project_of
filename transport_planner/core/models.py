# core/models.py
from django.db import models

class RouteRequest(models.Model):
    start_point = models.CharField(max_length=255)
    end_point = models.CharField(max_length=255)
    search_time = models.DateTimeField(auto_now_add=True)
    # Пока сохраняем просто текст запроса
