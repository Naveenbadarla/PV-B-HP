# app.py
# E.ON Residential Flex Value Simulator
# PV + Battery + Heat Pump optimisation dashboard

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="E.ON Residential Flex Value Simulator",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>
    .main {
        background-color: #fafafa;
    }

    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 2rem;
    }

    .hero {
        padding: 24px 28px;
        border-radius: 24px;
        background: linear-gradient(135deg, #e2001a 0%, #9b0012 45%, #4d0010 100%);
        color: white;
        margin-bottom: 20px;
        box-shadow: 0 12px 30px rgba(0,0,0,0.16);
    }

    .hero h1 {
        font-size: 38px;
        margin-bottom: 6px;
        font-weight: 800;
    }

    .hero p {
        font-size: 18px;
        opacity: 0.95;
        margin-bottom: 0px;
    }

    .kpi-card {
        background: white;
        padding: 18px 20px;
        border-radius: 20px;
        box-shadow: 0 5px 18px rgba(0,0,0,0.08);
        border: 1px solid rgba(0,0,0,0.05);
        height: 132px;
    }

    .kpi-label {
        color: #666;
        font-size: 14px;
        margin-bottom: 8px;
    }

    .kpi-value {
        color: #111;
        font-size: 28px;
        font-weight: 800;
        margin-bottom: 5px;
    }

    .kpi-note {
        color: #777;
        font-size: 12px;
    }

    .section-card {
        background: white;
        padding: 22px;
        border-radius: 22px;
        box-shadow: 0 4px 18px rgba(0,0,0,0.07);
        border: 1px solid rgba(0,0,0,0.05);
        margin-bottom: 18px;
    }

    .red-title {
        color: #e2001a;
        font-weight: 800;
        font-size: 22px;
        margin-bottom: 10px;
    }

    .small-muted {
        color: #777;
        font-size: 13px;
    }

    .pill {
        display: inline-block;
        padding: 6px 12px;
        border-radius: 999px;
        background: #fff0f2;
        color: #e2001a;
        font-weight: 700;
        font-size: 13px;
        margin-right: 6px;
        border: 1px solid #ffd2d8;
    }

    .assumption-box {
        background: #fff7f8;
        border: 1px solid #ffd2d8;
        padding: 16px;
        border-radius: 16px;
        color: #222;
        font-size: 14px;
    }

    div[data-testid="stMetricValue"] {
        font-size: 26px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def format_eur(x):
    return f"€{x:,.0f}".replace(",", ".")


def format_kwh(x):
    return f"{x:,.0f} kWh".replace(",", ".")


def format_ct(x):
    return f"{x:.1f} ct/kWh"


def get_persona_defaults(persona):
    personas = {
        "PV+B small": {
            "household_load": 3500,
            "pv_kwp": 7,
            "battery_kwh": 5,
            "hp_kwh": 0,
            "hp_shift": 0.0,
            "pv_to_hp": 0.0,
            "battery_cycles": 150,
            "gross_ct": 8.0,
            "bonus_ct": 5.0,
            "cost_ct": 1.5,
        },
        "PV+B large": {
            "household_load": 4000,
            "pv_kwp": 10,
            "battery_kwh": 10,
            "hp_kwh": 0,
            "hp_shift": 0.0,
            "pv_to_hp": 0.0,
            "battery_cycles": 190,
            "gross_ct": 9.5,
            "bonus_ct": 5.0,
            "cost_ct": 1.5,
        },
        "HP only": {
            "household_load": 4000,
            "pv_kwp": 0,
            "battery_kwh": 0,
            "hp_kwh": 5000,
            "hp_shift": 0.35,
            "pv_to_hp": 0.0,
            "battery_cycles": 0,
            "gross_ct": 8.5,
            "bonus_ct": 5.0,
            "cost_ct": 1.3,
        },
        "PV+B+HP standard": {
            "household_load": 4000,
            "pv_kwp": 10,
            "battery_kwh": 10,
            "hp_kwh": 5000,
            "hp_shift": 0.35,
            "pv_to_hp": 0.15,
            "battery_cycles": 180,
            "gross_ct": 11.0,
            "bonus_ct": 6.0,
            "cost_ct": 1.7,
        },
        "Premium Flex Home": {
            "household_load": 5000,
            "pv_kwp": 12,
            "battery_kwh": 15,
            "hp_kwh": 7000,
            "hp_shift": 0.45,
            "pv_to_hp": 0.20,
            "battery_cycles": 220,
            "gross_ct": 13.0,
            "bonus_ct": 6.5,
            "cost_ct": 2.0,
        },
    }
    return personas[persona]


def calculate_flex_value(
    household_load,
    pv_kwp,
    battery_kwh,
    hp_kwh_year,
    hp_shiftable_share,
    pv_to_hp_share,
    battery_cycles_year,
    battery_efficiency,
    usable_soc_share,
    gross_value_ct,
    customer_bonus_ct,
    eon_cost_ct,
    overlap_share,
):
    usable_battery_kwh = battery_kwh * usable_soc_share

    battery_flex_kwh = usable_battery_kwh * battery_cycles_year * battery_efficiency

    hp_shift_flex_kwh = hp_kwh_year * hp_shiftable_share

    pv_to_hp_flex_kwh = hp_kwh_year * pv_to_hp_share if pv_kwp > 0 else 0

    raw_flex = battery_flex_kwh + hp_shift_flex_kwh + pv_to_hp_flex_kwh

    overlap_adjustment = raw_flex * overlap_share

    bonus_flex_kwh = max(0, raw_flex - overlap_adjustment)

    gross_value_eur = bonus_flex_kwh * gross_value_ct / 100
    customer_bonus_eur = bonus_flex_kwh * customer_bonus_ct / 100
    eon_cost_eur = bonus_flex_kwh * eon_cost_ct / 100
    eon_margin_eur = gross_value_eur - customer_bonus_eur - eon_cost_eur

    annual_pv_generation = pv_kwp * 950

    return {
        "usable_battery_kwh": usable_battery_kwh,
        "battery_flex_kwh": battery_flex_kwh,
        "hp_shift_flex_kwh": hp_shift_flex_kwh,
        "pv_to_hp_flex_kwh": pv_to_hp_flex_kwh,
        "overlap_adjustment": overlap_adjustment,
        "bonus_flex_kwh": bonus_flex_kwh,
        "gross_value_eur": gross_value_eur,
        "customer_bonus_eur": customer_bonus_eur,
        "eon_cost_eur": eon_cost_eur,
        "eon_margin_eur": eon_margin_eur,
        "annual_pv_generation": annual_pv_generation,
        "total_consumption": household_load + hp_kwh_year,
    }


def generate_day_profile(pv_kwp, battery_kwh, hp_kwh_year, household_load):
    """
    Creates a stylised 24h example day profile.
    This is not a full physical optimisation engine.
    It is a visually explainable dispatch model for stakeholder storytelling.
    """

    hours = np.arange(0, 24)

    # Relative price curve: low night, morning bump, midday low, evening peak
    price = (
        18
        + 10 * np.exp(-0.5 * ((hours - 7) / 1.8) ** 2)
        - 7 * np.exp(-0.5 * ((hours - 12) / 2.4) ** 2)
        + 24 * np.exp(-0.5 * ((hours - 18.5) / 2.0) ** 2)
    )
    price = np.maximum(price, 4)

    # PV curve
    if pv_kwp > 0:
        pv = pv_kwp * 0.75 * np.maximum(0, np.sin((hours - 6) / 12 * np.pi))
    else:
        pv = np.zeros_like(hours, dtype=float)

    # Household load curve
    base = household_load / 365 / 24
    home_load = (
        base
        + 0.25 * np.exp(-0.5 * ((hours - 7) / 1.5) ** 2)
        + 0.45 * np.exp(-0.5 * ((hours - 19) / 2.0) ** 2)
    )

    # Heat pump normal daily profile
    hp_daily_kwh = hp_kwh_year / 365 if hp_kwh_year > 0 else 0
    hp_normal_shape = (
        0.8 * np.exp(-0.5 * ((hours - 6) / 2.5) ** 2)
        + 0.7 * np.exp(-0.5 * ((hours - 19) / 2.5) ** 2)
        + 0.35
    )
    if hp_daily_kwh > 0:
        hp_normal = hp_daily_kwh * hp_normal_shape / hp_normal_shape.sum()
    else:
        hp_normal = np.zeros_like(hours, dtype=float)

    # Optimised HP: reduce evening, increase midday and cheap night
    hp_optimised = hp_normal.copy()
    if hp_kwh_year > 0:
        evening = (hours >= 16) & (hours <= 21)
        midday = (hours >= 10) & (hours <= 15)
        night = (hours >= 0) & (hours <= 5)

        reduced = hp_optimised[evening] * 0.65
        reduction_kwh = reduced.sum()
        hp_optimised[evening] -= reduced

        hp_optimised[midday] += reduction_kwh * 0.70 / midday.sum()
        hp_optimised[night] += reduction_kwh * 0.30 / night.sum()

    # Battery simplified rule:
    # charge from PV surplus and possibly cheap night, discharge morning/evening
    batt_capacity = battery_kwh * 0.8
    soc = []
    battery_charge = np.zeros_like(hours, dtype=float)
    battery_discharge = np.zeros_like(hours, dtype=float)

    current_soc = batt_capacity * 0.35 if batt_capacity > 0 else 0
    min_soc = batt_capacity * 0.15
    max_soc = batt_capacity * 0.95

    for i, h in enumerate(hours):
        demand_before_battery = home_load[i] + hp_optimised[i]
        pv_surplus = max(0, pv[i] - demand_before_battery)

        # Night cheap grid charge
        if batt_capacity > 0 and h in [1, 2, 3, 4] and current_soc < batt_capacity * 0.55:
            charge = min(0.6, max_soc - current_soc)
            battery_charge[i] += charge
            current_soc += charge

        # PV charging
        if batt_capacity > 0 and pv_surplus > 0:
            charge = min(pv_surplus, max_soc - current_soc, 2.2)
            battery_charge[i] += charge
            current_soc += charge

        # Discharge morning/evening
        if batt_capacity > 0 and ((6 <= h <= 9) or (16 <= h <= 21)):
            need = max(0, demand_before_battery - pv[i])
            discharge = min(need, current_soc - min_soc, 2.2)
            discharge = max(0, discharge)
            battery_discharge[i] = discharge
            current_soc -= discharge

        soc.append(current_soc)

    soc = np.array(soc)

    total_demand = home_load + hp_optimised
    grid_import = np.maximum(0, total_demand + battery_charge - pv - battery_discharge)
    pv_export = np.maximum(0, pv - total_demand - battery_charge + battery_discharge * 0)

    df = pd.DataFrame(
        {
            "Hour": hours,
            "Price_ct_kWh": price,
            "PV_generation_kWh": pv,
            "Home_load_kWh": home_load,
            "HP_normal_kWh": hp_normal,
            "HP_optimised_kWh": hp_optimised,
            "Battery_charge_kWh": battery_charge,
            "Battery_discharge_kWh": battery_discharge,
            "Battery_SoC_kWh": soc,
            "Grid_import_kWh": grid_import,
            "PV_export_kWh": pv_export,
        }
    )

    return df


def make_kpi_card(label, value, note):
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def make_timeline_figure(df):
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=df["Hour"],
            y=df["Price_ct_kWh"],
            name="Electricity price signal",
            mode="lines",
            line=dict(width=4, color="#e2001a"),
            yaxis="y1",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df["Hour"],
            y=df["PV_generation_kWh"],
            name="PV generation",
            mode="lines",
            fill="tozeroy",
            line=dict(width=3, color="#00a651"),
            opacity=0.55,
            yaxis="y2",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df["Hour"],
            y=df["Battery_SoC_kWh"],
            name="Battery SoC",
            mode="lines",
            line=dict(width=3, color="#174A7C"),
            yaxis="y2",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df["Hour"],
            y=df["Grid_import_kWh"],
            name="Grid import",
            mode="lines",
            line=dict(width=3, color="#444444", dash="dot"),
            yaxis="y2",
        )
    )

    zones = [
        (0, 5, "Cheap night", "rgba(23,74,124,0.08)"),
        (6, 9, "Morning peak", "rgba(255,150,40,0.09)"),
        (10, 15, "PV surplus", "rgba(0,166,81,0.09)"),
        (16, 21, "Evening peak", "rgba(226,0,26,0.10)"),
        (22, 24, "Reset", "rgba(120,80,180,0.08)"),
    ]

    for x0, x1, label, color in zones:
        fig.add_vrect(x0=x0, x1=x1, fillcolor=color, line_width=0)
        fig.add_annotation(
            x=(x0 + x1) / 2,
            y=1.08,
            yref="paper",
            text=label,
            showarrow=False,
            font=dict(size=12, color="#333"),
        )

    fig.update_layout(
        height=430,
        margin=dict(l=20, r=20, t=45, b=25),
        legend=dict(orientation="h", yanchor="bottom", y=1.16, xanchor="left", x=0),
        yaxis=dict(title="Price signal ct/kWh", side="left"),
        yaxis2=dict(
            title="Energy kWh / SoC kWh",
            overlaying="y",
            side="right",
            showgrid=False,
        ),
        xaxis=dict(title="Hour of day", tickmode="linear", dtick=2),
        hovermode="x unified",
        plot_bgcolor="white",
        paper_bgcolor="white",
    )

    return fig


