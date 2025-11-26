import numpy as np, pandas as pd, io
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
        {"name":"Curarrehue","TS_in":0.05,"m3_demand":6.0,"batea_capacity_t":15.0},
        {"name":"Catripulli","TS_in":0.05,"m3_demand":5.0,"batea_capacity_t":15.0},
        {"name":"Melipeuco","TS_in":0.05,"m3_demand":6.0,"batea_capacity_t":15.0},
        {"name":"Caburga 2","TS_in":0.05,"m3_demand":4.0,"batea_capacity_t":15.0},
        {"name":"Codihue","TS_in":0.05,"m3_demand":5.0,"batea_capacity_t":15.0},
    ],
    "SUR": [
        {"name":"Hornopirén","TS_in":0.05,"m3_demand":6.0,"batea_capacity_t":15.0},
        {"name":"Pargua","TS_in":0.05,"m3_demand":5.0,"batea_capacity_t":15.0},
        {"name":"Reloncaví","TS_in":0.05,"m3_demand":5.0,"batea_capacity_t":15.0},
        {"name":"Centro Innovación ATC","TS_in":0.05,"m3_demand":5.0,"batea_capacity_t":15.0},
        {"name":"Agua Buena","TS_in":0.05,"m3_demand":5.0,"batea_capacity_t":15.0},
        {"name":"Aucar","TS_in":0.05,"m3_demand":5.0,"batea_capacity_t":15.0},
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

def simulate_two_trucks(days, route_key, Q_proc_m3h, TS_in, TS_cake, eta_captura,
                        truck_speed_kmh=60.0, step_min=10, seed=123):
    np.random.seed(seed)
    rho = 1.0
    step = step_min
    steps_total = int(days*24*60/step)
    start_time = datetime(2025,10,1,8,0)

    route = ROUTES[route_key]
    centers = CENTERS[route_key]
    ordered_centers = [tr["to"] for tr in route]
    stock = {c["name"]: 0.0 for c in centers}
    cap   = {c["name"]: c.get("batea_capacity_t",15.0) for c in centers}
    dem   = {c["name"]: c.get("m3_demand",Q_proc_m3h) for c in centers}
    TSmap = {c["name"]: c.get("TS_in",TS_in) for c in centers}

    # planta
    proc_state="DRIVE"; proc_time=_tramo_min(route[0], truck_speed_kmh); proc_ptr=0
    current_to=route[0]["to"]
    proc_km=route[0]["km"]; proc_hours_run=0; proc_kWh=0; proc_tDR=0; proc_cake=0

    # distribución
    dist_state="IDLE"; dist_time=0; dist_km=0.0; dist_ton_km=0.0; dist_trips=0
    dist_payload=0.0; dist_to=None

    rows=[]
    for s in range(steps_total):
        tstamp = start_time + timedelta(minutes=s*step)

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
            Q_use = min(Q_proc_m3h, dem.get(current_to, Q_proc_m3h))
            tDR, cake = _press_step(Q_use, TSmap.get(current_to,TS_in), TS_cake, eta_captura, rho, step)
            free = cap[current_to]-stock[current_to]
            add = min(cake, max(free,0.0))
            stock[current_to]+=add
            frac = add/cake if cake>1e-9 else 0.0
            proc_cake += add; proc_tDR += tDR*frac; proc_kWh += 8*(tDR*frac); proc_hours_run += step/60
            if stock[current_to] >= cap[current_to]*0.95 and proc_ptr < len(route)-1:
                proc_ptr += 1
                current_to = route[proc_ptr]["to"]
                proc_state="DRIVE"; proc_time=_tramo_min(route[proc_ptr], truck_speed_kmh)
                proc_km += route[proc_ptr]["km"]

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
                dist_state="DRIVE_PICK"; dist_time=tmin; dist_km+=km; dist_to=pick; dist_km_ida=km
        elif dist_state=="DRIVE_PICK":
            dist_time -= step
            if dist_time<=0:
                dist_state="LOAD"; dist_time=30
        elif dist_state=="LOAD":
            dist_time -= step
            if dist_time<=0:
                dist_payload = stock[dist_to]; stock[dist_to]=0.0; dist_trips+=1
                km=dist_km_ida; tmin=int(km/truck_speed_kmh*60)
                dist_km += km; dist_time=tmin; dist_state="DRIVE_DROP"
                dist_ton_km += dist_payload * km
        elif dist_state=="DRIVE_DROP":
            dist_time -= step
            if dist_time<=0:
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

    # costos
    CLP_per_kWh=120; CLP_per_km=800; CLP_per_ton_km=65
    energy_cost = proc_kWh * CLP_per_kWh
    trans_cost  = dist_km * CLP_per_km + dist_ton_km * CLP_per_ton_km
    total_cost  = energy_cost + trans_cost

    kpis = {
        "Ruta": route_key, "Días": days, "Horas RUN planta": round(proc_hours_run,2),
        "Torta producida (t)": round(proc_cake,2), "tDR (t)": round(proc_tDR,2),
        "Energía (kWh)": round(proc_kWh,1), "Viajes distribución": dist_trips,
        "Km distribución": round(dist_km,1), "Costo energía (CLP)": round(energy_cost),
        "Costo transporte (CLP)": round(trans_cost), "Costo total (CLP)": round(total_cost),
        "Stock final (t)": round(sum(stock.values()),2)
    }
    df_log = pd.DataFrame(rows)
    stock_cols = [c for c in df_log.columns if c.startswith("stock_")]
    df_stock = df_log[["time"]+stock_cols].copy()

    # gráfico PNG (stock total)
    fig, ax = plt.subplots(figsize=(6,3))
    ax.plot(df_log["time"], df_log["stock_total_t"])
    ax.set_title("Stock total en centros (t)")
    ax.set_xlabel("Tiempo"); ax.set_ylabel("t")
    buf_png = io.BytesIO()
    fig.tight_layout(); fig.savefig(buf_png, format='png'); plt.close(fig)
    buf_png.seek(0)

    # Excel con KPI, Log y Stock
    buf_xlsx = io.BytesIO()
    with pd.ExcelWriter(buf_xlsx, engine='xlsxwriter') as writer:
        df_kpi = pd.DataFrame([kpis])
        df_kpi.to_excel(writer, sheet_name="KPI", index=False)
        df_log.to_excel(writer, sheet_name="Log", index=False)
        df_stock.to_excel(writer, sheet_name="Stock", index=False)

        # formatting and README for better readability
        workbook = writer.book
        header_fmt = workbook.add_format(
            {"bold": True, "bg_color": "#1F4E78", "font_color": "#FFFFFF", "border": 1}
        )
        body_fmt = workbook.add_format({"border": 1})
        money_fmt = workbook.add_format({"border": 1, "num_format": "#,##0"})
        number_fmt = workbook.add_format({"border": 1, "num_format": "#,##0.00"})
        note_title_fmt = workbook.add_format(
            {"bold": True, "bg_color": "#E2F0D9", "border": 1}
        )
        note_fmt = workbook.add_format({"text_wrap": True, "border": 1})

        # KPI sheet styling
        kpi_ws = writer.sheets["KPI"]
        kpi_ws.freeze_panes(1, 1)
        kpi_ws.set_row(0, None, header_fmt)
        for col_num, col_name in enumerate(df_kpi.columns):
            width = max(18, len(col_name) + 2)
            kpi_ws.set_column(col_num, col_num, width, money_fmt if "Costo" in col_name else body_fmt)
        kpi_ws.set_column(df_kpi.columns.get_loc("Horas RUN planta"), df_kpi.columns.get_loc("Horas RUN planta"), 18, number_fmt)
        kpi_ws.set_column(df_kpi.columns.get_loc("Torta producida (t)"), df_kpi.columns.get_loc("Stock final (t)"), 18, number_fmt)

        info_start = len(df_kpi) + 2
        kpi_ws.write(info_start, 0, "Cómo leer este Excel", note_title_fmt)
        kpi_ws.merge_range(
            info_start, 1, info_start, 3, "KPI resume la ruta, días, producción, energía y costos consolidados.", note_fmt
        )
        kpi_ws.write(info_start + 1, 0, "Hoja Log", note_title_fmt)
        kpi_ws.merge_range(
            info_start + 1,
            1,
            info_start + 1,
            3,
            "Bitácora paso a paso con estados de proceso, viajes de distribución y stock total.",
            note_fmt,
        )
        kpi_ws.write(info_start + 2, 0, "Hoja Stock", note_title_fmt)
        kpi_ws.merge_range(
            info_start + 2,
            1,
            info_start + 2,
            3,
            "Trazabilidad del stock por centro para gráficos y anexos operativos.",
            note_fmt,
        )

        # README tab with a compact legend
        readme_ws = workbook.add_worksheet("README")
        writer.sheets["README"] = readme_ws
        readme_ws.set_column("A:A", 26)
        readme_ws.set_column("B:B", 72)
        readme_ws.write("A1", "Cómo usar este archivo", header_fmt)
        readme_ws.write(
            "B1",
            "Descarga lista para reportes: KPIs resumidos, bitácora logística y trazabilidad de stock.",
            note_fmt,
        )
        readme_ws.write_row("A3", ["Hoja", "Qué encontrarás"], header_fmt)
        readme_ws.write_row(
            "A4",
            [
                "KPI",
                "Resumen ejecutivo: ruta simulada, días, horas RUN, torta producida, tDR, energía, viajes y costos ",
            ],
            body_fmt,
        )
        readme_ws.write_row(
            "A5",
            ["Log", "Cronología de la operación: estados de proceso, kilómetros recorridos, stock total y viajes realizados."],
            body_fmt,
        )
        readme_ws.write_row(
            "A6",
            ["Stock", "Serie de tiempo por centro para graficar o anexar en informes de trazabilidad."],
            body_fmt,
        )
        readme_ws.write_row(
            "A7",
            [
                "Tip",
                "Usa el filtro automático de Excel en cada hoja para explorar horas críticas y validar el cumplimiento DS-30.",
            ],
            body_fmt,
        )
    buf_xlsx.seek(0)

    return kpis, df_log, df_stock, buf_png, buf_xlsx
