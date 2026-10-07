"""Step 2 of the simulator: budgets -> spend -> impressions -> clicks.

Brand search is NOT built here: its volume depends on the other channels'
effects, so it is generated in the sales layer.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _ar1(n: int, phi: float, sd: float, rng: np.random.Generator) -> np.ndarray:
    x = np.zeros(n)
    eps = rng.normal(0, sd, n)
    for t in range(1, n):
        x[t] = phi * x[t - 1] + eps[t]
    return x


def _in_flight(dates: pd.Series, windows: list) -> np.ndarray:
    on = np.zeros(len(dates), dtype=bool)
    for start, end in windows:
        on |= ((dates >= start) & (dates <= end)).values
    return on


def media_channels(cfg: dict) -> list[str]:
    return [c for c, v in cfg["channels"].items() if v.get("generated_in") != "sales_layer"]


# ---------------------------------------------------------------------------
# National budgets
# ---------------------------------------------------------------------------
def build_national_spend(cfg: dict, demand: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    bp = cfg["budget_planning"]
    dates = demand["date"]
    n = len(dates)
    months = dates.dt.to_period("M")
    month_codes, month_index = np.unique(months.astype(str), return_inverse=True)

    raw = {}
    for ch in media_channels(cfg):
        c = cfg["channels"][ch]
        monthly = rng.lognormal(0, bp["monthly_shift_sd"], len(month_codes))[month_index]
        pacing = np.exp(_ar1(n, bp["daily_ar_phi"], bp["daily_ar_sd"], rng))
        r = demand["planner_forecast"].values ** c["demand_elasticity"] * monthly * pacing
        if "flighting" in c:
            r = r * _in_flight(dates, c["flighting"])
        raw[ch] = r

    # Planted collinearity: follower copies leader's shape inside the window
    cw = bp["collinear_window"]
    win = ((dates >= cw["start"]) & (dates <= cw["end"])).values
    lead, fol = raw[cw["leader"]], raw[cw["follower"]]
    ratio = fol[win].mean() / lead[win].mean()
    fol[win] = lead[win] * ratio * rng.lognormal(0, cw["noise_sd"], win.sum())

    # Scale each calendar year to its annual budget
    years = dates.dt.year.values
    first_year = years.min()
    rows = []
    for ch, r in raw.items():
        spend = np.zeros(n)
        for y in np.unique(years):
            m = years == y
            budget = cfg["channels"][ch]["annual_budget_gbp"] * (1 + bp["yearly_growth"]) ** (y - first_year)
            budget *= m.sum() / 365.0      # handles leap years / partial years
            spend[m] = r[m] / r[m].sum() * budget
        rows.append(pd.DataFrame({"date": dates.values, "channel": ch, "spend": spend}))
    return pd.concat(rows, ignore_index=True)


# ---------------------------------------------------------------------------
# Regional split + impressions + clicks
# ---------------------------------------------------------------------------
def build_media_daily(cfg: dict, regions: pd.DataFrame, demand: pd.DataFrame,
                      national: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    bp = cfg["budget_planning"]
    dates = demand["date"].values
    n_days, n_reg = len(dates), len(regions)
    forecast = demand["planner_forecast"].values
    pop_share = regions["pop_share"].values
    cpm_mult = regions["cpm_mult"].values

    out = []
    for ch in media_channels(cfg):
        c = cfg["channels"][ch]
        nat_spend = national.loc[national["channel"] == ch, "spend"].values

        # Daily CPM: pricier when demand is high, plus national noise, plus region factor
        cpm_daily = c["cpm_gbp"] * forecast ** bp["cpm_demand_elasticity"] * rng.lognormal(0, 0.08, n_days)
        cpm = cpm_daily[:, None] * cpm_mult[None, :]                      # days x regions

        if c["geo_targetable"]:
            w = pop_share * regions[f"alloc_{ch}"].values
            share = w[None, :] * rng.lognormal(0, bp["regional_daily_noise_sd"], (n_days, n_reg))
            share /= share.sum(axis=1, keepdims=True)
            spend = nat_spend[:, None] * share
            impressions = spend / cpm * 1000
            spend_out = spend
        else:
            # National buy: impressions land by population x reach; regional spend unknown
            nat_imps = nat_spend / cpm_daily * 1000
            w = pop_share * regions["tv_reach_mult"].values
            impressions = nat_imps[:, None] * (w / w.sum())[None, :]
            spend_out = np.full((n_days, n_reg), np.nan)

        impressions = np.round(impressions).astype(np.int64)
        if c["ctr"] is not None:
            ctr = c["ctr"] * rng.lognormal(0, 0.10, n_days)
            ctr = np.clip(ctr, 0, 1)[:, None] * np.ones((1, n_reg))
            clicks = rng.binomial(impressions, ctr)
        else:
            ctr = np.full((n_days, n_reg), np.nan)
            clicks = np.zeros((n_days, n_reg), dtype=np.int64)

        out.append(pd.DataFrame({
            "date": np.repeat(dates, n_reg),
            "region_id": np.tile(regions["region_id"].values, n_days),
            "channel": ch,
            "spend": spend_out.ravel(),
            "impressions": impressions.ravel(),
            "clicks": clicks.ravel(),
            "cpm": cpm.ravel(),
            "ctr": ctr.ravel(),
        }))
    return pd.concat(out, ignore_index=True)


def national_rollup(media_daily: pd.DataFrame, national_spend: pd.DataFrame) -> pd.DataFrame:
    agg = (media_daily.groupby(["date", "channel"], as_index=False)
           [["impressions", "clicks"]].sum())
    return national_spend.merge(agg, on=["date", "channel"])


def observed_media_daily(media_daily: pd.DataFrame) -> pd.DataFrame:
    """Drop truth-only columns (realised CPM / CTR)."""
    return media_daily.drop(columns=["cpm", "ctr"])