def make_dispatch_figure(df):
    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=df["Hour"],
            y=df["PV_generation_kWh"],
            name="PV generation",
            marker_color="#00a651",
            opacity=0.55,
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df["Hour"],
            y=df["Home_load_kWh"],
            name="Home load",
            mode="lines",
            line=dict(width=3, color="#222222"),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df["Hour"],
            y=df["HP_optimised_kWh"],
            name="Heat pump optimised",
            mode="lines",
            line=dict(width=3, color="#e36c0a"),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df["Hour"],
            y=df["HP_normal_kWh"],
            name="Heat pump baseline",
            mode="lines",
            line=dict(width=2, color="#e36c0a", dash="dash"),
        )
    )

    fig.add_trace(
        go.Bar(
            x=df["Hour"],
            y=df["Battery_charge_kWh"],
            name="Battery charge",
            marker_color="#5dade2",
        )
    )

    fig.add_trace(
        go.Bar(
            x=df["Hour"],
            y=-df["Battery_discharge_kWh"],
            name="Battery discharge",
            marker_color="#174A7C",
        )
    )

    fig.update_layout(
        height=430,
        barmode="relative",
        margin=dict(l=20, r=20, t=45, b=25),
        legend=dict(orientation="h", yanchor="bottom", y=1.10, xanchor="left", x=0),
        xaxis=dict(title="Hour of day", tickmode="linear", dtick=2),
        yaxis=dict(title="kWh per hour"),
        hovermode="x unified",
        plot_bgcolor="white",
        paper_bgcolor="white",
    )

    return fig


