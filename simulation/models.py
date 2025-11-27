from django.db import models
from django.contrib.auth.models import User

class Scenario(models.Model):
    ROUTES = (('NORTE','NORTE'), ('SUR','SUR'))
    name = models.CharField(max_length=120)
    route_key = models.CharField(max_length=10, choices=ROUTES)
    days = models.PositiveIntegerField(default=1)
    volume_m3 = models.FloatField(default=30.0)
    Q_proc_m3h = models.FloatField(default=6.0)
    TS_in = models.FloatField(default=0.05)
    TS_cake = models.FloatField(default=0.25)
    eta_captura = models.FloatField(default=0.97)
    energy_cost_per_kwh = models.FloatField(default=120.0)
    transport_cost_per_km = models.FloatField(default=1300.0)
    dehydration_cost_per_m3 = models.FloatField(default=0.0)
    kpis = models.JSONField(null=True, blank=True)

    created_by = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        permissions = [
            ('can_run_simulation', 'Puede ejecutar simulaciones QPRESS'),
        ]

    def __str__(self):
        return f"{self.name} ({self.route_key})"

    def kpi(self, key):
        return (self.kpis or {}).get(key)

    @property
    def kpi_torta(self):
        return self.kpi("Torta producida (t)")

    @property
    def kpi_costo_total(self):
        return self.kpi("Costo total (CLP)")

    @property
    def kpi_energia(self):
        return self.kpi("Energía (kWh)")

    @property
    def kpi_horas_run(self):
        return self.kpi("Horas RUN planta")

class ResultFile(models.Model):
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE)
    kind = models.CharField(max_length=20)  # 'excel' | 'grafico_total' | 'grafico_pisciculturas'
    file = models.FileField(upload_to='results/')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.kind} - {self.scenario.name}"
