import numpy as np, pandas as pd, io
from xlsxwriter.utility import xl_col_to_name
from datetime import datetime, timedelta
import matplotlib
matplotlib.use('Agg')               # render server
import matplotlib.pyplot as plt

ROUTES = {
    "NORTE": [
        {"from":"Puerto Varas","to":"Curarrehue","km":357.00,"hours":4.17},
        {"from":"Curarrehue","to":"Catripulli","km":13.43,"hours":0.22},
        {"from":"Catripulli","to":"Melipeuco","km":175.00,"hours":2.48},
        {"from":"Melipeuco","to":"Caburga 2","km":170.00,"hours":2.47},
        {"from":"Caburga 2","to":"Codihue","km":116.00,"hours":0.78},
    ],
    "SUR": [
        {"from":"Puerto Varas","to":"Hornopirén","km":126.00,"hours":2.43},
        {"from":"Hornopirén","to":"Pargua","km":167.00,"hours":2.83},
        {"from":"Pargua","to":"Reloncaví","km":43.96,"hours":0.73},
        {"from":"Reloncaví","to":"Centro Innovación ATC","km":11.87,"hours":0.20},
        {"from":"Centro Innovación ATC","to":"Agua Buena","km":80.30,"hours":1.34},
        {"from":"Agua Buena","to":"Aucar","km":61.47,"hours":1.02},
    ],
}

CENTERS = {
    "NORTE": [
        {"name":"Curarrehue","predio":"Villarrica","TS_in":0.05,"m3_demand":6.0,"batea_capacity_t":15.0},
        {"name":"Catripulli","predio":"Pucón","TS_in":0.05,"m3_demand":5.0,"batea_capacity_t":15.0},
        {"name":"Melipeuco","predio":"Cunco","TS_in":0.05,"m3_demand":6.0,"batea_capacity_t":15.0},
        {"name":"Caburga 2","predio":"Caburgua","TS_in":0.05,"m3_demand":4.0,"batea_capacity_t":15.0},
        {"name":"Codihue","predio":"Temuco","TS_in":0.05,"m3_demand":5.0,"batea_capacity_t":15.0},
    ],
    "SUR": [
        {"name":"Hornopirén","predio":"Calbuco","TS_in":0.05,"m3_demand":6.0,"batea_capacity_t":15.0},
        {"name":"Pargua","predio":"Chacao","TS_in":0.05,"m3_demand":5.0,"batea_capacity_t":15.0},
        {"name":"Reloncaví","predio":"Cochamó","TS_in":0.05,"m3_demand":5.0,"batea_capacity_t":15.0},
        {"name":"Centro Innovación ATC","predio":"Rilán","TS_in":0.05,"m3_demand":5.0,"batea_capacity_t":15.0},
        {"name":"Agua Buena","predio":"Chonchi","TS_in":0.05,"m3_demand":5.0,"batea_capacity_t":15.0},
        {"name":"Aucar","predio":"Quinchao","TS_in":0.05,"m3_demand":5.0,"batea_capacity_t":15.0},
    ],
}

def _tramo_min(tr, speed):
    return int(tr["hours"]*60) if tr.get("hours") is not None else int(tr["km"]/max(speed,1e-6)*60)

def _press_step(Q_m3h, TS_in, TS_cake, eta, rho, step_min):
    h = step_min/60
    mSS_in = Q_m3h * rho * TS_in
    mSS_cake = eta * mSS_in
    cake_tph = mSS_cake / TS_cake
    return mSS_cake*h, cake_tph*h  # (tDR_step, torta_step)