def make_sankey_figure(results, pv_kwp, battery_kwh, hp_kwh_year):
    # Stylised annual flows based on calculated values.
    pv_gen = results["annual_pv_generation"]
    total_load = results["total_consumption"]
    battery_flex = results["battery_flex_kwh"]
    hp_shift = results["hp_shift_flex_kwh"]
    pv_hp = results["pv_to_hp_flex_kwh"]

    pv_to_home = min(pv_gen * 0.28, total_load * 0.30)
    pv_to_battery = min(pv_gen * 0.22, battery_flex * 1.15 if battery_kwh > 0 else 0)
    pv_to_hp = min(pv_gen * 0.18, pv_hp if hp_kwh_year > 0 else 0)
    pv_export = max(0, pv_gen - pv_to_home - pv_to_battery - pv_to_hp)

    grid_to_home = max(0, results["total_consumption"] * 0.35)
    grid_to_hp = max(0, hp_kwh_year - pv_to_hp - hp_shift * 0.20)
    grid_to_battery = max(0, battery_flex * 0.20 if battery_kwh > 0 else 0)

    battery_to_home = max(0, battery_flex * 0.55)
    battery_to_hp = max(0, battery_flex * 0.20 if hp_kwh_year > 0 else 0)
    battery_losses = max(0, battery_flex * 0.08)

    hp_to_heat = max(0, hp_kwh_year * 3.0)  # thermal output at COP around 3

    labels = [
        "PV generation",
        "Grid",
        "Battery",
        "Home load",
        "Heat pump",
        "PV export",
        "Battery losses",
        "Thermal storage / heat demand",
    ]

    label_index = {label: i for i, label in enumerate(labels)}

    flows = [
        ("PV generation", "Home load", pv_to_home, "#00a651"),
        ("PV generation", "Battery", pv_to_battery, "#00a651"),
        ("PV generation", "Heat pump", pv_to_hp, "#00a651"),
        ("PV generation", "PV export", pv_export, "#8ad29d"),
        ("Grid", "Home load", grid_to_home, "#777777"),
        ("Grid", "Heat pump", grid_to_hp, "#777777"),
        ("Grid", "Battery", grid_to_battery, "#777777"),
        ("Battery", "Home load", battery_to_home, "#174A7C"),
        ("Battery", "Heat pump", battery_to_hp, "#174A7C"),
        ("Battery", "Battery losses", battery_losses, "#b0bec5"),
        ("Heat pump", "Thermal storage / heat demand", hp_to_heat, "#e36c0a"),
    ]

    flows = [f for f in flows if f[2] > 1]

    fig = go.Figure(
        data=[
            go.Sankey(
                arrangement="snap",
                node=dict(
                    pad=18,
                    thickness=18,
                    line=dict(color="rgba(0,0,0,0.2)", width=0.5),
                    label=labels,
                    color=[
                        "#00a651",
                        "#666666",
                        "#174A7C",
                        "#333333",
                        "#e36c0a",
                        "#a5d6a7",
                        "#b0bec5",
                        "#ffb74d",
                    ],
                ),
                link=dict(
                    source=[label_index[s] for s, t, v, c in flows],
                    target=[label_index[t] for s, t, v, c in flows],
                    value=[v for s, t, v, c in flows],
                    color=[c for s, t, v, c in flows],
                ),
            )
        ]
    )

    fig.update_layout(
        height=520,
        margin=dict(l=10, r=10, t=20, b=10),
        font=dict(size=12),
        paper_bgcolor="white",
    )

    return fig


