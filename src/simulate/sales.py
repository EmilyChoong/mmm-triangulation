"""Step 3 of the simulator: how ads (and everything else) turn into sales.

Pipeline
--------
1. Media effects   spend per head -> adstock -> Hill saturation -> x beta
2. Baseline        population x region traits x growth x demand x promotions
3. Brand search    searches driven by baseline AND by other channels' effects
4. Brand effect    brand search spend -> adstock -> saturation -> x beta (small)
5. Orders          PyMC generative model, true parameters fixed with pm.do, sampled with pm.draw

Arrays are shaped (days, regions) unless stated.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pymc as pm


# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------
def adstock_weights(truth: dict, l_max: dict) -> np.ndarray:
    """Share of today's spend that acts on day 0, 1, 2, ... (sums to 1)."""
    alpha = 0.5 ** (1 / truth["half_life_days"])          # daily decay from half-life
    if truth["adstock"] == "geometric":
        lags = np.arange(l_max["geometric"])
        w = alpha ** lags
    elif truth["adstock"] == "delayed":
        lags = np.arange(l_max["delayed"])
        theta = truth["peak_delay_days"]
        ramp = np.minimum((lags + 1) / (theta + 1), 1.0)   # builds up to the peak...
        w = ramp * alpha ** np.maximum(lags - theta, 0)    # ...then decays
    else:
        raise ValueError(truth["adstock"])
    return w / w.sum()


def apply_adstock(x: np.ndarray, w: np.ndarray) -> np.ndarray:
    """Convolve each region's daily series with the carryover weights."""
    T = x.shape[0]
    out = np.zeros_like(x, dtype=float)
    for lag, wl in enumerate(w):
        if lag >= T:
            break
        out[lag:] += wl * x[: T - lag]
    return out


def hill(x: np.ndarray, half_sat: float, shape: float) -> np.ndarray:
    """Saturation in [0, 1). half_sat = level giving 50% of the maximum effect."""
    xs = np.power(np.clip(x, 0, None), shape)
    return xs / (xs + half_sat ** shape)


def _pivot(df: pd.DataFrame, value: str, dates, region_ids) -> np.ndarray:
    return (df.pivot(index="date", columns="region_id", values=value)
              .reindex(index=dates, columns=region_ids).to_numpy(dtype=float))


# ---------------------------------------------------------------------------
# 1. Media effects
# ---------------------------------------------------------------------------
def spend_per_head(cfg, ch, media_daily, national, dates, regions) -> np.ndarray:
    """Spend per person per day. TV has no regional spend, so national spend is
    shared out by each region's impression share (what TV *actually* delivered)."""
    rid = regions["region_id"].values
    pop = regions["population"].values[None, :]
    m = media_daily[media_daily["channel"] == ch]
    if cfg["channels"][ch]["geo_targetable"]:
        spend = _pivot(m, "spend", dates, rid)
    else:
        imps = _pivot(m, "impressions", dates, rid)
        share = imps / np.where(imps.sum(1, keepdims=True) == 0, 1, imps.sum(1, keepdims=True))
        nat = national.loc[national["channel"] == ch].set_index("date")["spend"].reindex(dates).values
        spend = nat[:, None] * share
    return np.nan_to_num(spend) / pop, np.nan_to_num(spend)


def saturated_signal(cfg, ch, x_per_head):
    """Adstock then saturate. Returns the [0,1) signal and the half-saturation level used."""
    t = cfg["channels"][ch]["truth"]
    w = adstock_weights(t, cfg["sales"]["adstock_l_max"])
    ad = apply_adstock(x_per_head, w)
    active = ad[ad > 0]
    half_sat = t["saturation_half_spend_pct"] * active.mean()
    return hill(ad, half_sat, t["hill_shape"]), half_sat, w


def calibrate_beta(target_iroas, spend_total, signal_scaled) -> float:
    """Pick beta so that total contribution / total spend = target iROAS exactly."""
    return target_iroas * spend_total / signal_scaled.sum()


