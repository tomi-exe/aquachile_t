from django import forms
from .models import Scenario

class ScenarioForm(forms.ModelForm):
    class Meta:
        model = Scenario
        fields = ['name','route_key','days','Q_proc_m3h','TS_in','TS_cake','eta_captura']
        widgets = {'route_key': forms.Select(choices=Scenario.ROUTES)}
