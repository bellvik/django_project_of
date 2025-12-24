# core/forms.py
from django import forms

class RouteSearchForm(forms.Form):
    start_point = forms.CharField(label='Откуда', max_length=100)
    end_point = forms.CharField(label='Куда', max_length=100)
    # Поле для выбора уровня пробок (заглушка)
    traffic_level = forms.ChoiceField(
        label='Уровень пробок',
        choices=[('light', 'Легкие'), ('medium', 'Средние'), ('heavy', 'Сильные')]
    )