def simulate_two_trucks(
    days,
    route_key,
    volume_m3,
    Q_proc_m3h,
    TS_in,
    TS_cake,
    eta_captura,
    energy_cost_per_kwh=120.0,
    transport_cost_per_km=1300.0,
    dehydration_cost_per_m3=0.0,
    truck_speed_kmh=60.0,
    step_min=10,
    seed=123,
):
    np.random.seed(seed)
    rho = 1.0
    step = step_min
    target_volume = max(volume_m3, 0.0)
    volume_remaining = target_volume
    start_time = datetime(2025,10,1,8,0)

    route = ROUTES[route_key]
    centers = CENTERS[route_key]
    ordered_centers = [tr["to"] for tr in route]
    stock = {c["name"]: 0.0 for c in centers}
    cap   = {c["name"]: c.get("batea_capacity_t",15.0) for c in centers}
    dem   = {c["name"]: c.get("m3_demand",Q_proc_m3h) for c in centers}
    TSmap = {c["name"]: c.get("TS_in",TS_in) for c in centers}
    produced_cum = {c["name"]: 0.0 for c in centers}

    total_dem = sum(dem.values()) if dem else 0
    expected_cake_total_t = target_volume * rho * TS_in * eta_captura / max(TS_cake, 1e-6)
    target_alloc = {
        c["name"]: (
            expected_cake_total_t * (dem[c["name"]] / total_dem)
            if total_dem > 0 else expected_cake_total_t / len(centers)
        )
        for c in centers
    }

    # planta
    proc_state="DRIVE"; proc_time=_tramo_min(route[0], truck_speed_kmh); proc_ptr=0
    current_to=route[0]["to"]
    proc_km=route[0]["km"]; proc_hours_run=0; proc_kWh=0; proc_tDR=0; proc_cake=0

    # distribución
    dist_state="IDLE"; dist_time=0; dist_km=0.0; dist_ton_km=0.0; dist_trips=0
    dist_payload=0.0; dist_to=None; dist_leg_km=0.0

    rows=[]
    # permitir terminar distribución aún con rutas largas: tiempo de proceso + 72h buffer
    route_minutes = sum(_tramo_min(tr, truck_speed_kmh) for tr in route)
    max_minutes = ((target_volume / max(Q_proc_m3h, 1e-6)) * 60) + 72*60 + route_minutes
    max_steps = max(int(max_minutes/step), 1)
    s = 0
    while s < max_steps:
        tstamp = start_time + timedelta(minutes=s*step)
        s += 1

        # planta
        if proc_state=="DRIVE":
            proc_time -= step
            if proc_time<=0:
                proc_state="SETUP"; proc_time=10
        elif proc_state=="SETUP":
            proc_time -= step
            if proc_time<=0:
                proc_state="RUN"
        elif proc_state=="RUN":
            if volume_remaining <= 0:
                proc_state = "IDLE"
            else:
                Q_use = min(Q_proc_m3h, dem.get(current_to, Q_proc_m3h))
                volume_step = min(Q_use * step/60, volume_remaining)
                volume_remaining -= volume_step
                # recalcular caudal efectivo por si queda menos volumen
                Q_effective = volume_step * 60 / step if step > 0 else 0
                tDR, cake = _press_step(Q_effective, TSmap.get(current_to,TS_in), TS_cake, eta_captura, rho, step)
                free = cap[current_to]-stock[current_to]
                add = min(cake, max(free,0.0))
                stock[current_to]+=add
                produced_cum[current_to] += add
                frac = add/cake if cake>1e-9 else 0.0
                proc_cake += add; proc_tDR += tDR*frac; proc_kWh += 8*(tDR*frac); proc_hours_run += step/60
                target_cake = min(cap[current_to]*0.95, target_alloc.get(current_to, 0.0)*1.05)
                target_cake = max(target_cake, 0.5)  # asegurar salida aun con volúmenes bajos
                if produced_cum[current_to] >= target_cake and proc_ptr < len(route)-1:
                    proc_ptr += 1
                    current_to = route[proc_ptr]["to"]
                    proc_state="DRIVE"; proc_time=_tramo_min(route[proc_ptr], truck_speed_kmh)
                    proc_km += route[proc_ptr]["km"]
        elif proc_state=="IDLE":
            pass

        # distribución
        if dist_state=="IDLE":
            pick=None
            for nm in ordered_centers:
                if stock.get(nm,0.0) >= 1.0:
                    pick=nm; break
            if pick:
                km=0.0; tmin=0
                for tr in route:
                    km+=tr["km"]; tmin+=_tramo_min(tr, truck_speed_kmh)
                    if tr["to"]==pick: break
                dist_state="DRIVE_PICK"; dist_time=tmin; dist_to=pick; dist_km_ida=km; dist_leg_km=km
        elif dist_state=="DRIVE_PICK":
            dist_time -= step
            if dist_time<=0:
                dist_km += dist_leg_km
                dist_state="LOAD"; dist_time=30
        elif dist_state=="LOAD":
            dist_time -= step
            if dist_time<=0:
                dist_payload = stock[dist_to]; stock[dist_to]=0.0; dist_trips+=1
                km=dist_km_ida; tmin=int(km/truck_speed_kmh*60)
                dist_leg_km = km
                dist_time=tmin; dist_state="DRIVE_DROP"
                dist_ton_km += dist_payload * km
        elif dist_state=="DRIVE_DROP":
            dist_time -= step
            if dist_time<=0:
                dist_km += dist_leg_km
                dist_state="UNLOAD"; dist_time=30
        elif dist_state=="UNLOAD":
            dist_time -= step
            if dist_time<=0:
                dist_payload=0.0; dist_state="IDLE"

        row = {
            "time": tstamp, "proc_state": proc_state, "proc_center": current_to,
            "proc_km_cum": round(proc_km,2), "dist_state": dist_state,
            "dist_km_cum": round(dist_km,2), "dist_trips": dist_trips,
            "stock_total_t": round(sum(stock.values()),3)
        }
        for c in centers:
            row[f"stock_{c['name']}"] = round(stock[c['name']],3)
        rows.append(row)

        # condición de término: sin volumen pendiente y stock en cero y logística en reposo
        if volume_remaining <= 1e-6 and all(v <= 1e-3 for v in stock.values()) and dist_state=="IDLE" and proc_state in ("IDLE","DRIVE","SETUP"):
            if dist_state=="IDLE" and proc_state=="IDLE":
                break

    # costos
    CLP_per_kWh=energy_cost_per_kwh; CLP_per_km=transport_cost_per_km; CLP_per_ton_km=0
    energy_cost = proc_kWh * CLP_per_kWh
    trans_cost  = dist_km * CLP_per_km + dist_ton_km * CLP_per_ton_km
    dehydration_cost = target_volume * dehydration_cost_per_m3
    total_cost  = energy_cost + trans_cost + dehydration_cost

    kpis = {
        "Ruta": route_key, "Volumen procesado (m3)": round(target_volume,1), "Horas RUN planta": round(proc_hours_run,2),
        "Torta producida (t)": round(proc_cake,2), "tDR (t)": round(proc_tDR,2),
        "Energía (kWh)": round(proc_kWh,1), "Viajes distribución": dist_trips,
        "Km distribución": round(dist_km,1), "Km recolección": round(proc_km,1),
        "Costo energía (CLP)": round(energy_cost), "Costo transporte (CLP)": round(trans_cost),
        "Costo deshidratación (CLP)": round(dehydration_cost),
        "Costo total (CLP)": round(total_cost), "Stock final (t)": round(sum(stock.values()),2)
    }
    df_log = pd.DataFrame(rows)
    stock_cols = [c for c in df_log.columns if c.startswith("stock_")]
    df_stock = df_log[["time"]+stock_cols].copy()
    df_stock["stock_total_t"] = df_log["stock_total_t"]

    # gráfico PNG: total consolidado
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(df_log["time"], df_log["stock_total_t"], color="#0f3057", linewidth=2.4)
    ax.fill_between(df_log["time"], 0, df_log["stock_total_t"], color="#dbe8ff", alpha=0.5)
    ax.set_title("Stock total en pisciculturas y predios (t)")
    ax.set_xlabel("Tiempo"); ax.set_ylabel("Toneladas")
    ax.grid(True, linestyle='--', alpha=0.3)
    buf_png_total = io.BytesIO()
    fig.tight_layout(); fig.savefig(buf_png_total, format='png'); plt.close(fig)
    buf_png_total.seek(0)

    # gráfico PNG: detalle por piscicultura
    fig, ax = plt.subplots(figsize=(8, 4))
    for c in centers:
        label = c['name'] + (f" → {c.get('predio')}" if c.get('predio') else "")
        ax.plot(df_log["time"], df_log[f"stock_{c['name']}"] , linewidth=1.4, label=label)
    ax.set_title("Stock por piscicultura y predio (t)")
    ax.set_xlabel("Tiempo"); ax.set_ylabel("Toneladas")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(True, linestyle='--', alpha=0.3)
    buf_png_centers = io.BytesIO()
    fig.tight_layout(); fig.savefig(buf_png_centers, format='png'); plt.close(fig)
    buf_png_centers.seek(0)

    # Excel con KPI, Log y Stock
    buf_xlsx = io.BytesIO()
    # métricas adicionales para el Excel
    total_km = proc_km + dist_km
    costo_unitario_t = total_cost / max(proc_cake, 1e-6)
    costo_unitario_km = total_cost / max(total_km, 1e-6)
    costo_unitario_viaje = total_cost / max(dist_trips, 1) if dist_trips else 0
    energia_por_t = proc_kWh / max(proc_cake, 1e-6)
    costo_medio = (energy_cost + trans_cost + dehydration_cost) / 3

    df_kpi = pd.DataFrame([kpis])

    with pd.ExcelWriter(buf_xlsx, engine='xlsxwriter') as writer:
        df_kpi.to_excel(writer, sheet_name="KPI", startrow=2, index=False, header=False)
        df_log.to_excel(writer, sheet_name="Log", index=False)
        df_stock.to_excel(writer, sheet_name="Stock", index=False)

        workbook = writer.book

        # formatos base
        title_fmt = workbook.add_format({"bold": True, "font_size": 18})
        subtitle_fmt = workbook.add_format({"font_size": 11, "italic": True, "font_color": "#555555"})
        header_fmt = workbook.add_format({"bold": True, "bg_color": "#e8eef7", "border": 1})
        card_title_fmt = workbook.add_format({"bold": True, "font_color": "#0f3057"})
        card_value_fmt = workbook.add_format({"bold": True, "font_size": 12, "bg_color": "#f6f8fb", "border": 1, "align": "center"})
        currency_fmt = workbook.add_format({"num_format": "$ #,##0", "border": 1})
        number_fmt = workbook.add_format({"num_format": "#,##0.00", "border": 1})
        percent_fmt = workbook.add_format({"num_format": "0.0%", "border": 1})
        note_fmt = workbook.add_format({"text_wrap": True, "font_color": "#333333"})

        # hoja resumen visual
        resumen_ws = workbook.add_worksheet("Resumen")
        resumen_ws.merge_range("A1:F1", "Simulación logística - Resumen ejecutivo", title_fmt)
        resumen_ws.merge_range("A2:F2", "Costos y operación por ruta con desglose económico y métricas unitarias", subtitle_fmt)

        resumen_ws.write("A4", "Resumen rápido", header_fmt)
        cards = [
            ("Costo total (CLP)", total_cost, currency_fmt),
            ("Torta producida (t)", proc_cake, number_fmt),
            ("Energía (kWh)", proc_kWh, number_fmt),
            ("Horas RUN planta", proc_hours_run, number_fmt),
            ("Viajes distribución", dist_trips, number_fmt),
            ("Km totales", total_km, number_fmt),
        ]
        start_row = 5
        start_col = 0
        for i, (label, value, fmt) in enumerate(cards):
            r = start_row + (i // 3) * 2
            c = start_col + (i % 3) * 2
            resumen_ws.write(r, c, label, card_title_fmt)
            resumen_ws.write(r + 1, c, value, card_value_fmt)
            resumen_ws.set_column(c, c, 18)

        # desglose económico
        resumen_ws.write("A10", "Desglose económico", header_fmt)
        breakdown_headers = ["Concepto", "Monto (CLP)", "% del total", "Δ vs costo medio", "Explicación"]
        for col, h in enumerate(breakdown_headers):
            resumen_ws.write(10, col, h, header_fmt)

        breakdown_data = [
            ("Energía", energy_cost, energy_cost / total_cost if total_cost else 0, energy_cost - costo_medio, "Consumo energético en planta."),
            ("Transporte", trans_cost, trans_cost / total_cost if total_cost else 0, trans_cost - costo_medio, "Traslado (ida y vuelta) del camión."),
            ("Servicio deshidratación", dehydration_cost, dehydration_cost / total_cost if total_cost else 0, dehydration_cost - costo_medio, "Cobro por m³ procesado."),
            ("Total", total_cost, 1, total_cost - costo_medio, "Suma de energía + transporte + servicio."),
        ]
        for row_offset, (name, amount, pct, delta, desc) in enumerate(breakdown_data, start=11):
            resumen_ws.write(row_offset, 0, name)
            resumen_ws.write(row_offset, 1, amount, currency_fmt)
            resumen_ws.write(row_offset, 2, pct, percent_fmt)
            resumen_ws.write(row_offset, 3, delta, currency_fmt)
            resumen_ws.write(row_offset, 4, desc, note_fmt)

        resumen_ws.conditional_format(11, 1, 13, 1, {"type": "3_color_scale"})

        # métricas unitarias y normalizadas
        resumen_ws.write("A15", "Métricas unitarias", header_fmt)
        unit_headers = ["Indicador", "Valor", "Descripción"]
        for col, h in enumerate(unit_headers):
            resumen_ws.write(15, col, h, header_fmt)
        unit_rows = [
            ("Costo unitario por t", costo_unitario_t, "Costo total dividido por torta producida."),
            ("Costo unitario por km", costo_unitario_km, "Costo total normalizado por km recorridos (planta + distribución)."),
            ("Costo unitario por viaje", costo_unitario_viaje, "Costo promedio por viaje de distribución."),
            ("Energía por t", energia_por_t, "kWh consumidos por tonelada producida."),
        ]
        for row_offset, (name, value, desc) in enumerate(unit_rows, start=16):
            resumen_ws.write(row_offset, 0, name)
            resumen_ws.write(row_offset, 1, value, number_fmt)
            resumen_ws.write(row_offset, 2, desc, note_fmt)

        # datos de ruta para contexto y lectura sencilla
        resumen_ws.write("A21", "Tramos de la ruta", header_fmt)
        route_headers = ["Desde", "Hasta", "Km", "Horas"]
        for col, h in enumerate(route_headers):
            resumen_ws.write(21, col, h, header_fmt)
        for idx, tramo in enumerate(route, start=22):
            resumen_ws.write(idx, 0, tramo.get("from"))
            resumen_ws.write(idx, 1, tramo.get("to"))
            resumen_ws.write_number(idx, 2, tramo.get("km", 0), number_fmt)
            resumen_ws.write_number(idx, 3, tramo.get("hours", 0), number_fmt)

        # sparkline para stock total
        resumen_ws.write("F10", "Tendencia stock total")
        total_col = xl_col_to_name(len(stock_cols) + 1)
        resumen_ws.add_sparkline(
            "F11",
            {
                "range": f"Stock!${total_col}$2:${total_col}${len(df_stock)+1}",
                "type": "column",
            },
        )

        # gráfico de barras apiladas para composición de costos
        chart = workbook.add_chart({"type": "column", "subtype": "stacked"})
        chart.add_series({"name": "Energía", "values": f"=Resumen!$B$12:$B$12"})
        chart.add_series({"name": "Transporte", "values": f"=Resumen!$B$13:$B$13"})
        chart.add_series({"name": "Servicio", "values": f"=Resumen!$B$14:$B$14"})
        chart.set_title({"name": "Composición de costos"})
        chart.set_x_axis({"visible": False})
        chart.set_y_axis({"name": "CLP"})
        resumen_ws.insert_chart("D5", chart, {"x_scale": 1.1, "y_scale": 1.1})

        # notas y definiciones para lectores no técnicos
        resumen_ws.write("A29", "Notas y definiciones", header_fmt)
        resumen_ws.write("A30", "RUN: Horas efectivas de operación de planta.\nTDR: Toneladas de Densidad Real (sólidos recuperados).\nLos costos se muestran en CLP con separador de miles. Se incluye desglose energético, transporte y servicio de deshidratación, además de métricas unitarias para facilitar comparaciones entre rutas.", note_fmt)
        resumen_ws.set_column("A:A", 18)
        resumen_ws.set_column("B:B", 16)
        resumen_ws.set_column("C:C", 20)
        resumen_ws.set_column("D:D", 18)
        resumen_ws.set_column("E:E", 40)
        resumen_ws.set_column("F:F", 20)

        # hoja KPI con formato y filtros
        kpi_ws = writer.sheets["KPI"]
        for col, name in enumerate(df_kpi.columns):
            kpi_ws.write(0, col, name, header_fmt)
            description = {
                "Ruta": "Ruta seleccionada (NORTE o SUR)",
                "Volumen procesado (m3)": "Volumen total de lodos húmedos alimentados",
                "Horas RUN planta": "Horas efectivas de operación de planta",
                "Torta producida (t)": "Toneladas de torta producida",
                "tDR (t)": "Toneladas de sólidos recuperados",
                "Energía (kWh)": "Consumo energético acumulado",
                "Viajes distribución": "Cantidad de viajes realizados",
                "Km distribución": "Km recorridos en distribución",
                "Km recolección": "Km recorridos durante la recolección",
                "Costo energía (CLP)": "Costo asociado al consumo de energía",
                "Costo transporte (CLP)": "Costo asociado a transporte (CLP/km)",
                "Costo deshidratación (CLP)": "Cobro del servicio externo por volumen", 
                "Costo total (CLP)": "Suma de energía, transporte y servicio",
                "Stock final (t)": "Stock remanente al cierre",
            }.get(name, "")
            kpi_ws.write(1, col, description, note_fmt)
        kpi_ws.autofilter(0, 0, len(df_kpi)+2, len(df_kpi.columns)-1)
        kpi_ws.set_row(0, None, header_fmt)
        for col in range(len(df_kpi.columns)):
            kpi_ws.set_column(col, col, 18)
        kpi_ws.freeze_panes(2, 0)

        # hoja Log con filtros, formatos y columnas legibles
        log_ws = writer.sheets["Log"]
        log_ws.freeze_panes(1, 1)
        log_ws.autofilter(0, 0, len(df_log), len(df_log.columns)-1)
        log_ws.set_column(0, 0, 20)
        log_ws.set_column(1, 6, 14)
        log_ws.set_column(7, 7 + len(stock_cols), 14)
        log_ws.conditional_format(1, df_log.columns.get_loc("dist_km_cum"), len(df_log), df_log.columns.get_loc("dist_km_cum"), {"type": "3_color_scale"})
        log_ws.conditional_format(1, df_log.columns.get_loc("stock_total_t"), len(df_log), df_log.columns.get_loc("stock_total_t"), {"type": "data_bar", "bar_color": "#4caf50"})

        # hoja Stock con filtros y formato
        stock_ws = writer.sheets["Stock"]
        stock_ws.freeze_panes(1, 1)
        stock_ws.autofilter(0, 0, len(df_stock), len(df_stock.columns)-1)
        stock_ws.set_column(0, 0, 20)
        stock_ws.set_column(1, len(stock_cols)+1, 14)

    buf_xlsx.seek(0)

    return kpis, df_log, df_stock, buf_png_total, buf_png_centers, buf_xlsx