def make_waterfall_figure(results, gross_ct, bonus_ct, cost_ct):
    flex = results["bonus_flex_kwh"]

    da_id_ct = gross_ct * 0.36
    pv_self_ct = gross_ct * 0.20
    module3_ct = gross_ct * 0.18
    battery_ct = gross_ct * 0.14
    afrr_ct = gross_ct * 0.12

    x = [
        "DA/ID optimisation",
        "PV self-use uplift",
        "§14a / Module 3",
        "Battery arbitrage",
        "aFRR upside",
        "Customer bonus",
        "E.ON operating cost",
        "E.ON retained margin",
    ]

    y = [
        da_id_ct,
        pv_self_ct,
        module3_ct,
        battery_ct,
        afrr_ct,
        -bonus_ct,
        -cost_ct,
        results["eon_margin_eur"] / flex * 100 if flex > 0 else 0,
    ]

    measure = [
        "relative",
        "relative",
        "relative",
        "relative",
        "relative",
        "relative",
        "relative",
        "total",
    ]

    fig = go.Figure(
        go.Waterfall(
            name="Value stack",
            orientation="v",
            measure=measure,
            x=x,
            y=y,
            connector={"line": {"color": "rgba(0,0,0,0.25)"}},
            increasing={"marker": {"color": "#00a651"}},
            decreasing={"marker": {"color": "#e2001a"}},
            totals={"marker": {"color": "#174A7C"}},
        )
    )

    fig.update_layout(
        height=470,
        yaxis_title="ct/kWh",
        margin=dict(l=20, r=20, t=35, b=70),
        plot_bgcolor="white",
        paper_bgcolor="white",
    )

    return fig


