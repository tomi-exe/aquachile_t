from django import forms
from .models import Scenario

class ScenarioForm(forms.ModelForm):
    """Human-friendly form for configuring a QPRESS simulation."""

    placeholders = {
        "name": "Ej: Campaña QPRESS otoño",
        "days": "Duración en días de la campaña (ej: 4)",
        "Q_proc_m3h": "Caudal objetivo de alimentación en m³/h",
        "TS_in": "Sólidos totales de alimentación (ej: 0.05)",
        "TS_cake": "Sólidos totales esperados en torta (ej: 0.25)",
        "eta_captura": "Eficiencia de captura de sólidos (0-1)",
    }

    class Meta:
        model = Scenario
        fields = ['name','route_key','days','Q_proc_m3h','TS_in','TS_cake','eta_captura']
        labels = {
            'name': 'Nombre de la simulación',
            'route_key': 'Ruta logística',
            'days': 'Días de operación',
            'Q_proc_m3h': 'Caudal (m³/h)',
            'TS_in': 'TS alimentación',
            'TS_cake': 'TS torta',
            'eta_captura': 'Eficiencia de captura',
        }
        help_texts = {
            'route_key': 'Selecciona la macro ruta donde operará la prensa móvil.',
            'days': 'Cuántos días seguidos estará trabajando la cuadrilla.',
            'Q_proc_m3h': 'Define el rango min–max esperado de alimentación a la máquina.',
            'TS_in': 'Fracción de sólidos totales en la entrada (típico 4–6%).',
            'TS_cake': 'Fracción de sólidos totales esperados en la torta (típico 22–28%).',
            'eta_captura': 'Captura estimada de sólidos en la tela (%).',
        }
        widgets = {
            'route_key': forms.Select(choices=Scenario.ROUTES, attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'days': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'Q_proc_m3h': forms.NumberInput(attrs={'class': 'form-control', 'step': 0.1}),
            'TS_in': forms.NumberInput(attrs={'class': 'form-control', 'step': 0.001}),
            'TS_cake': forms.NumberInput(attrs={'class': 'form-control', 'step': 0.001}),
            'eta_captura': forms.NumberInput(attrs={'class': 'form-control', 'step': 0.01, 'max': 1}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field, placeholder in self.placeholders.items():
            if field in self.fields:
                self.fields[field].widget.attrs.setdefault('placeholder', placeholder)
