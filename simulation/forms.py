from django import forms
from .models import Scenario

class ScenarioForm(forms.ModelForm):
    """Human-friendly form for configuring a QPRESS simulation."""

    placeholders = {
        "name": "Ej: Campaña QPRESS otoño",
        "volume_m3": "Volumen total de lodo a procesar (m³)",
        "Q_proc_m3h": "Caudal objetivo de alimentación en m³/h",
        "TS_in": "Sólidos totales de alimentación (ej: 0.05)",
        "TS_cake": "Sólidos totales esperados en torta (ej: 0.25)",
        "eta_captura": "Eficiencia de captura de sólidos (0-1)",
        "energy_cost_per_kwh": "CLP por kWh consumido",
        "transport_cost_per_km": "CLP por kilómetro de camión",
        "dehydration_cost_per_m3": "CLP cobrados por m³ deshidratado",
    }

    class Meta:
        model = Scenario
        fields = [
            'name','route_key','volume_m3','Q_proc_m3h','TS_in','TS_cake','eta_captura',
            'energy_cost_per_kwh','transport_cost_per_km','dehydration_cost_per_m3'
        ]
        labels = {
            'name': 'Nombre de la simulación',
            'route_key': 'Ruta logística',
            'volume_m3': 'Volumen a procesar (m³)',
            'Q_proc_m3h': 'Caudal (m³/h)',
            'TS_in': 'TS alimentación',
            'TS_cake': 'TS torta',
            'eta_captura': 'Eficiencia de captura',
            'energy_cost_per_kwh': 'Costo energía (CLP/kWh)',
            'transport_cost_per_km': 'Costo camión (CLP/km)',
            'dehydration_cost_per_m3': 'Servicio deshidratación (CLP/m³)',
        }
        help_texts = {
            'route_key': 'Selecciona la macro ruta donde operará la prensa móvil.',
            'volume_m3': 'Volumen inicial de lodos húmedos a deshidratar.',
            'Q_proc_m3h': 'Define el rango min–max esperado de alimentación a la máquina.',
            'TS_in': 'Fracción de sólidos totales en la entrada (típico 4–6%).',
            'TS_cake': 'Fracción de sólidos totales esperados en la torta (típico 22–28%).',
            'eta_captura': 'Captura estimada de sólidos en la tela (%).',
            'energy_cost_per_kwh': 'Costo energético vigente para la simulación.',
            'transport_cost_per_km': 'Tarifa por kilómetro recorrido por el camión (ida y vuelta).',
            'dehydration_cost_per_m3': 'Permite sensibilizar el cobro del servicio de deshidratación por m³.',
        }
        widgets = {
            'route_key': forms.Select(choices=Scenario.ROUTES, attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'volume_m3': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'step': 1}),
            'Q_proc_m3h': forms.NumberInput(attrs={'class': 'form-control', 'step': 0.1}),
            'TS_in': forms.NumberInput(attrs={'class': 'form-control', 'step': 0.001}),
            'TS_cake': forms.NumberInput(attrs={'class': 'form-control', 'step': 0.001}),
            'eta_captura': forms.NumberInput(attrs={'class': 'form-control', 'step': 0.01, 'max': 1}),
            'energy_cost_per_kwh': forms.NumberInput(attrs={'class': 'form-control', 'step': 1, 'min': 0}),
            'transport_cost_per_km': forms.NumberInput(attrs={'class': 'form-control', 'step': 10, 'min': 0}),
            'dehydration_cost_per_m3': forms.NumberInput(attrs={'class': 'form-control', 'step': 10, 'min': 0}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field, placeholder in self.placeholders.items():
            if field in self.fields:
                self.fields[field].widget.attrs.setdefault('placeholder', placeholder)
