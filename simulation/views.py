from django.shortcuts import render, redirect, get_object_or_404
from django.core.files.base import ContentFile

from .forms import ScenarioForm
from .models import Scenario, ResultFile
from .services import simulate_two_trucks

def scenario_list(request):
    qs = Scenario.objects.all().order_by('-created_at')
    return render(request, 'simulation/scenario_list.html', {'scenarios': qs})

def scenario_new(request):
    if request.method == 'POST':
        form = ScenarioForm(request.POST)
        if form.is_valid():
            scenario = form.save(commit=False)
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

def scenario_detail(request, scenario_id):
    scenario = get_object_or_404(Scenario, id=scenario_id)
    files = ResultFile.objects.filter(scenario=scenario).order_by('-created_at')
    return render(request, 'simulation/scenario_detail.html', {'scenario': scenario, 'files': files})