def make_heatmap():
    profiles = [
        "PV+B small",
        "PV+B large",
        "HP only",
        "PV+B+HP standard",
        "Premium Flex Home",
    ]
    bonus_levels = [4, 5, 6, 7, 8, 10]

    matrix = []
    for p in profiles:
        d = get_persona_defaults(p)
        row = []
        for bonus in bonus_levels:
            r = calculate_flex_value(
                household_load=d["household_load"],
                pv_kwp=d["pv_kwp"],
                battery_kwh=d["battery_kwh"],
                hp_kwh_year=d["hp_kwh"],
                hp_shiftable_share=d["hp_shift"],
                pv_to_hp_share=d["pv_to_hp"],
                battery_cycles_year=d["battery_cycles"],
                battery_efficiency=0.90,
                usable_soc_share=0.80,
                gross_value_ct=d["gross_ct"],
                customer_bonus_ct=bonus,
                eon_cost_ct=d["cost_ct"],
                overlap_share=0.15,
            )
            row.append(r["eon_margin_eur"])
        matrix.append(row)

    heat_df = pd.DataFrame(matrix, index=profiles, columns=[f"{b} ct/kWh" for b in bonus_levels])

    fig = px.imshow(
        heat_df,
        text_auto=".0f",
        aspect="auto",
        color_continuous_scale=["#e2001a", "#fff3cd", "#00a651"],
        labels=dict(color="E.ON margin €/year"),
    )

    fig.update_layout(
        height=430,
        margin=dict(l=20, r=20, t=35, b=20),
        xaxis_title="Customer bonus level",
        yaxis_title="Customer profile",
        paper_bgcolor="white",
        plot_bgcolor="white",
    )

    return fig


# ============================================================
# HEADER
# ============================================================

