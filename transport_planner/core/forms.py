from django import forms

class RouteSearchForm(forms.Form):
    # Основные поля
    start_point = forms.CharField(
        label='Откуда',
        max_length=100,
        widget=forms.TextInput(attrs={
            'placeholder': 'Например: ЖД вокзал, Екатеринбург',
            'class': 'form-control',
            'id': 'start-point'
        })
    )
    
    end_point = forms.CharField(
        label='Куда', 
        max_length=100,
        widget=forms.TextInput(attrs={
            'placeholder': 'Например: Цирк, Екатеринбург',
            'class': 'form-control',
            'id': 'end-point'
        })
    )

    travel_mode = forms.ChoiceField(
        label='Тип маршрута',
        choices=[
            ('public', '🚌 Общественный транспорт'),
            ('car', '🚗 На машине (с пробками)'),
            ('pedestrian', '🚶 Пешком'),
            ('bicycle', '🚲 На велосипеде')
        ],
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'travel-mode',
            'onchange': 'toggleTransportFilters()'  
        }),
        initial='public'
    )

    TRANSPORT_CHOICES = [
        ('all', 'Все виды транспорта'),
        ('bus', '🚌 Автобус'),
        ('tram', '🚋 Трамвай'), 
        ('trolleybus', '🚎 Троллейбус'),
        ('subway', '🚇 Метро'),
        ('shuttle_bus', '🚐 Маршрутное такси'),
        ('train', '🚆 Электропоезд'),
        ('mcd', '🚄 МЦД'),
        ('mck', '🚆 МЦК'),
    ]
    
    TRANSFER_CHOICES = [
        ('any', 'Любое количество пересадок'),
        ('0', 'Без пересадок'),
        ('1', 'Не более 1 пересадки'),
        ('2', 'Не более 2 пересадок'),
        ('3', 'Не более 3 пересадок'),
    ]
    
    transport_types = forms.MultipleChoiceField(
        label='Типы транспорта',
        choices=TRANSPORT_CHOICES,
        required=False,
        widget=forms.SelectMultiple(attrs={
            'class': 'form-control',
            'id': 'transport-types',
            'style': 'height: 150px;'
        })
    )
    
    max_transfers = forms.ChoiceField(
        label='Максимальное количество пересадок',
        choices=TRANSFER_CHOICES,
        initial='any',
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'max-transfers'
        })
    )
    
    only_direct = forms.BooleanField(
        label='Только прямые маршруты',
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'only-direct'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        travel_mode = cleaned_data.get('travel_mode')
        if travel_mode != 'public':
            cleaned_data['transport_types'] = []
            cleaned_data['max_transfers'] = 'any'
            cleaned_data['only_direct'] = False
            
        return cleaned_data