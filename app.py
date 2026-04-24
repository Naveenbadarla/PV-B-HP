      # app.py
# E.ON HomeFlex Optimisation Cockpit v3
# Adds Real German DA/ID Price ZIP Upload + Real Price Data Manager
# Requirements: streamlit, pandas, numpy, plotly

import io
import re
import zipfile
from datetime import date

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="E.ON HomeFlex Optimisation Cockpit",
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
    .block-container {padding-top: 1rem; padding-bottom: 2rem;}
    .hero {
        padding: 28px 32px; border-radius: 26px;
        background: linear-gradient(135deg, #e2001a 0%, #9b0012 48%, #2c0008 100%);
        color: white; margin-bottom: 22px; box-shadow: 0 14px 36px rgba(0,0,0,0.18);
    }
    .hero h1 {font-size: 42px; margin-bottom: 6px; font-weight: 850; letter-spacing: -0.6px;}
    .hero p {font-size: 18px; opacity: 0.95; margin-bottom: 0px;}
    .kpi-card {background: white; padding: 18px 20px; border-radius: 22px; box-shadow: 0 6px 20px rgba(0,0,0,0.08); border: 1px solid rgba(0,0,0,0.06); min-height: 138px;}
    .kpi-label {color: #666; font-size: 14px; margin-bottom: 8px; font-weight: 600;}
    .kpi-value {color: #111; font-size: 28px; font-weight: 850; margin-bottom: 5px;}
    .kpi-note {color: #777; font-size: 12px; line-height: 1.25;}
    .section-card {background: white; padding: 24px; border-radius: 24px; box-shadow: 0 5px 20px rgba(0,0,0,0.07); border: 1px solid rgba(0,0,0,0.05); margin-bottom: 18px;}
    .red-title {color: #e2001a; font-weight: 850; font-size: 24px; margin-bottom: 10px;}
    .pill {display: inline-block; padding: 7px 13px; border-radius: 999px; background: #fff0f2; color: #e2001a; font-weight: 800; font-size: 13px; margin-right: 6px; margin-bottom: 6px; border: 1px solid #ffd2d8;}
    .decision-green {padding: 18px 20px; border-radius: 20px; background: #ecfff2; border: 1px solid #b7efc5; color: #054a1c; font-weight: 800; font-size: 21px;}
    .decision-yellow {padding: 18px 20px; border-radius: 20px; background: #fff9e8; border: 1px solid #ffe0a3; color: #6b4500; font-weight: 800; font-size: 21px;}
    .decision-red {padding: 18px 20px; border-radius: 20px; background: #fff0f0; border: 1px solid #ffc0c0; color: #8b0000; font-weight: 800; font-size: 21px;}
    .story-card {background: #fff7f8; border: 1px solid #ffd2d8; padding: 18px; border-radius: 20px; color: #222; min-height: 180px;}
    .story-title {color: #e2001a; font-size: 19px; font-weight: 850; margin-bottom: 8px;}
    .mini-label {font-size: 12px; color: #777; font-weight: 700; text-transform: uppercase; letter-spacing: 0.3px;}
    .big-number {font-size: 34px; font-weight: 850; color: #111; line-height: 1.1;}
    .comfort-box {border-radius: 18px; padding: 16px; background: #f7fbff; border: 1px solid #d4e8ff;}
    div[data-testid="stMetricValue"] {font-size: 26px;}
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# FORMAT HELPERS
# ============================================================

def format_eur(x):
    return f"€{x:,.0f}".replace(",", ".")


def format_kwh(x):
    return f"{x:,.0f} kWh".replace(",", ".")


def format_ct(x):
    return f"{x:.1f} ct/kWh"


def pct(x):
    return f"{x:.0%}"


# ============================================================
# PERSONAS / PROFILES
# ============================================================

def get_persona_defaults(persona):
    personas = {
        "Solar Saver Family": {
            "short": "PV + small battery, mostly self-consumption",
            "problem": "High evening import despite rooftop PV.",
            "eon_action": "Shift PV surplus into battery and reduce expensive evening grid import.",
            "customer_benefit": "Simple bonus for smarter battery use.",
            "household_load": 3600, "pv_kwp": 7.5, "battery_kwh": 5,
            "hp_kwh": 0, "hp_shift": 0.0, "pv_to_hp": 0.0,
            "battery_cycles": 145, "gross_ct": 8.0, "bonus_ct": 4.5, "cost_ct": 1.4,
        },
        "Battery Optimiser Home": {
            "short": "Large PV + 10 kWh battery",
            "problem": "PV export is high and battery is not used against price peaks.",
            "eon_action": "Use DA/ID and grid-fee signals to time charge/discharge better.",
            "customer_benefit": "Higher value from existing battery without behaviour change.",
            "household_load": 4200, "pv_kwp": 10, "battery_kwh": 10,
            "hp_kwh": 0, "hp_shift": 0.0, "pv_to_hp": 0.0,
            "battery_cycles": 190, "gross_ct": 9.5, "bonus_ct": 5.0, "cost_ct": 1.5,
        },
        "HeatFlex Home": {
            "short": "Heat pump without PV/battery",
            "problem": "High winter heat-pump bills and peak-time consumption.",
            "eon_action": "Shift heat pump operation into cheap hours while protecting comfort.",
            "customer_benefit": "Earn bonus by making heat demand more flexible.",
            "household_load": 4000, "pv_kwp": 0, "battery_kwh": 0,
            "hp_kwh": 5200, "hp_shift": 0.35, "pv_to_hp": 0.0,
            "battery_cycles": 0, "gross_ct": 8.5, "bonus_ct": 5.0, "cost_ct": 1.3,
        },
        "HomeFlex Standard": {
            "short": "10 kWp PV + 10 kWh battery + heat pump",
            "problem": "The home exports cheap PV at noon and imports expensive power in evening/winter.",
            "eon_action": "Optimise PV, battery, HP and thermal storage together.",
            "customer_benefit": "Meaningful annual bonus with comfort protection.",
            "household_load": 4000, "pv_kwp": 10, "battery_kwh": 10,
            "hp_kwh": 5000, "hp_shift": 0.35, "pv_to_hp": 0.15,
            "battery_cycles": 180, "gross_ct": 11.0, "bonus_ct": 6.0, "cost_ct": 1.7,
        },
        "Premium Flex Home": {
            "short": "12 kWp PV + 15 kWh battery + large heat pump",
            "problem": "Large controllable energy volume needs orchestration across PV, battery and heat.",
            "eon_action": "Use multi-layer optimisation: DA/ID, PV absorption, §14a and future grid services.",
            "customer_benefit": "High-value flex bonus and future upside kicker.",
            "household_load": 5000, "pv_kwp": 12, "battery_kwh": 15,
            "hp_kwh": 7000, "hp_shift": 0.45, "pv_to_hp": 0.20,
            "battery_cycles": 220, "gross_ct": 13.0, "bonus_ct": 6.5, "cost_ct": 2.0,
        },
        "Winter Peak Home": {
            "short": "Large HP load, moderate PV, small battery",
            "problem": "Winter peak import is high and PV contribution is seasonally weak.",
            "eon_action": "Prioritise HP shift, cheap-hour preheating and §14a grid-fee avoidance.",
            "customer_benefit": "Bill relief during expensive winter periods.",
            "household_load": 4500, "pv_kwp": 6, "battery_kwh": 6,
            "hp_kwh": 8000, "hp_shift": 0.40, "pv_to_hp": 0.08,
            "battery_cycles": 150, "gross_ct": 10.5, "bonus_ct": 5.5, "cost_ct": 1.8,
        },
    }
    return personas[persona]


def get_dso_profile(dso):
    profiles = {
        "Westnetz": {"active_quarters": "Q1–Q4", "module3_factor": 1.00, "description": "High suitability: Module 3 available across the full year."},
        "LEW": {"active_quarters": "Q1–Q4", "module3_factor": 0.95, "description": "Strong suitability: broad time-variable grid-fee availability."},
        "NetzeBW": {"active_quarters": "Q1–Q4", "module3_factor": 0.90, "description": "Strong suitability: broad time-variable grid-fee availability."},
        "Bayernwerk": {"active_quarters": "Q2–Q3", "module3_factor": 0.55, "description": "Seasonal suitability: value concentrated in selected quarters."},
        "Avacon": {"active_quarters": "Q1 + Q4", "module3_factor": 0.60, "description": "Winter-focused suitability: useful for HP-heavy customers."},
        "Stadtwerke München": {"active_quarters": "Q1 + Q4", "module3_factor": 0.55, "description": "Winter-focused suitability, but lower annual availability."},
        "Generic DSO": {"active_quarters": "User-defined / unknown", "module3_factor": 0.70, "description": "Generic placeholder until exact DSO tariff windows are known."},
    }
    return profiles[dso]


def get_season_factors(season):
    return {
        "Winter day": {"pv_factor": 0.28, "hp_factor": 1.75, "price_evening_multiplier": 1.25, "description": "High heat demand, weak PV. HP shifting and §14a are most important."},
        "Spring sunny day": {"pv_factor": 1.10, "hp_factor": 0.85, "price_evening_multiplier": 1.00, "description": "Strong PV + remaining heat demand. Best PV-to-HP and battery story."},
        "Summer PV surplus day": {"pv_factor": 1.35, "hp_factor": 0.15, "price_evening_multiplier": 0.85, "description": "PV is high, HP space heating is low. Battery and export avoidance dominate."},
        "Autumn mixed day": {"pv_factor": 0.75, "hp_factor": 1.10, "price_evening_multiplier": 1.05, "description": "Balanced case with meaningful HP and battery flexibility."},
    }[season]


# ============================================================
# REAL PRICE ZIP HANDLING
# ============================================================

def _read_csv_from_zip(zf, member):
    with zf.open(member) as f:
        df = pd.read_csv(f, encoding="utf-8-sig")
    df.columns = [c.strip().replace("\ufeff", "") for c in df.columns]
    # Expected: timestamp, price (€/MWh)
    ts_col = [c for c in df.columns if "timestamp" in c.lower()][0]
    price_col = [c for c in df.columns if "price" in c.lower()][0]
    out = df[[ts_col, price_col]].copy()
    out.columns = ["timestamp", "price_eur_mwh"]
    out["timestamp"] = pd.to_datetime(out["timestamp"], errors="coerce")
    out["price_eur_mwh"] = pd.to_numeric(out["price_eur_mwh"], errors="coerce")
    out = out.dropna().sort_values("timestamp")
    out["price_ct_kwh"] = out["price_eur_mwh"] / 10.0
    return out


@st.cache_data(show_spinner=False)
def list_years_from_zip(zip_bytes):
    years = set()
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for n in zf.namelist():
            m = re.search(r"(spot|intraday)_price_(\d{4})\.csv$", n)
            if m:
                years.add(int(m.group(2)))
    return sorted(years)


@st.cache_data(show_spinner=False)
def load_price_year_from_zip(zip_bytes, year):
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
        spot_members = [n for n in names if n.endswith(f"spot_price_{year}.csv")]
        id_members = [n for n in names if n.endswith(f"intraday_price_{year}.csv")]
        if not spot_members or not id_members:
            raise ValueError(f"Could not find both spot_price_{year}.csv and intraday_price_{year}.csv inside ZIP.")
        spot = _read_csv_from_zip(zf, spot_members[0])
        intraday = _read_csv_from_zip(zf, id_members[0])

    # Expand / align DA hourly to 15-minute timestamps using forward fill.
    idx_15 = pd.date_range(intraday["timestamp"].min(), intraday["timestamp"].max(), freq="15min")

    da = spot.set_index("timestamp")[["price_eur_mwh", "price_ct_kwh"]].rename(
        columns={"price_eur_mwh": "da_eur_mwh", "price_ct_kwh": "da_ct_kwh"}
    )
    da = da.reindex(idx_15).ffill().reset_index().rename(columns={"index": "timestamp"})

    idp = intraday.set_index("timestamp")[["price_eur_mwh", "price_ct_kwh"]].rename(
        columns={"price_eur_mwh": "id_eur_mwh", "price_ct_kwh": "id_ct_kwh"}
    )
    idp = idp.reindex(idx_15).interpolate(limit_direction="both").reset_index().rename(columns={"index": "timestamp"})

    merged = pd.merge(da, idp, on="timestamp", how="inner")
    merged["date"] = merged["timestamp"].dt.date
    merged["hour_float"] = merged["timestamp"].dt.hour + merged["timestamp"].dt.minute / 60
    merged["spread_id_minus_da_ct"] = merged["id_ct_kwh"] - merged["da_ct_kwh"]
    return merged


def get_price_day_df(price_year_df, selected_date, price_signal_mode):
    day = price_year_df[price_year_df["date"] == selected_date].copy()
    if day.empty:
        return pd.DataFrame()
    if price_signal_mode == "DA only":
        day["price_signal_ct"] = day["da_ct_kwh"]
    elif price_signal_mode == "ID only":
        day["price_signal_ct"] = day["id_ct_kwh"]
    else:
        # Commercial storytelling: use ID for D-day optimisation, while showing DA hedge/spread separately.
        day["price_signal_ct"] = day["id_ct_kwh"]
    return day.reset_index(drop=True)


# ============================================================
# CALCULATION ENGINE
# ============================================================

def calculate_settlement_confidence(smart_meter, battery_telemetry, hp_submeter, indoor_temp, customer_override_rate):
    score = 45
    if smart_meter:
        score += 20
    if battery_telemetry:
        score += 12
    if hp_submeter:
        score += 13
    if indoor_temp:
        score += 8
    score -= customer_override_rate * 100 * 0.5
    return int(max(40, min(98, score)))


def calculate_comfort_score(hp_shiftable_share, max_hp_block_hours, customer_override_rate):
    score = 100
    if hp_shiftable_share > 0.45:
        score -= 7
    if max_hp_block_hours > 2.5:
        score -= 6
    score -= customer_override_rate * 100 * 0.7
    return int(max(65, min(99, score)))


def calculate_flex_value(
    household_load, pv_kwp, battery_kwh, hp_kwh_year, hp_shiftable_share, pv_to_hp_share,
    battery_cycles_year, battery_efficiency, usable_soc_share, gross_value_ct, customer_bonus_ct,
    eon_cost_ct, overlap_share, module3_enabled, module3_ct, dso_factor,
    afrr_enabled, afrr_capacity_kw, afrr_availability, afrr_value_eur_kw_year, afrr_customer_share,
):
    usable_battery_kwh = battery_kwh * usable_soc_share
    battery_flex_kwh = usable_battery_kwh * battery_cycles_year * battery_efficiency
    hp_shift_flex_kwh = hp_kwh_year * hp_shiftable_share
    pv_to_hp_flex_kwh = hp_kwh_year * pv_to_hp_share if pv_kwp > 0 and hp_kwh_year > 0 else 0

    raw_flex = battery_flex_kwh + hp_shift_flex_kwh + pv_to_hp_flex_kwh
    overlap_adjustment = raw_flex * overlap_share
    base_bonus_flex_kwh = max(0, raw_flex - overlap_adjustment)

    module3_uplift_eur = 0
    if module3_enabled:
        module3_eligible_kwh = min(base_bonus_flex_kwh, hp_shift_flex_kwh + battery_flex_kwh * 0.45)
        module3_uplift_eur = module3_eligible_kwh * module3_ct * dso_factor / 100

    afrr_gross_eur = afrr_customer_eur = afrr_eon_eur = 0
    if afrr_enabled:
        afrr_gross_eur = afrr_capacity_kw * afrr_availability * afrr_value_eur_kw_year
        afrr_customer_eur = afrr_gross_eur * afrr_customer_share
        afrr_eon_eur = afrr_gross_eur - afrr_customer_eur

    gross_value_eur = base_bonus_flex_kwh * gross_value_ct / 100 + module3_uplift_eur + afrr_gross_eur
    customer_bonus_eur = base_bonus_flex_kwh * customer_bonus_ct / 100 + afrr_customer_eur
    eon_cost_eur = base_bonus_flex_kwh * eon_cost_ct / 100
    eon_margin_eur = gross_value_eur - customer_bonus_eur - eon_cost_eur

    return {
        "usable_battery_kwh": usable_battery_kwh,
        "battery_flex_kwh": battery_flex_kwh,
        "hp_shift_flex_kwh": hp_shift_flex_kwh,
        "pv_to_hp_flex_kwh": pv_to_hp_flex_kwh,
        "raw_flex": raw_flex,
        "overlap_adjustment": overlap_adjustment,
        "bonus_flex_kwh": base_bonus_flex_kwh,
        "module3_uplift_eur": module3_uplift_eur,
        "afrr_gross_eur": afrr_gross_eur,
        "afrr_customer_eur": afrr_customer_eur,
        "afrr_eon_eur": afrr_eon_eur,
        "gross_value_eur": gross_value_eur,
        "customer_bonus_eur": customer_bonus_eur,
        "eon_cost_eur": eon_cost_eur,
        "eon_margin_eur": eon_margin_eur,
        "annual_pv_generation": pv_kwp * 950,
        "total_consumption": household_load + hp_kwh_year,
        "settlement_confidence": calculate_settlement_confidence(True, battery_kwh > 0, hp_kwh_year > 0, hp_kwh_year > 0, 0.06),
        "comfort_score": calculate_comfort_score(hp_shiftable_share, 2.0, 0.06),
    }


def recommend_offer(results, gross_ct, eon_cost_ct, target_margin_eur, min_customer_value_eur):
    flex = results["bonus_flex_kwh"]
    if flex <= 0:
        return {"recommended_bonus_ct": 0, "max_bonus_ct": 0, "decision": "Do not target", "decision_class": "decision-red", "reason": "No meaningful controllable flexible kWh."}

    max_bonus_ct = gross_ct - eon_cost_ct - (target_margin_eur / flex * 100)
    max_bonus_ct = max(0, max_bonus_ct)
    recommended_bonus_ct = min(max_bonus_ct, 6.5)
    recommended_bonus_ct = max(3.0, recommended_bonus_ct) if max_bonus_ct >= 3 else max_bonus_ct
    customer_value = flex * recommended_bonus_ct / 100

    if max_bonus_ct < 3 or customer_value < 100:
        decision, cls, reason = "Do not target yet", "decision-red", "Customer value or E.ON margin is too weak."
    elif customer_value < min_customer_value_eur:
        decision, cls, reason = "Needs bundling", "decision-yellow", "Economics are positive, but customer headline may be weak."
    else:
        decision, cls, reason = "Launch target", "decision-green", "Customer bonus and E.ON margin can both be positive."
    return {"recommended_bonus_ct": recommended_bonus_ct, "max_bonus_ct": max_bonus_ct, "decision": decision, "decision_class": cls, "reason": reason}


# ============================================================
# 15-MINUTE EXAMPLE DAY ENGINE
# ============================================================

def generate_stylised_price_day(season):
    sf = get_season_factors(season)
    t = np.arange(0, 24, 0.25)
    price = 18 + 10 * np.exp(-0.5 * ((t - 7) / 1.8) ** 2) - 7 * np.exp(-0.5 * ((t - 12) / 2.4) ** 2) + 24 * sf["price_evening_multiplier"] * np.exp(-0.5 * ((t - 18.5) / 2.0) ** 2)
    price = np.maximum(price, 4)
    return pd.DataFrame({"hour_float": t, "price_signal_ct": price, "da_ct_kwh": price, "id_ct_kwh": price, "spread_id_minus_da_ct": 0.0})


def generate_day_profile(pv_kwp, battery_kwh, hp_kwh_year, household_load, season, price_day=None):
    sf = get_season_factors(season)
    if price_day is None or price_day.empty:
        df = generate_stylised_price_day(season)
    else:
        df = price_day[["hour_float", "price_signal_ct", "da_ct_kwh", "id_ct_kwh", "spread_id_minus_da_ct"]].copy().reset_index(drop=True)

    t = df["hour_float"].values
    n = len(df)
    step_h = 0.25

    # PV profile, kWh per 15 min
    if pv_kwp > 0:
        pv_kw = pv_kwp * 0.75 * sf["pv_factor"] * np.maximum(0, np.sin((t - 6) / 12 * np.pi))
        pv = pv_kw * step_h
    else:
        pv = np.zeros(n)

    # Home load kWh per 15 min
    base_kw = household_load / 365 / 24
    home_kw = base_kw + 0.25 * np.exp(-0.5 * ((t - 7) / 1.5) ** 2) + 0.45 * np.exp(-0.5 * ((t - 19) / 2.0) ** 2)
    home_load = home_kw * step_h

    # Heat pump baseline kWh per 15 min
    hp_daily_kwh = hp_kwh_year / 365 * sf["hp_factor"] if hp_kwh_year > 0 else 0
    hp_shape = 0.8 * np.exp(-0.5 * ((t - 6) / 2.5) ** 2) + 0.7 * np.exp(-0.5 * ((t - 19) / 2.5) ** 2) + 0.35
    hp_baseline = hp_daily_kwh * hp_shape / hp_shape.sum() if hp_daily_kwh > 0 else np.zeros(n)

    # Optimised HP: reduce expensive windows, move to cheap/PV windows
    hp_optimised = hp_baseline.copy()
    if hp_kwh_year > 0 and hp_baseline.sum() > 0:
        price = df["price_signal_ct"].values
        expensive = price >= np.quantile(price, 0.75)
        cheap = price <= np.quantile(price, 0.30)
        pv_rich = pv >= np.quantile(pv, 0.70) if pv.max() > 0 else np.zeros(n, dtype=bool)
        target = cheap | pv_rich

        reduction = hp_optimised[expensive] * 0.58
        shift_energy = reduction.sum()
        hp_optimised[expensive] -= reduction
        if target.sum() > 0:
            # allocate extra HP operation to target periods weighted by PV + cheapness
            weights = np.where(target, 1, 0).astype(float)
            weights += np.where(pv_rich, 1.2, 0)
            weights += np.where(cheap, 0.8, 0)
            weights = weights / weights.sum()
            hp_optimised += shift_energy * weights

    # Battery control
    batt_capacity = battery_kwh * 0.8
    soc = []
    battery_charge = np.zeros(n)
    battery_discharge = np.zeros(n)
    current_soc = batt_capacity * 0.35 if batt_capacity > 0 else 0
    min_soc = batt_capacity * 0.15
    max_soc = batt_capacity * 0.95
    price = df["price_signal_ct"].values
    cheap = price <= np.quantile(price, 0.25)
    expensive = price >= np.quantile(price, 0.75)
    max_power_kW = 5.0
    max_energy_step = max_power_kW * step_h

    for i in range(n):
        demand_before_battery = home_load[i] + hp_optimised[i]
        pv_surplus = max(0, pv[i] - demand_before_battery)

        # Charge with PV surplus first
        if batt_capacity > 0 and pv_surplus > 0:
            charge = min(pv_surplus, max_soc - current_soc, max_energy_step)
            battery_charge[i] += max(0, charge)
            current_soc += max(0, charge)

        # Optional grid charge in cheap periods
        if batt_capacity > 0 and cheap[i] and current_soc < batt_capacity * 0.65:
            charge = min(max_energy_step * 0.65, max_soc - current_soc)
            battery_charge[i] += max(0, charge)
            current_soc += max(0, charge)

        # Discharge in expensive periods
        if batt_capacity > 0 and expensive[i]:
            need = max(0, demand_before_battery - pv[i])
            discharge = min(need, current_soc - min_soc, max_energy_step)
            battery_discharge[i] = max(0, discharge)
            current_soc -= max(0, discharge)

        soc.append(current_soc)

    total_demand = home_load + hp_optimised
    grid_import = np.maximum(0, total_demand + battery_charge - pv - battery_discharge)
    pv_export = np.maximum(0, pv - total_demand - battery_charge)

    # Baseline: thermostat HP + basic PV self-consumption battery
    baseline_battery_charge = np.zeros(n)
    baseline_battery_discharge = np.zeros(n)
    baseline_soc = batt_capacity * 0.35 if batt_capacity > 0 else 0
    baseline_grid_import = []
    baseline_pv_export = []

    for i in range(n):
        demand = home_load[i] + hp_baseline[i]
        surplus = max(0, pv[i] - demand)
        ch = min(surplus, max(0, max_soc - baseline_soc), max_energy_step) if batt_capacity > 0 else 0
        baseline_battery_charge[i] = ch
        baseline_soc += ch
        # simple evening discharge regardless of actual price
        dis = 0
        if batt_capacity > 0 and 17 <= t[i] <= 21:
            dis = min(max(0, demand - pv[i]), max(0, baseline_soc - min_soc), max_energy_step * 0.55)
        baseline_battery_discharge[i] = dis
        baseline_soc -= dis
        baseline_grid_import.append(max(0, demand - pv[i] - dis))
        baseline_pv_export.append(max(0, surplus - ch))

    out = df.copy()
    out["PV_generation_kWh"] = pv
    out["Home_load_kWh"] = home_load
    out["HP_baseline_kWh"] = hp_baseline
    out["HP_optimised_kWh"] = hp_optimised
    out["Battery_charge_kWh"] = battery_charge
    out["Battery_discharge_kWh"] = battery_discharge
    out["Battery_SoC_kWh"] = np.array(soc)
    out["Grid_import_kWh"] = grid_import
    out["PV_export_kWh"] = pv_export
    out["Baseline_grid_import_kWh"] = baseline_grid_import
    out["Baseline_pv_export_kWh"] = baseline_pv_export
    out["Baseline_battery_discharge_kWh"] = baseline_battery_discharge
    return out


# ============================================================
# CHARTS
# ============================================================

def make_kpi_card(label, value, note):
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-note">{note}</div>
    </div>
    """, unsafe_allow_html=True)


def make_price_manager_chart(day_df):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=day_df["hour_float"], y=day_df["da_ct_kwh"], name="DA / Spot", mode="lines", line=dict(width=3, color="#e2001a")))
    fig.add_trace(go.Scatter(x=day_df["hour_float"], y=day_df["id_ct_kwh"], name="Intraday", mode="lines", line=dict(width=3, color="#174A7C")))
    fig.add_trace(go.Bar(x=day_df["hour_float"], y=day_df["spread_id_minus_da_ct"], name="ID - DA spread", marker_color="#999999", opacity=0.35, yaxis="y2"))
    fig.update_layout(height=430, margin=dict(l=20, r=20, t=35, b=30), xaxis_title="Hour", yaxis_title="ct/kWh", yaxis2=dict(title="Spread ct/kWh", overlaying="y", side="right", showgrid=False), hovermode="x unified", plot_bgcolor="white", paper_bgcolor="white", legend=dict(orientation="h", y=1.08))
    return fig


def make_timeline_figure(df):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["hour_float"], y=df["price_signal_ct"], name="Optimisation price signal", mode="lines", line=dict(width=4, color="#e2001a"), yaxis="y1"))
    fig.add_trace(go.Scatter(x=df["hour_float"], y=df["PV_generation_kWh"], name="PV generation", mode="lines", fill="tozeroy", line=dict(width=3, color="#00a651"), opacity=0.55, yaxis="y2"))
    fig.add_trace(go.Scatter(x=df["hour_float"], y=df["Battery_SoC_kWh"], name="Battery SoC", mode="lines", line=dict(width=3, color="#174A7C"), yaxis="y2"))
    fig.add_trace(go.Scatter(x=df["hour_float"], y=df["Grid_import_kWh"], name="Optimised grid import", mode="lines", line=dict(width=3, color="#222", dash="dot"), yaxis="y2"))
    for x0, x1, label, color in [(0,5,"Cheap night","rgba(23,74,124,0.08)"),(6,9,"Morning peak","rgba(255,150,40,0.10)"),(10,15,"PV surplus","rgba(0,166,81,0.10)"),(16,21,"Evening peak","rgba(226,0,26,0.10)"),(22,24,"Reset","rgba(120,80,180,0.08)")]:
        fig.add_vrect(x0=x0, x1=x1, fillcolor=color, line_width=0)
        fig.add_annotation(x=(x0+x1)/2, y=1.08, yref="paper", text=label, showarrow=False, font=dict(size=12, color="#333"))
    fig.update_layout(height=430, margin=dict(l=20,r=20,t=50,b=30), legend=dict(orientation="h", y=1.17, x=0), yaxis=dict(title="Price ct/kWh"), yaxis2=dict(title="Energy / SoC", overlaying="y", side="right", showgrid=False), xaxis=dict(title="Hour", dtick=2), hovermode="x unified", plot_bgcolor="white", paper_bgcolor="white")
    return fig


def make_dispatch_figure(df):
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["hour_float"], y=df["PV_generation_kWh"], name="PV generation", marker_color="#00a651", opacity=0.50))
    fig.add_trace(go.Scatter(x=df["hour_float"], y=df["Home_load_kWh"], name="Home load", mode="lines", line=dict(width=3, color="#222")))
    fig.add_trace(go.Scatter(x=df["hour_float"], y=df["HP_optimised_kWh"], name="HP optimised", mode="lines", line=dict(width=4, color="#e36c0a")))
    fig.add_trace(go.Scatter(x=df["hour_float"], y=df["HP_baseline_kWh"], name="HP baseline", mode="lines", line=dict(width=2, color="#e36c0a", dash="dash")))
    fig.add_trace(go.Bar(x=df["hour_float"], y=df["Battery_charge_kWh"], name="Battery charge", marker_color="#5dade2"))
    fig.add_trace(go.Bar(x=df["hour_float"], y=-df["Battery_discharge_kWh"], name="Battery discharge", marker_color="#174A7C"))
    fig.update_layout(height=430, barmode="relative", margin=dict(l=20,r=20,t=50,b=30), legend=dict(orientation="h", y=1.14, x=0), xaxis=dict(title="Hour", dtick=2), yaxis=dict(title="kWh / 15 min"), hovermode="x unified", plot_bgcolor="white", paper_bgcolor="white")
    return fig


def make_before_after_figure(df):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["hour_float"], y=df["Baseline_grid_import_kWh"], name="Without optimisation: grid import", mode="lines", line=dict(width=4, color="#e2001a", dash="dash")))
    fig.add_trace(go.Scatter(x=df["hour_float"], y=df["Grid_import_kWh"], name="With optimisation: grid import", mode="lines", fill="tozeroy", line=dict(width=4, color="#174A7C")))
    fig.add_trace(go.Scatter(x=df["hour_float"], y=df["HP_baseline_kWh"], name="HP baseline", mode="lines", line=dict(width=2, color="#e36c0a", dash="dash")))
    fig.add_trace(go.Scatter(x=df["hour_float"], y=df["HP_optimised_kWh"], name="HP optimised", mode="lines", line=dict(width=3, color="#e36c0a")))
    fig.add_vrect(x0=16, x1=21, fillcolor="rgba(226,0,26,0.08)", line_width=0)
    fig.update_layout(height=480, title="Before vs After: Grid Import and Heat Pump Operation", margin=dict(l=20,r=20,t=55,b=30), legend=dict(orientation="h", y=1.08, x=0), xaxis=dict(title="Hour", dtick=2), yaxis=dict(title="kWh / 15 min"), hovermode="x unified", plot_bgcolor="white", paper_bgcolor="white")
    return fig


def make_sankey_figure(results, pv_kwp, battery_kwh, hp_kwh_year):
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
    hp_to_heat = max(0, hp_kwh_year * 3.0)
    labels = ["PV generation", "Grid", "Battery", "Home load", "Heat pump", "PV export", "Battery losses", "Thermal storage / heat demand"]
    idx = {label: i for i, label in enumerate(labels)}
    flows = [("PV generation","Home load",pv_to_home,"rgba(0,166,81,0.65)"),("PV generation","Battery",pv_to_battery,"rgba(0,166,81,0.65)"),("PV generation","Heat pump",pv_to_hp,"rgba(0,166,81,0.65)"),("PV generation","PV export",pv_export,"rgba(120,200,140,0.45)"),("Grid","Home load",grid_to_home,"rgba(110,110,110,0.45)"),("Grid","Heat pump",grid_to_hp,"rgba(110,110,110,0.45)"),("Grid","Battery",grid_to_battery,"rgba(110,110,110,0.45)"),("Battery","Home load",battery_to_home,"rgba(23,74,124,0.75)"),("Battery","Heat pump",battery_to_hp,"rgba(23,74,124,0.75)"),("Battery","Battery losses",battery_losses,"rgba(176,190,197,0.55)"),("Heat pump","Thermal storage / heat demand",hp_to_heat,"rgba(227,108,10,0.65)")]
    flows = [f for f in flows if f[2] > 1]
    fig = go.Figure(data=[go.Sankey(arrangement="snap", node=dict(pad=18, thickness=18, line=dict(color="rgba(0,0,0,0.2)", width=0.5), label=labels, color=["#00a651","#666","#174A7C","#333","#e36c0a","#a5d6a7","#b0bec5","#ffb74d"]), link=dict(source=[idx[s] for s,t,v,c in flows], target=[idx[t] for s,t,v,c in flows], value=[v for s,t,v,c in flows], color=[c for s,t,v,c in flows]))])
    fig.update_layout(height=540, margin=dict(l=10,r=10,t=20,b=10), font=dict(size=12), paper_bgcolor="white")
    return fig


def make_waterfall_figure(results, gross_ct, bonus_ct, cost_ct):
    flex = max(1, results["bonus_flex_kwh"])
    y = [gross_ct*0.34, gross_ct*0.20, gross_ct*0.18, gross_ct*0.14, gross_ct*0.14, -bonus_ct, -cost_ct, results["eon_margin_eur"] / flex * 100]
    x = ["DA/ID", "PV self-use", "§14a", "Battery", "aFRR", "Customer bonus", "E.ON cost", "E.ON margin"]
    fig = go.Figure(go.Waterfall(name="Value stack", measure=["relative"]*7+["total"], x=x, y=y, connector={"line":{"color":"rgba(0,0,0,0.25)"}}, increasing={"marker":{"color":"#00a651"}}, decreasing={"marker":{"color":"#e2001a"}}, totals={"marker":{"color":"#174A7C"}}))
    fig.update_layout(height=480, yaxis_title="ct/kWh", margin=dict(l=20,r=20,t=35,b=80), plot_bgcolor="white", paper_bgcolor="white")
    return fig


def make_heatmap():
    profiles = ["Solar Saver Family", "Battery Optimiser Home", "HeatFlex Home", "HomeFlex Standard", "Premium Flex Home", "Winter Peak Home"]
    bonus_levels = [4, 5, 6, 7, 8, 10]
    matrix = []
    for p in profiles:
        d = get_persona_defaults(p)
        row = []
        for bonus in bonus_levels:
            r = calculate_flex_value(d["household_load"], d["pv_kwp"], d["battery_kwh"], d["hp_kwh"], d["hp_shift"], d["pv_to_hp"], d["battery_cycles"], 0.90, 0.80, d["gross_ct"], bonus, d["cost_ct"], 0.15, True, 2.0, 0.8, False, 0, 0, 0, 0)
            row.append(r["eon_margin_eur"])
        matrix.append(row)
    heat_df = pd.DataFrame(matrix, index=profiles, columns=[f"{b} ct/kWh" for b in bonus_levels])
    fig = px.imshow(heat_df, text_auto=".0f", aspect="auto", color_continuous_scale=["#e2001a", "#fff3cd", "#00a651"], labels=dict(color="E.ON margin €/year"))
    fig.update_layout(height=460, margin=dict(l=20,r=20,t=35,b=20), xaxis_title="Customer bonus level", yaxis_title="Customer profile", paper_bgcolor="white", plot_bgcolor="white")
    return fig


# ============================================================
# HEADER
# ============================================================

st.markdown(
    """
    <div class="hero">
        <h1>⚡ E.ON HomeFlex Optimisation Cockpit</h1>
        <p>Now with real DA/Intraday ZIP upload, 15-minute price-based dispatch, flex settlement, §14a value, aFRR kicker and portfolio scaling.</p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SIDEBAR INPUTS
# ============================================================

st.sidebar.markdown("## 1. Customer profile")
persona = st.sidebar.selectbox("Select persona", ["Solar Saver Family", "Battery Optimiser Home", "HeatFlex Home", "HomeFlex Standard", "Premium Flex Home", "Winter Peak Home"], index=3)
defaults = get_persona_defaults(persona)
season = st.sidebar.selectbox("Season / example day", ["Winter day", "Spring sunny day", "Summer PV surplus day", "Autumn mixed day"], index=1)

st.sidebar.markdown("---")
st.sidebar.markdown("## 2. Real price data")
price_mode = st.sidebar.radio("Price mode", ["Stylised example prices", "Uploaded real DA/ID prices"], index=0)
uploaded_zip = st.sidebar.file_uploader("Upload price_for_dashboard.zip", type=["zip"])
price_signal_mode = st.sidebar.selectbox("Optimisation price signal", ["DA only", "ID only", "DA + ID correction"], index=2)

zip_bytes = None
available_years = []
selected_year = None
selected_date = None
price_year_df = pd.DataFrame()
price_day_df = pd.DataFrame()
price_data_status = "No ZIP uploaded"

if uploaded_zip is not None:
    zip_bytes = uploaded_zip.getvalue()
    try:
        available_years = list_years_from_zip(zip_bytes)
        selected_year = st.sidebar.selectbox("Select price year", available_years, index=0 if available_years else None)
        if selected_year:
            price_year_df = load_price_year_from_zip(zip_bytes, selected_year)
            dates = sorted(price_year_df["date"].unique())
            # Default to a spring day if available, else first date.
            preferred = date(selected_year, 4, 15) if date(selected_year, 4, 15) in dates else dates[0]
            selected_date = st.sidebar.selectbox("Select example date", dates, index=dates.index(preferred))
            price_day_df = get_price_day_df(price_year_df, selected_date, price_signal_mode)
            price_data_status = f"Loaded {selected_year}, {selected_date}"
    except Exception as e:
        st.sidebar.error(f"Could not read ZIP: {e}")
        price_mode = "Stylised example prices"

st.sidebar.markdown("---")
st.sidebar.markdown("## 3. Asset assumptions")
household_load = st.sidebar.slider("Household load kWh/year", 1500, 10000, int(defaults["household_load"]), 250)
pv_kwp = st.sidebar.slider("PV size kWp", 0.0, 25.0, float(defaults["pv_kwp"]), 0.5)
battery_kwh = st.sidebar.slider("Battery gross capacity kWh", 0.0, 30.0, float(defaults["battery_kwh"]), 0.5)
hp_kwh_year = st.sidebar.slider("Heat pump electricity kWh/year", 0, 14000, int(defaults["hp_kwh"]), 250)

st.sidebar.markdown("---")
st.sidebar.markdown("## 4. Flex assumptions")
usable_soc_share = st.sidebar.slider("Battery usable SoC share", 0.50, 0.95, 0.80, 0.05)
battery_efficiency = st.sidebar.slider("Battery round-trip efficiency", 0.75, 0.98, 0.90, 0.01)
battery_cycles_year = st.sidebar.slider("Controllable battery cycles/year", 0, 380, int(defaults["battery_cycles"]), 10)
hp_shiftable_share = st.sidebar.slider("HP shiftable share", 0.00, 0.70, float(defaults["hp_shift"]), 0.05)
pv_to_hp_share = st.sidebar.slider("PV-to-HP absorption share of HP load", 0.00, 0.40, float(defaults["pv_to_hp"]), 0.05)
overlap_share = st.sidebar.slider("Overlap / double-counting adjustment", 0.00, 0.40, 0.15, 0.05)

st.sidebar.markdown("---")
st.sidebar.markdown("## 5. Commercial assumptions")
gross_value_ct = st.sidebar.slider("Gross flex value ct/kWh", 3.0, 22.0, float(defaults["gross_ct"]), 0.5)
customer_bonus_ct = st.sidebar.slider("Customer flex bonus ct/kWh", 0.0, 14.0, float(defaults["bonus_ct"]), 0.5)
eon_cost_ct = st.sidebar.slider("E.ON operating / risk cost ct/kWh", 0.0, 7.0, float(defaults["cost_ct"]), 0.5)
target_margin_eur = st.sidebar.slider("Target E.ON margin floor €/customer/year", 0, 400, 120, 10)
min_customer_value_eur = st.sidebar.slider("Minimum attractive customer bonus €/year", 0, 500, 180, 10)

st.sidebar.markdown("---")
st.sidebar.markdown("## 6. §14a / aFRR")
module3_enabled = st.sidebar.toggle("Enable §14a / Module 3 uplift", value=True)
dso = st.sidebar.selectbox("DSO profile", ["Westnetz", "LEW", "NetzeBW", "Bayernwerk", "Avacon", "Stadtwerke München", "Generic DSO"], index=0)
dso_profile = get_dso_profile(dso)
module3_ct = st.sidebar.slider("Module 3 uplift ct/kWh", 0.0, 8.0, 2.0, 0.5)
afrr_enabled = st.sidebar.toggle("Enable aFRR upside kicker", value=False)
afrr_capacity_kw = st.sidebar.slider("Eligible aFRR capacity kW", 0.0, 5.0, 1.0, 0.25)
afrr_availability = st.sidebar.slider("aFRR availability", 0.0, 1.0, 0.45, 0.05)
afrr_value_eur_kw_year = st.sidebar.slider("aFRR gross value €/kW/year", 0, 200, 70, 5)
afrr_customer_share = st.sidebar.slider("Customer share of aFRR value", 0.0, 1.0, 0.40, 0.05)


# ============================================================
# CALCULATIONS
# ============================================================

results = calculate_flex_value(household_load, pv_kwp, battery_kwh, hp_kwh_year, hp_shiftable_share, pv_to_hp_share, battery_cycles_year, battery_efficiency, usable_soc_share, gross_value_ct, customer_bonus_ct, eon_cost_ct, overlap_share, module3_enabled, module3_ct, dso_profile["module3_factor"], afrr_enabled, afrr_capacity_kw, afrr_availability, afrr_value_eur_kw_year, afrr_customer_share)
recommendation = recommend_offer(results, gross_value_ct, eon_cost_ct, target_margin_eur, min_customer_value_eur)
use_real_prices = price_mode == "Uploaded real DA/ID prices" and uploaded_zip is not None and not price_day_df.empty
if use_real_prices:
    day_df = generate_day_profile(pv_kwp, battery_kwh, hp_kwh_year, household_load, season, price_day_df)
else:
    day_df = generate_day_profile(pv_kwp, battery_kwh, hp_kwh_year, household_load, season, None)


# ============================================================
# TOP KPIS
# ============================================================

k1, k2, k3, k4, k5 = st.columns(5)
with k1: make_kpi_card("Bonus-qualifiable flex", format_kwh(results["bonus_flex_kwh"]), "Annual kWh eligible for customer bonus")
with k2: make_kpi_card("Customer bonus", format_eur(results["customer_bonus_eur"]), f"Base {format_ct(customer_bonus_ct)} + optional kicker")
with k3: make_kpi_card("Gross system value", format_eur(results["gross_value_eur"]), f"At {format_ct(gross_value_ct)} incl. enabled uplifts")
with k4: make_kpi_card("E.ON net margin", format_eur(results["eon_margin_eur"]), "After customer bonus and operating/risk cost")
with k5: make_kpi_card("Price mode", "Real" if use_real_prices else "Stylised", price_data_status if use_real_prices else "Upload ZIP to activate real prices")


# ============================================================
# TABS
# ============================================================

tabs = st.tabs(["1 | Executive", "2 | Price Manager", "3 | Customer Story", "4 | Example Day", "5 | Before vs After", "6 | Energy Flows", "7 | Flex Settlement", "8 | Commercial Offer", "9 | §14a + aFRR", "10 | Portfolio", "11 | Heatmap", "12 | Assumptions"])

with tabs[0]:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="red-title">Executive Recommendation</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1.2, 1, 1])
    with c1:
        st.markdown(f'<div class="{recommendation["decision_class"]}">{recommendation["decision"]}</div>', unsafe_allow_html=True)
        st.write(recommendation["reason"])
    with c2:
        st.markdown('<div class="mini-label">Customer headline</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="big-number">{format_eur(results["customer_bonus_eur"])}/year</div>', unsafe_allow_html=True)
        st.caption("Expected payout under selected assumptions")
    with c3:
        st.markdown('<div class="mini-label">E.ON retained value</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="big-number">{format_eur(results["eon_margin_eur"])}/year</div>', unsafe_allow_html=True)
        st.caption("Estimated net margin per customer")
    st.markdown("---")
    c4, c5, c6, c7 = st.columns(4)
    with c4: st.metric("Recommended bonus", format_ct(recommendation["recommended_bonus_ct"]))
    with c5: st.metric("Max affordable bonus", format_ct(recommendation["max_bonus_ct"]))
    with c6: st.metric("Settlement confidence", f"{results['settlement_confidence']}%")
    with c7: st.metric("Comfort score", f"{results['comfort_score']}/100")
    st.markdown("</div>", unsafe_allow_html=True)
    st.info(f"Using **{'real uploaded DA/ID prices' if use_real_prices else 'stylised example prices'}**. Select the Price Manager tab to inspect DA, ID and spreads.")

with tabs[1]:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="red-title">Real Price Data Manager</div>', unsafe_allow_html=True)
    if uploaded_zip is None:
        st.warning("Upload `price_for_dashboard.zip` in the sidebar to activate real DA/Intraday prices.")
    else:
        st.success(f"ZIP loaded. Available years: {', '.join(map(str, available_years))}")
        st.write(f"Selected: **{selected_year}** / **{selected_date}** / signal: **{price_signal_mode}**")
        st.plotly_chart(make_price_manager_chart(price_day_df), use_container_width=True)
        p1, p2, p3, p4 = st.columns(4)
        with p1: st.metric("DA avg", format_ct(price_day_df["da_ct_kwh"].mean()))
        with p2: st.metric("ID avg", format_ct(price_day_df["id_ct_kwh"].mean()))
        with p3: st.metric("Min 15-min price", format_ct(price_day_df["price_signal_ct"].min()))
        with p4: st.metric("Max 15-min price", format_ct(price_day_df["price_signal_ct"].max()))
        st.markdown("### Cheapest charging windows")
        cheapest = price_day_df.nsmallest(10, "price_signal_ct")[["timestamp", "da_ct_kwh", "id_ct_kwh", "price_signal_ct", "spread_id_minus_da_ct"]] if "timestamp" in price_day_df.columns else price_day_df.nsmallest(10, "price_signal_ct")
        st.dataframe(cheapest, use_container_width=True, hide_index=True)
        st.markdown("### Most expensive avoidance windows")
        expensive = price_day_df.nlargest(10, "price_signal_ct")[["timestamp", "da_ct_kwh", "id_ct_kwh", "price_signal_ct", "spread_id_minus_da_ct"]] if "timestamp" in price_day_df.columns else price_day_df.nlargest(10, "price_signal_ct")
        st.dataframe(expensive, use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)

with tabs[2]:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown(f'<div class="red-title">{persona}</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.markdown(f'<div class="story-card"><div class="story-title">Customer profile</div><b>{defaults["short"]}</b><br><br>Load: <b>{format_kwh(household_load)}</b><br>PV: <b>{pv_kwp:.1f} kWp</b><br>Battery: <b>{battery_kwh:.1f} kWh</b><br>HP: <b>{format_kwh(hp_kwh_year)}</b></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="story-card"><div class="story-title">Customer problem</div>{defaults["problem"]}</div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="story-card"><div class="story-title">E.ON action</div>{defaults["eon_action"]}</div>', unsafe_allow_html=True)
    with c4: st.markdown(f'<div class="story-card"><div class="story-title">Customer benefit</div>{defaults["customer_benefit"]}<br><br><span style="font-size:28px;font-weight:850;">{format_eur(results["customer_bonus_eur"])}/year</span></div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    st.info(f"**{season}:** {get_season_factors(season)['description']}")

with tabs[3]:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="red-title">Example Day Optimisation</div>', unsafe_allow_html=True)
    st.markdown('<span class="pill">00:00–05:00 Cheap night</span><span class="pill">06:00–09:00 Morning peak</span><span class="pill">10:00–15:00 PV surplus</span><span class="pill">16:00–21:00 Evening peak</span><span class="pill">22:00–24:00 Reset</span>', unsafe_allow_html=True)
    c1, c2 = st.columns([1.1, 1])
    with c1: st.plotly_chart(make_timeline_figure(day_df), use_container_width=True)
    with c2: st.plotly_chart(make_dispatch_figure(day_df), use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)
    d1, d2, d3, d4 = st.columns(4)
    with d1: st.metric("PV generation", f"{day_df['PV_generation_kWh'].sum():.1f} kWh/day")
    with d2: st.metric("Optimised grid import", f"{day_df['Grid_import_kWh'].sum():.1f} kWh/day")
    with d3: st.metric("PV export", f"{day_df['PV_export_kWh'].sum():.1f} kWh/day")
    with d4: st.metric("Battery discharge", f"{day_df['Battery_discharge_kWh'].sum():.1f} kWh/day")

with tabs[4]:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="red-title">Before vs After Optimisation</div>', unsafe_allow_html=True)
    st.plotly_chart(make_before_after_figure(day_df), use_container_width=True)
    baseline_grid, opt_grid = day_df["Baseline_grid_import_kWh"].sum(), day_df["Grid_import_kWh"].sum()
    baseline_export, opt_export = day_df["Baseline_pv_export_kWh"].sum(), day_df["PV_export_kWh"].sum()
    exp = day_df[(day_df["hour_float"] >= 16) & (day_df["hour_float"] <= 21)]
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Grid import reduction", f"{baseline_grid - opt_grid:.1f} kWh/day")
    with c2: st.metric("PV export reduction", f"{baseline_export - opt_export:.1f} kWh/day")
    with c3: st.metric("Expensive import avoided", f"{exp['Baseline_grid_import_kWh'].sum() - exp['Grid_import_kWh'].sum():.1f} kWh/day")
    with c4: st.metric("HP evening reduction", f"{exp['HP_baseline_kWh'].sum() - exp['HP_optimised_kWh'].sum():.1f} kWh/day")
    st.markdown("</div>", unsafe_allow_html=True)

with tabs[5]:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="red-title">Annual Energy Flow Sankey</div>', unsafe_allow_html=True)
    st.plotly_chart(make_sankey_figure(results, pv_kwp, battery_kwh, hp_kwh_year), use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

with tabs[6]:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="red-title">Bonus-Qualifiable Flex kWh Settlement</div>', unsafe_allow_html=True)
    calc_df = pd.DataFrame({"Component": ["Battery qualified flex", "Heat pump shift flex", "PV-to-HP absorption flex", "Overlap adjustment", "Bonus-qualifiable flex"], "Formula logic": ["Usable battery capacity × controllable cycles × efficiency", "HP annual electricity × shiftable share", "HP annual electricity × PV-to-HP absorption share", "Raw flex × overlap adjustment", "Battery + HP shift + PV-to-HP - overlap"], "kWh/year": [results["battery_flex_kwh"], results["hp_shift_flex_kwh"], results["pv_to_hp_flex_kwh"], -results["overlap_adjustment"], results["bonus_flex_kwh"]]})
    st.dataframe(calc_df.style.format({"kWh/year": "{:,.0f}"}), use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1: st.markdown(f'<div class="comfort-box"><div class="red-title">Settlement Confidence</div><div class="big-number">{results["settlement_confidence"]}%</div><br>Based on smart meter, battery telemetry, HP submetering and comfort proxy.</div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="comfort-box"><div class="red-title">Comfort Protection</div><div class="big-number">{results["comfort_score"]}/100</div><br>Comfort guardrails protect indoor temperature, hot-water availability and customer override rights.</div>', unsafe_allow_html=True)

with tabs[7]:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="red-title">Commercial Offer and Value Waterfall</div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1.15, 0.85])
    with c1: st.plotly_chart(make_waterfall_figure(results, gross_value_ct, customer_bonus_ct, eon_cost_ct), use_container_width=True)
    with c2:
        offer_df = pd.DataFrame({"Metric": ["Bonus flex volume", "Gross flex value", "Customer bonus", "E.ON cost", "E.ON margin", "Recommended bonus", "Max affordable", "Decision"], "Value": [format_kwh(results["bonus_flex_kwh"]), format_eur(results["gross_value_eur"]), format_eur(results["customer_bonus_eur"]), format_eur(results["eon_cost_eur"]), format_eur(results["eon_margin_eur"]), format_ct(recommendation["recommended_bonus_ct"]), format_ct(recommendation["max_bonus_ct"]), recommendation["decision"]]})
        st.dataframe(offer_df, use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)

with tabs[8]:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="red-title">§14a / Module 3 Grid-Fee Optimisation</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Selected DSO", dso)
    with c2: st.metric("Active quarters", dso_profile["active_quarters"])
    with c3: st.metric("Module 3 uplift", format_eur(results["module3_uplift_eur"]))
    with c4: st.metric("Applied uplift", format_ct(module3_ct * dso_profile["module3_factor"]))
    st.info(dso_profile["description"])
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="red-title">aFRR / Grid-Service Upside Kicker</div>', unsafe_allow_html=True)
    a1, a2, a3, a4 = st.columns(4)
    with a1: st.metric("Eligible capacity", f"{afrr_capacity_kw:.2f} kW")
    with a2: st.metric("Availability", pct(afrr_availability))
    with a3: st.metric("Customer kicker", format_eur(results["afrr_customer_eur"]))
    with a4: st.metric("E.ON retained", format_eur(results["afrr_eon_eur"]))
    st.markdown("Recommended: keep aFRR as an optional performance kicker, not guaranteed base bonus.")
    st.markdown("</div>", unsafe_allow_html=True)

with tabs[9]:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="red-title">Portfolio Scaling</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1: portfolio_homes = st.slider("Number of homes", 100, 200000, 10000, 100)
    with c2: adoption_share = st.slider("Active optimisation availability", 0.40, 1.00, 0.80, 0.05)
    with c3: quality_factor = st.slider("Portfolio quality factor", 0.50, 1.50, 1.00, 0.05)
    sizes = sorted(list(set([1000, 5000, 10000, 25000, 50000, 100000, portfolio_homes])))
    rows = []
    for s in sizes:
        rows.append({"Homes": s, "Flex GWh": s * results["bonus_flex_kwh"] * adoption_share * quality_factor / 1_000_000, "Customer payouts €": s * results["customer_bonus_eur"] * adoption_share * quality_factor, "Gross value €": s * results["gross_value_eur"] * adoption_share * quality_factor, "E.ON margin €": s * results["eon_margin_eur"] * adoption_share * quality_factor})
    pdf = pd.DataFrame(rows)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=pdf["Homes"], y=pdf["Customer payouts €"], name="Customer payouts", mode="lines+markers", line=dict(width=4, color="#e2001a")))
    fig.add_trace(go.Scatter(x=pdf["Homes"], y=pdf["E.ON margin €"], name="E.ON margin", mode="lines+markers", line=dict(width=4, color="#174A7C")))
    fig.add_trace(go.Scatter(x=pdf["Homes"], y=pdf["Gross value €"], name="Gross value", mode="lines+markers", line=dict(width=4, color="#00a651")))
    fig.update_layout(height=460, xaxis_title="Homes", yaxis_title="€/year", hovermode="x unified", plot_bgcolor="white", paper_bgcolor="white")
    st.plotly_chart(fig, use_container_width=True)
    show = pdf.copy()
    show["Flex GWh"] = show["Flex GWh"].map(lambda x: f"{x:,.1f}".replace(",", "."))
    for col in ["Customer payouts €", "Gross value €", "E.ON margin €"]: show[col] = show[col].map(format_eur)
    st.dataframe(show, use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)

with tabs[10]:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="red-title">Segment Heatmap</div>', unsafe_allow_html=True)
    st.plotly_chart(make_heatmap(), use_container_width=True)
    st.markdown("Green segments remain profitable even at higher customer bonus levels. PV+B+HP and Premium Flex Homes are usually the priority.")
    st.markdown("</div>", unsafe_allow_html=True)

with tabs[11]:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="red-title">Model Assumptions and Next Upgrades</div>', unsafe_allow_html=True)
    assumptions = pd.DataFrame({"Area": ["Real price data", "DA price", "Intraday price", "Battery dispatch", "Heat pump dispatch", "PV generation", "Flex settlement", "§14a", "aFRR", "Limitations"], "Current assumption": ["Uploaded ZIP can contain spot_price_YEAR.csv and intraday_price_YEAR.csv.", "Hourly spot/DA is expanded to 15-minute using forward fill.", "15-minute ID prices are used directly/interpolated to a 15-minute grid.", "Rule-based 15-minute dispatch using cheap/expensive price quantiles, PV surplus and SoC limits.", "Expensive-period HP demand is shifted into cheap/PV-rich windows.", "Stylised PV curve by season, not yet PVGIS/postcode based.", "Annual flex kWh remains simplified; next step is measured-baseline settlement.", "DSO factor and uplift are simplified; next step is true HT/ST/NT table by DSO.", "Optional kicker based on eligible kW, availability and €/kW/year.", "This is not yet a full MILP optimiser or real thermal building model."]})
    st.dataframe(assumptions, use_container_width=True, hide_index=True)
    st.markdown("### Recommended next production upgrades")
    st.markdown("""
    1. Add real PVGIS forecast by postcode, roof tilt and orientation.  
    2. Add true heat-pump thermal model with indoor temperature and hot-water tank constraints.  
    3. Add DSO-specific §14a Module 3 HT/ST/NT tables and active-quarter logic.  
    4. Replace rule-based dispatch with linear optimisation.  
    5. Add measured-baseline settlement and exportable PDF/PPT report.  
    """)
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("---")
st.markdown('<div style="text-align:center;color:#777;font-size:13px;">E.ON HomeFlex Optimisation Cockpit v3 · Real DA/ID price ZIP enabled · Conceptual MVP for strategy and product design</div>', unsafe_allow_html=True)
