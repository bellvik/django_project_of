# core/forms.py
from django import forms

class RouteSearchForm(forms.Form):
    start_point = forms.CharField(
        label='Откуда',
        max_length=100,
        widget=forms.TextInput(attrs={
            'placeholder': 'Например: ЖД вокзал',
            'class': 'form-control',
            'id': 'start-point'
        })
    )
    
    end_point = forms.CharField(
        label='Куда', 
        max_length=100,
        widget=forms.TextInput(attrs={
            'placeholder': 'Например: Цирк',
            'class': 'form-control',
            'id': 'end-point'
        })
    )
  
    
    travel_mode = forms.ChoiceField(
        label='Тип маршрута',
        choices=[
            ('car', '🚗 На машине (с пробками)'),
            ('pedestrian', '🚶 Пешком'),
            ('bicycle', '🚲 На велосипеде')
        ],
        widget=forms.Select(attrs={'class': 'form-control'}),
        initial='car'  # Значение по умолчанию
    )