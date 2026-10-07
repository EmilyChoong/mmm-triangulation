"""Step 1 of the simulator: regions, calendar, demand and promotions.

Everything returned here is ground truth. `observed_*` helpers strip the
columns a real client would not have.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Regions
# ---------------------------------------------------------------------------
def build_regions(cfg: dict, rng: np.random.Generator) -> pd.DataFrame:
    """One row per region with its hidden (latent) characteristics."""
    het = cfg["region_heterogeneity"]
    channels = [c for c, v in cfg["channels"].items() if v["geo_targetable"]]

    df = pd.DataFrame(cfg["regions"])
    n = len(df)
    df.insert(0, "region_id", [f"R{i+1:02d}" for i in range(n)])
    df["population"] = df.pop("pop_k") * 1000
    df["pop_share"] = df["population"] / df["population"].sum()

    # Latent traits (truth only)
    df["baseline_mult"] = rng.lognormal(0, het["baseline_per_capita_sd"], n)
    df["yearly_growth"] = rng.normal(het["growth_mean"], het["growth_sd"], n)
    df["media_response_mult"] = rng.lognormal(0, het["media_response_sd"], n)
    df["cpm_mult"] = rng.lognormal(0, het["cpm_sd"], n)
    df.loc[df["name"] == "London", "cpm_mult"] *= 1.3   # London is expensive
    df["tv_reach_mult"] = rng.lognormal(0, het["tv_reach_sd"], n)
    for ch in channels:
        df[f"alloc_{ch}"] = rng.lognormal(0, het["allocation_sd"], n)

    return df


def observed_regions(regions: pd.DataFrame) -> pd.DataFrame:
    return regions[["region_id", "name", "nation", "population"]].copy()


# ---------------------------------------------------------------------------
# Calendar + demand index
# ---------------------------------------------------------------------------
def build_calendar(cfg: dict) -> pd.DataFrame:
    dates = pd.date_range(cfg["dates"]["start"], cfg["dates"]["end"], freq="D")
    cal = pd.DataFrame({"date": dates})
    cal["year"] = cal["date"].dt.year
    cal["day_of_week"] = cal["date"].dt.dayofweek          # 0 = Monday
    cal["day_of_year"] = cal["date"].dt.dayofyear
    cal["iso_week"] = cal["date"].dt.isocalendar().week.astype(int)
    bh = pd.to_datetime(cfg["demand"]["bank_holidays"])
    cal["is_bank_holiday"] = cal["date"].isin(bh)

    bf = pd.to_datetime(cfg["demand"]["events"]["black_friday"]["dates"])
    cal["is_black_friday"] = cal["date"].isin(bf)
    return cal


def build_demand_index(cfg: dict, cal: pd.DataFrame) -> pd.DataFrame:
    """True national demand, split into components so we can check recovery later."""
    d = cfg["demand"]
    out = cal[["date"]].copy()

    out["weekly"] = np.array(d["weekly"])[cal["day_of_week"]]

    yearly = np.ones(len(cal))
    for comp in d["yearly"]:
        h = comp.get("harmonic", 1)
        phase = 2 * np.pi * h * (cal["day_of_year"] - comp["peak_day_of_year"]) / 365.25
        yearly += comp["amplitude"] * np.cos(phase)
    out["yearly"] = yearly

    events = np.ones(len(cal))
    for bf_date in pd.to_datetime(d["events"]["black_friday"]["dates"]):
        for offset, mult in d["events"]["black_friday"]["multipliers"].items():
            events[(cal["date"] == bf_date + pd.Timedelta(days=int(offset))).values] *= mult
    mmdd = cal["date"].dt.strftime("%m-%d")
    for key, mult in d["events"]["christmas"]["multipliers"].items():
        events[(mmdd == key).values] *= mult
    events[cal["is_bank_holiday"].values] *= d["bank_holiday_mult"]
    out["events"] = events

    out["demand_index"] = out["weekly"] * out["yearly"] * out["events"]

    # What the planner *expects*: knows the season and big events, not the
    # day-of-week wiggle. Budgets follow this -> spend is confounded with demand.
    out["planner_forecast"] = (
        (out["yearly"] * out["events"]).rolling(3, center=True, min_periods=1).mean()
    )
    return out


# ---------------------------------------------------------------------------
# Promotions
# ---------------------------------------------------------------------------
def build_promotions(cfg: dict, regions: pd.DataFrame) -> pd.DataFrame:
    """Long table: one row per promotion x region."""
    rows = []
    for p in cfg["promotions"]:
        nations = regions["nation"].unique() if p["nations"] == "all" else p["nations"]
        for rid in regions.loc[regions["nation"].isin(nations), "region_id"]:
            rows.append({
                "promo_name": p["name"], "region_id": rid,
                "start_date": pd.Timestamp(p["start"]), "end_date": pd.Timestamp(p["end"]),
                "discount": p["discount"], "true_lift": p["true_lift"],
            })
    return pd.DataFrame(rows)


def observed_promotions(promos: pd.DataFrame) -> pd.DataFrame:
    return promos.drop(columns="true_lift")