st.markdown(
    """
    <div class="hero">
        <h1>⚡ E.ON Residential Flex Value Simulator</h1>
        <p>Interactive dashboard for PV + Battery + Heat Pump customer profiles, flex kWh, customer bonus, and E.ON retained value.</p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SIDEBAR INPUTS
# ============================================================

st.sidebar.markdown("## Customer Profile")

persona = st.sidebar.selectbox(
    "Select customer persona",
    [
        "PV+B small",
        "PV+B large",
        "HP only",
        "PV+B+HP standard",
        "Premium Flex Home",
    ],
    index=3,
)

defaults = get_persona_defaults(persona)

st.sidebar.markdown("---")
st.sidebar.markdown("## Asset assumptions")

household_load = st.sidebar.slider(
    "Household load kWh/year",
    min_value=1500,
    max_value=9000,
    value=int(defaults["household_load"]),
    step=250,
)

pv_kwp = st.sidebar.slider(
    "PV size kWp",
    min_value=0.0,
    max_value=20.0,
    value=float(defaults["pv_kwp"]),
    step=0.5,
)

battery_kwh = st.sidebar.slider(
    "Battery gross capacity kWh",
    min_value=0.0,
    max_value=25.0,
    value=float(defaults["battery_kwh"]),
    step=0.5,
)

hp_kwh_year = st.sidebar.slider(
    "Heat pump electricity kWh/year",
    min_value=0,
    max_value=12000,
    value=int(defaults["hp_kwh"]),
    step=250,
)

st.sidebar.markdown("---")
st.sidebar.markdown("## Flexibility assumptions")

usable_soc_share = st.sidebar.slider(
    "Battery usable SoC share",
    min_value=0.50,
    max_value=0.95,
    value=0.80,
    step=0.05,
)

battery_efficiency = st.sidebar.slider(
    "Battery round-trip efficiency",
    min_value=0.75,
    max_value=0.98,
    value=0.90,
    step=0.01,
)

battery_cycles_year = st.sidebar.slider(
    "Controllable battery cycles/year",
    min_value=0,
    max_value=350,
    value=int(defaults["battery_cycles"]),
    step=10,
)

hp_shiftable_share = st.sidebar.slider(
    "HP shiftable share",
    min_value=0.00,
    max_value=0.70,
    value=float(defaults["hp_shift"]),
    step=0.05,
)

pv_to_hp_share = st.sidebar.slider(
    "PV-to-HP absorption share of HP load",
    min_value=0.00,
    max_value=0.35,
    value=float(defaults["pv_to_hp"]),
    step=0.05,
)

overlap_share = st.sidebar.slider(
    "Overlap / double-counting adjustment",
    min_value=0.00,
    max_value=0.35,
    value=0.15,
    step=0.05,
)

st.sidebar.markdown("---")
st.sidebar.markdown("## Commercial assumptions")

gross_value_ct = st.sidebar.slider(
    "Gross flex value ct/kWh",
    min_value=3.0,
    max_value=20.0,
    value=float(defaults["gross_ct"]),
    step=0.5,
)

customer_bonus_ct = st.sidebar.slider(
    "Customer flex bonus ct/kWh",
    min_value=0.0,
    max_value=12.0,
    value=float(defaults["bonus_ct"]),
    step=0.5,
)

eon_cost_ct = st.sidebar.slider(
    "E.ON operating / risk cost ct/kWh",
    min_value=0.0,
    max_value=6.0,
    value=float(defaults["cost_ct"]),
    step=0.5,
)


# ============================================================
# CALCULATIONS
# ============================================================

results = calculate_flex_value(
    household_load=household_load,
    pv_kwp=pv_kwp,
    battery_kwh=battery_kwh,
    hp_kwh_year=hp_kwh_year,
    hp_shiftable_share=hp_shiftable_share,
    pv_to_hp_share=pv_to_hp_share,
    battery_cycles_year=battery_cycles_year,
    battery_efficiency=battery_efficiency,
    usable_soc_share=usable_soc_share,
    gross_value_ct=gross_value_ct,
    customer_bonus_ct=customer_bonus_ct,
    eon_cost_ct=eon_cost_ct,
    overlap_share=overlap_share,
)

day_df = generate_day_profile(
    pv_kwp=pv_kwp,
    battery_kwh=battery_kwh,
    hp_kwh_year=hp_kwh_year,
    household_load=household_load,
)


# ============================================================
# KPI CARDS
# ============================================================

k1, k2, k3, k4, k5 = st.columns(5)

with k1:
    make_kpi_card(
        "Bonus-qualifiable flex",
        format_kwh(results["bonus_flex_kwh"]),
        "Annual kWh eligible for customer bonus",
    )

with k2:
    make_kpi_card(
        "Customer bonus",
        format_eur(results["customer_bonus_eur"]),
        f"At {format_ct(customer_bonus_ct)}",
    )

with k3:
    make_kpi_card(
        "Gross system value",
        format_eur(results["gross_value_eur"]),
        f"At {format_ct(gross_value_ct)}",
    )

with k4:
    make_kpi_card(
        "E.ON net margin",
        format_eur(results["eon_margin_eur"]),
        "After bonus and operating cost",
    )

with k5:
    attractiveness = "High" if results["eon_margin_eur"] > 150 else "Medium" if results["eon_margin_eur"] > 50 else "Low"
    make_kpi_card(
        "Flex attractiveness",
        attractiveness,
        "Commercial segment score",
    )


# ============================================================
# TABS
# ============================================================

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    [
        "1 | Example Day",
        "2 | Energy Flows",
        "3 | Flex kWh Calculator",
        "4 | Commercial Offer",
        "5 | Segment Heatmap",
        "6 | Assumptions",
    ]
)


# ============================================================
# TAB 1 — EXAMPLE DAY
# ============================================================

with tab1:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="red-title">Example Day Optimisation</div>', unsafe_allow_html=True)

    st.markdown(
        """
        <span class="pill">00:00–05:00 Cheap night</span>
        <span class="pill">06:00–09:00 Morning peak</span>
        <span class="pill">10:00–15:00 PV surplus</span>
        <span class="pill">16:00–21:00 Evening peak</span>
        <span class="pill">22:00–24:00 Reset</span>
        """,
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns([1.1, 1])

    with c1:
        st.plotly_chart(make_timeline_figure(day_df), use_container_width=True)

    with c2:
        st.plotly_chart(make_dispatch_figure(day_df), use_container_width=True)

    st.markdown("</div>", unsafe_allow_html=True)

    c3, c4, c5, c6 = st.columns(4)

    with c3:
        st.metric("Example-day PV generation", f"{day_df['PV_generation_kWh'].sum():.1f} kWh")
    with c4:
        st.metric("Example-day grid import", f"{day_df['Grid_import_kWh'].sum():.1f} kWh")
    with c5:
        st.metric("Example-day PV export", f"{day_df['PV_export_kWh'].sum():.1f} kWh")
    with c6:
        st.metric("Example-day battery discharge", f"{day_df['Battery_discharge_kWh'].sum():.1f} kWh")

    st.markdown(
        """
        **How to read this:** the optimiser pushes heat-pump operation and battery charging into cheap or solar-rich hours, 
        then uses the battery and stored heat to reduce expensive evening grid import.
        """
    )


# ============================================================
# TAB 2 — ENERGY FLOWS
# ============================================================

with tab2:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="red-title">Annual Energy Flow Sankey</div>', unsafe_allow_html=True)

    st.plotly_chart(
        make_sankey_figure(results, pv_kwp, battery_kwh, hp_kwh_year),
        use_container_width=True,
    )

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        """
        The Sankey explains the physical logic: PV first serves the home, battery and heat pump; the grid is used mainly when prices are cheap or when comfort requires it; the battery and thermal storage help avoid expensive hours.
        """
    )


# ============================================================
# TAB 3 — FLEX KWH CALCULATOR
# ============================================================

with tab3:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="red-title">Bonus-Qualifiable Flex kWh Calculation</div>', unsafe_allow_html=True)

    calc_df = pd.DataFrame(
        {
            "Component": [
                "Battery qualified flex",
                "Heat pump shift flex",
                "PV-to-HP absorption flex",
                "Overlap / double-counting adjustment",
                "Bonus-qualifiable flex",
            ],
            "Formula logic": [
                "Usable battery capacity × controllable cycles × efficiency",
                "HP annual electricity × shiftable share",
                "HP annual electricity × PV-to-HP absorption share",
                "Raw flex × overlap adjustment",
                "Battery flex + HP shift flex + PV-to-HP flex - overlap",
            ],
            "kWh/year": [
                results["battery_flex_kwh"],
                results["hp_shift_flex_kwh"],
                results["pv_to_hp_flex_kwh"],
                -results["overlap_adjustment"],
                results["bonus_flex_kwh"],
            ],
        }
    )

    st.dataframe(
        calc_df.style.format({"kWh/year": "{:,.0f}"}),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        f"""
        <div class="assumption-box">
        <b>Recommended product interpretation:</b><br>
        For this profile, E.ON can pay the customer on approximately 
        <b>{format_kwh(results["bonus_flex_kwh"])}</b> of annual bonus-qualifiable flexibility.
        At <b>{format_ct(customer_bonus_ct)}</b>, this equals a customer bonus of 
        <b>{format_eur(results["customer_bonus_eur"])}</b> per year.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### Formula")

    st.code(
        """
Bonus flex kWh =
Battery qualified flex
+ HP shift flex
+ PV-to-HP absorption flex
- overlap adjustment

Battery qualified flex =
usable battery capacity × cycles/year × efficiency

HP shift flex =
HP annual kWh × HP shiftable share

PV-to-HP absorption flex =
HP annual kWh × PV-to-HP absorption share
        """,
        language="text",
    )


# ============================================================
# TAB 4 — COMMERCIAL OFFER
# ============================================================

with tab4:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="red-title">Commercial Offer and Value Waterfall</div>', unsafe_allow_html=True)

    c1, c2 = st.columns([1.1, 0.9])

    with c1:
        st.plotly_chart(
            make_waterfall_figure(results, gross_value_ct, customer_bonus_ct, eon_cost_ct),
            use_container_width=True,
        )

    with c2:
        offer_df = pd.DataFrame(
            {
                "Metric": [
                    "Bonus flex volume",
                    "Gross flex value",
                    "Customer bonus",
                    "E.ON operating / risk cost",
                    "E.ON retained margin",
                    "Suggested customer message",
                ],
                "Value": [
                    format_kwh(results["bonus_flex_kwh"]),
                    format_eur(results["gross_value_eur"]),
                    format_eur(results["customer_bonus_eur"]),
                    format_eur(results["eon_cost_eur"]),
                    format_eur(results["eon_margin_eur"]),
                    f"Earn around {format_eur(results['customer_bonus_eur'])}/year by letting E.ON optimise your system.",
                ],
            }
        )

        st.dataframe(offer_df, use_container_width=True, hide_index=True)

        if results["eon_margin_eur"] > 0:
            st.success("Commercially positive under current assumptions.")
        else:
            st.error("Commercially negative. Reduce customer bonus, increase gross value, or target stronger profiles.")

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("### Bonus sensitivity")

    sensitivity_rows = []
    for b in np.arange(3, 10.5, 0.5):
        gross_value = results["bonus_flex_kwh"] * gross_value_ct / 100
        customer_bonus = results["bonus_flex_kwh"] * b / 100
        cost = results["bonus_flex_kwh"] * eon_cost_ct / 100
        margin = gross_value - customer_bonus - cost

        sensitivity_rows.append(
            {
                "Customer bonus ct/kWh": b,
                "Customer payout €/year": customer_bonus,
                "E.ON net margin €/year": margin,
            }
        )

    sensitivity_df = pd.DataFrame(sensitivity_rows)

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=sensitivity_df["Customer bonus ct/kWh"],
            y=sensitivity_df["Customer payout €/year"],
            name="Customer payout",
            mode="lines+markers",
            line=dict(width=4, color="#e2001a"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=sensitivity_df["Customer bonus ct/kWh"],
            y=sensitivity_df["E.ON net margin €/year"],
            name="E.ON net margin",
            mode="lines+markers",
            line=dict(width=4, color="#174A7C"),
        )
    )
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    fig.update_layout(
        height=390,
        xaxis_title="Customer bonus ct/kWh",
        yaxis_title="€/year",
        hovermode="x unified",
        margin=dict(l=20, r=20, t=35, b=30),
        plot_bgcolor="white",
        paper_bgcolor="white",
    )

    st.plotly_chart(fig, use_container_width=True)