# ---------------------------------------------------------------------------
# 2. Baseline (organic) revenue
# ---------------------------------------------------------------------------
def baseline_shape(cfg, regions, demand, promos, dates):
    """Organic revenue *shape* (no scale yet) and the promo multiplier."""
    rid = regions["region_id"].values
    pop = regions["population"].values[None, :]
    years = (np.arange(len(dates)) / 365.25)[:, None]
    growth = (1 + regions["yearly_growth"].values[None, :]) ** years
    d = demand.set_index("date").reindex(dates)["demand_index"].values[:, None]

    promo_lift = np.zeros((len(dates), len(rid)))
    discount = np.zeros_like(promo_lift)
    col = {r: i for i, r in enumerate(rid)}
    for _, p in promos.iterrows():
        on = (dates >= p["start_date"]) & (dates <= p["end_date"])
        promo_lift[on, col[p["region_id"]]] = p["true_lift"]
        discount[on, col[p["region_id"]]] = p["discount"]

    no_promo = pop * regions["baseline_mult"].values[None, :] * growth * d
    return no_promo, promo_lift, discount


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def simulate_sales(cfg, regions, demand, promos, media_daily, national, rng):
    s = cfg["sales"]
    dates = pd.DatetimeIndex(demand["date"])
    rid = regions["region_id"].values
    pop = regions["population"].values[None, :]
    resp = regions["media_response_mult"].values[None, :]
    T, R = len(dates), len(rid)
    is_2024 = (dates.year == 2024)

    # --- 2. baseline ---------------------------------------------------------
    no_promo_shape, promo_lift, discount = baseline_shape(cfg, regions, demand, promos, dates)
    b0 = s["baseline_annual_revenue_gbp"] / no_promo_shape[is_2024].sum()   # £ per head per day
    base = b0 * no_promo_shape
    promo = base * promo_lift

    # AOV: daily wobble, cheaper baskets during promotions
    aov = (s["aov_gbp"] * rng.lognormal(0, s["aov_daily_sd"], T)[:, None]
           * (1 - discount * s["promo_aov_pass_through"]))

    # --- 1. media effects (all channels except brand search) -----------------
    contrib, channel_rows, signals, spend_arrays = {}, [], {}, {}
    paid = [c for c, v in cfg["channels"].items() if v.get("generated_in") != "sales_layer"]

    def add_channel(ch, x_head, spend):
        t = cfg["channels"][ch]["truth"]
        sig, half_sat, w = saturated_signal(cfg, ch, x_head)
        scaled = resp * pop * sig                          # what beta multiplies
        beta = calibrate_beta(t["target_iroas"], spend.sum(), scaled)
        contrib[ch] = beta * scaled
        signals[ch] = scaled
        spend_arrays[ch] = spend
        # marginal iROAS: extra revenue from +1% spend, per extra £
        sig_up = hill(apply_adstock(x_head * 1.01, w), half_sat, t["hill_shape"])
        marginal = (beta * resp * pop * sig_up).sum() - contrib[ch].sum()
        channel_rows.append({
            "channel": ch, "adstock": t["adstock"], "half_life_days": t["half_life_days"],
            "decay_alpha_daily": 0.5 ** (1 / t["half_life_days"]),
            "peak_delay_days": t.get("peak_delay_days", 0),
            "hill_half_sat_per_head": half_sat, "hill_shape": t["hill_shape"],
            "beta": beta, "total_spend": spend.sum(), "total_contribution": contrib[ch].sum(),
            "avg_iroas": contrib[ch].sum() / spend.sum(),
            "marginal_iroas": marginal / (0.01 * spend.sum()),
        })

    for ch in paid:
        x_head, spend = spend_per_head(cfg, ch, media_daily, national, dates, regions)
        add_channel(ch, x_head, spend)

    media_rev = sum(contrib[c] for c in paid)

    # --- 3. brand search (mediator) -------------------------------------------
    bs_cfg, bs = s["brand_search"], cfg["channels"]["brand_search"]
    q_organic = bs_cfg["searches_per_organic_order"] * (base + promo) / aov
    q_media = bs_cfg["searches_per_media_order"] * media_rev / aov
    queries = rng.poisson(q_organic + q_media)
    bs_impr = rng.binomial(queries, bs_cfg["ad_impression_share"])
    bs_clicks = rng.binomial(bs_impr, bs["ctr"])
    cpc_noise = rng.lognormal(0, bs_cfg["cpc_daily_sd"], T)[:, None]
    cpc = bs["annual_budget_gbp"] / (bs_clicks[is_2024] * cpc_noise[is_2024]).sum()
    bs_spend = bs_clicks * cpc * cpc_noise

    # --- 4. brand search's own (small) effect ---------------------------------
    add_channel("brand_search", bs_spend / pop, bs_spend)

    # --- 5. orders via PyMC ---------------------------------------------------
    channels = list(contrib)
    orders, model = draw_orders(
        base_shape=(base + promo) / b0, signals=np.stack([signals[c] for c in channels]),
        aov=aov, true_b0=b0, true_beta=np.array([r["beta"] for r in channel_rows]),
        nb_alpha=s["nb_alpha"], dates=dates, regions=rid, channels=channels, rng=rng)
    revenue = orders * aov * rng.lognormal(0, s["basket_noise_sd"], (T, R))

    # --- tidy outputs ---------------------------------------------------------
    def long(arr, name):
        return pd.DataFrame({"date": np.repeat(dates.values, R), "region_id": np.tile(rid, T),
                             name: arr.ravel()})

    expected = base + promo + sum(contrib.values())
    sales_obs = long(orders, "orders").assign(revenue=revenue.ravel().round(2))

    comps = {"baseline": base, "promotion": promo, **contrib}
    contributions = pd.concat([long(v, "revenue").assign(component=k) for k, v in comps.items()],
                              ignore_index=True)

    bs_media = (long(bs_spend, "spend").assign(channel="brand_search",
                impressions=bs_impr.ravel(), clicks=bs_clicks.ravel())
                [["date", "region_id", "channel", "spend", "impressions", "clicks"]])
    bs_truth = long(queries, "queries").assign(
        expected_queries_organic=q_organic.ravel(), expected_queries_media=q_media.ravel(),
        cpc=(cpc * cpc_noise * np.ones((1, R))).ravel())

    sales_truth = long(expected, "expected_revenue").assign(
        aov=aov.ravel(), expected_orders=(expected / aov).ravel())

    channel_truth = pd.DataFrame(channel_rows)
    channel_truth["target_iroas"] = [cfg["channels"][c]["truth"]["target_iroas"] for c in channel_truth["channel"]]

    return {
        "sales_obs": sales_obs, "brand_search_media": bs_media,
        "contributions": contributions, "channel_truth": channel_truth,
        "brand_search_truth": bs_truth, "sales_truth": sales_truth,
        "baseline_b0": b0, "model": model,
    }


