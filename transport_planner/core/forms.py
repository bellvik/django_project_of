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
    
    traffic_level = forms.ChoiceField(
        label='Уровень пробок',
        choices=[
            ('light', 'Легкие (коэф. 1.0)'),
            ('medium', 'Средние (коэф. 1.3)'),
            ('heavy', 'Сильные (коэф. 1.7)')
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )