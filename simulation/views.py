from django.shortcuts import render, redirect, get_object_or_404
from django.core.files.base import ContentFile

from .forms import ScenarioForm
from .models import Scenario, ResultFile
from .services import simulate_two_trucks, ROUTES, CENTERS

def scenario_list(request):
    qs = Scenario.objects.all().order_by('-created_at')
    return render(request, 'simulation/scenario_list.html', {'scenarios': qs})

def scenario_new(request):
    if request.method == 'POST':
        form = ScenarioForm(request.POST)
        if form.is_valid():
            scenario = form.save(commit=False)
            scenario.days = 1
            scenario.save()

            kpis, df_log, df_stock, png, xlsx = simulate_two_trucks(
                days=scenario.days,
                volume_m3=scenario.volume_m3,
                route_key=scenario.route_key,
                Q_proc_m3h=scenario.Q_proc_m3h,
                TS_in=scenario.TS_in,
                TS_cake=scenario.TS_cake,
                eta_captura=scenario.eta_captura,
                energy_cost_per_kwh=scenario.energy_cost_per_kwh,
                transport_cost_per_km=scenario.transport_cost_per_km,
                dehydration_cost_per_m3=scenario.dehydration_cost_per_m3,
            )

            scenario.kpis = kpis
            scenario.save(update_fields=["kpis"])

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
    route_segments = ROUTES.get(scenario.route_key, [])
    centers = CENTERS.get(scenario.route_key, [])
    graph_file = files.filter(kind='grafico').first()
    excel_file = files.filter(kind='excel').first()
    kpi_values = scenario.kpis or {}
    kpi_summary = {
        'torta': kpi_values.get("Torta producida (t)"),
        'costo_total': kpi_values.get("Costo total (CLP)"),
        'energia': kpi_values.get("Energía (kWh)"),
        'horas_run': kpi_values.get("Horas RUN planta"),
    }
    return render(
        request,
        'simulation/scenario_detail.html',
        {
            'scenario': scenario,
            'files': files,
            'route_segments': route_segments,
            'centers': centers,
            'graph_file': graph_file,
            'excel_file': excel_file,
            'kpi_values': kpi_values,
            'kpi_summary': kpi_summary,
        },
    )
