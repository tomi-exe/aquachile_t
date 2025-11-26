from django.db import models
from django.contrib.auth.models import User

class Scenario(models.Model):
    ROUTES = (('NORTE','NORTE'), ('SUR','SUR'))
    name = models.CharField(max_length=120)
    route_key = models.CharField(max_length=10, choices=ROUTES)
    days = models.PositiveIntegerField(default=3)
    Q_proc_m3h = models.FloatField(default=6.0)
    TS_in = models.FloatField(default=0.05)
    TS_cake = models.FloatField(default=0.25)
    eta_captura = models.FloatField(default=0.97)

    created_by = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        permissions = [
            ('can_run_simulation', 'Puede ejecutar simulaciones QPRESS'),
        ]

    def __str__(self):
        return f"{self.name} ({self.route_key})"

class ResultFile(models.Model):
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE)
    kind = models.CharField(max_length=20)  # 'excel' | 'grafico'
    file = models.FileField(upload_to='results/')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.kind} - {self.scenario.name}"