# ============================================================
# TAB 5 — SEGMENT HEATMAP
# ============================================================

with tab5:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="red-title">Segment Heatmap: Where Should E.ON Target First?</div>', unsafe_allow_html=True)

    st.plotly_chart(make_heatmap(), use_container_width=True)

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        """
        **Interpretation:** green segments are commercially attractive even at higher customer bonus levels.
        PV+B+HP and Premium Flex Homes typically become priority targets because heat-pump thermal flexibility increases controllable kWh.
        """
    )


# ============================================================
# TAB 6 — ASSUMPTIONS
# ============================================================

with tab6:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="red-title">Model Assumptions and Limitations</div>', unsafe_allow_html=True)

    assumptions = pd.DataFrame(
        {
            "Area": [
                "PV generation",
                "Battery flexibility",
                "Heat pump flexibility",
                "PV-to-HP absorption",
                "Overlap adjustment",
                "Gross flex value",
                "Customer bonus",
                "E.ON margin",
                "Example-day dispatch",
            ],
            "Current assumption": [
                "Annual PV generation approximated as PV kWp × 950 kWh/kWp/year.",
                "Battery flex = usable capacity × controllable cycles/year × round-trip efficiency.",
                "HP shift flex = annual HP electricity × shiftable share.",
                "PV-to-HP flex is approximated as a share of annual HP consumption.",
                "Used to avoid double counting between battery, HP shift and PV absorption.",
                "Represents monetisable value from DA/ID, PV self-use, §14a, battery arbitrage and aFRR upside.",
                "Paid on bonus-qualifiable flex kWh.",
                "Gross value minus customer bonus minus E.ON operating/risk cost.",
                "Stylised 24-hour example, not a full physical MILP optimisation.",
            ],
        }
    )

    st.dataframe(assumptions, use_container_width=True, hide_index=True)

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("### Next improvements for a production-grade model")

    st.markdown(
        """
        1. Replace stylised price curves with real DA and ID 15-minute German price data.
        2. Add PVGIS-based PV generation by postcode and roof orientation.
        3. Add real heat-pump thermal model with indoor temperature and hot-water tank constraints.
        4. Add §14a Module 3 grid-fee tables by DSO.
        5. Add aFRR capacity and activation simulation for aggregated pools.
        6. Add customer override and comfort compliance scoring.
        7. Add measured-baseline settlement to calculate true bonus-qualifiable flex kWh.
        """
    )


# ============================================================
# FOOTER
# ============================================================

st.markdown("---")
st.markdown(
    """
    <div style="text-align:center; color:#777; font-size:13px;">
    E.ON Residential Flex Value Simulator · Conceptual MVP · Designed for product strategy, stakeholder storytelling and early business-case testing
    </div>
    """,
    unsafe_allow_html=True,
)
