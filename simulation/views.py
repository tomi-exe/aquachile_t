from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseForbidden
from django.core.files.base import ContentFile

from .forms import ScenarioForm
from .models import Scenario, ResultFile
from .services import simulate_two_trucks

@login_required
def scenario_list(request):
    if request.user.has_perm('simulation.can_run_simulation'):
        qs = Scenario.objects.all().order_by('-created_at')
    else:
        qs = Scenario.objects.filter(created_by=request.user).order_by('-created_at')
    return render(request, 'simulation/scenario_list.html', {'scenarios': qs})

@login_required
@permission_required('simulation.can_run_simulation', raise_exception=True)
def scenario_new(request):
    if request.method == 'POST':
        form = ScenarioForm(request.POST)
        if form.is_valid():
            scenario = form.save(commit=False)
            scenario.created_by = request.user
            scenario.save()

            kpis, df_log, df_stock, png, xlsx = simulate_two_trucks(
                days=scenario.days,
                route_key=scenario.route_key,
                Q_proc_m3h=scenario.Q_proc_m3h,
                TS_in=scenario.TS_in,
                TS_cake=scenario.TS_cake,
                eta_captura=scenario.eta_captura,
            )

            rf_x = ResultFile.objects.create(scenario=scenario, kind='excel')
            rf_x.file.save(f"{scenario.name}_resumen.xlsx", ContentFile(xlsx.read()))
            rf_p = ResultFile.objects.create(scenario=scenario, kind='grafico')
            rf_p.file.save(f"{scenario.name}_stock.png", ContentFile(png.read()))

            return redirect('scenario_detail', scenario_id=scenario.id)
    else:
        form = ScenarioForm()
    return render(request, 'simulation/scenario_form.html', {'form': form})

@login_required
def scenario_detail(request, scenario_id):
    scenario = get_object_or_404(Scenario, id=scenario_id)
    if not request.user.has_perm('simulation.can_run_simulation') and scenario.created_by != request.user:
        return HttpResponseForbidden("Sin permiso")
    files = ResultFile.objects.filter(scenario=scenario).order_by('-created_at')
    return render(request, 'simulation/scenario_detail.html', {'scenario': scenario, 'files': files})