# ---------------------------------------------------------------------------
# The PyMC part
# ---------------------------------------------------------------------------
def build_world_model(base_shape, signals, aov, dates, regions, channels):
    """A generative model of daily orders. Priors are deliberately loose - they
    only matter for the prior predictive check; the world itself uses pm.do."""
    coords = {"date": dates, "region": regions, "channel": channels}
    with pm.Model(coords=coords) as model:
        base_shape_d = pm.Data("base_shape", base_shape, dims=("date", "region"))
        signals_d = pm.Data("media_signal", signals, dims=("channel", "date", "region"))
        aov_d = pm.Data("aov", aov, dims=("date", "region"))

        b0 = pm.LogNormal("b0", mu=np.log(0.007), sigma=0.5)          # £ per head per day
        beta = pm.HalfNormal("beta", sigma=0.005, dims="channel")      # £ per head at full saturation (was 0.05: see notebook 02)
        alpha = pm.Gamma("nb_alpha", alpha=4, beta=0.1)                # overdispersion

        media = pm.Deterministic("media_revenue", (beta[:, None, None] * signals_d).sum(0),
                                 dims=("date", "region"))
        revenue = pm.Deterministic("expected_revenue", b0 * base_shape_d + media,
                                   dims=("date", "region"))
        pm.NegativeBinomial("orders", mu=revenue / aov_d, alpha=alpha, dims=("date", "region"))
    return model


def draw_orders(base_shape, signals, aov, true_b0, true_beta, nb_alpha,
                dates, regions, channels, rng):
    model = build_world_model(base_shape, signals, aov, dates, regions, channels)
    # pm.do = "set these random variables to fixed values" (an intervention)
    true_world = pm.do(model, {"b0": true_b0, "beta": true_beta, "nb_alpha": float(nb_alpha)})
    # pm.draw = forward-sample the remaining random variables (just `orders` now)
    orders = pm.draw(true_world["orders"], random_seed=rng)
    return orders.astype(np.int64), model
