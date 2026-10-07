# truth.duckdb: data schema

**What it is:** the answer key. True parameters, clean data and true incremental revenue.
**Rule:** models never read this. Open it only at the end, to score each method (or to debug the simulator).
**Built by:** `01_build_world` → `02_sales_layer` → `03_plant_issues`.

| Question | Table |
|---|---|
| What's each channel's true iROAS? | `channel_truth` |
| How much revenue did Meta really drive in the geo test window? | `contributions_daily` |
| Which issues should my data-quality checks find? | `issue_register` |
| Why does brand search look so good? | `brand_search_truth` |
| Why is spend confounded with demand? | `demand_index.planner_forecast` |

## Tables at a glance

| Table | Rows | Grain | Purpose |
|---|---|---|---|
| [`run_metadata`](#run_metadata) | 1 | one row | How this world was generated, so it can be reproduced. |
| [`region_params`](#region_params) | 40 | one row per region | Each region's hidden characteristics. |
| [`demand_index`](#demand_index) | 731 | one row per day | True national demand: what people would buy with no ads. |
| [`promotions_truth`](#promotions_truth) | 325 | one row per promo × region | Promotions plus the lift they really caused. |
| [`media_daily_clean`](#media_daily_clean) | 146,200 | one row per date × region × channel | Media delivery before any issues were planted. |
| [`media_national_clean`](#media_national_clean) | 3,655 | one row per date × channel | National media before any issues were planted. |
| [`sales_daily_clean`](#sales_daily_clean) | 29,240 | one row per date × region | Sales before any issues were planted. Notebook 03 builds `observed.sales_daily` from this. |
| [`sales_truth`](#sales_truth) | 29,240 | one row per date × region | Expected (noise-free) sales. |
| [`contributions_daily`](#contributions_daily) | 204,680 | one row per date × region × component | **Where every £ came from.** True revenue split into baseline, promotion and each channel. |
| [`channel_truth`](#channel_truth) | 5 | one row per channel | **The main answer key**: how each channel really works. |
| [`brand_search_truth`](#brand_search_truth) | 29,240 | one row per date × region | Why people searched the brand: organic vs ad-driven. |
| [`issue_register`](#issue_register) | 7 | one row per issue | **Answer key for data-quality checks**: every planted issue. |

## run_metadata

How this world was generated, so it can be reproduced.

- **Grain:** one row
- **Rows:** 1
- **Written by notebook:** 01

| Column | Type | Meaning |
|---|---|---|
| `seed` | BIGINT | Random seed. |
| `config_json` | VARCHAR | Full `world.yaml` as JSON. |

## region_params

Each region's hidden characteristics.

- **Grain:** one row per region · key `region_id`
- **Rows:** 40
- **Written by notebook:** 01

| Column | Type | Meaning |
|---|---|---|
| `region_id` | VARCHAR | Region code. |
| `name` | VARCHAR | Name. |
| `nation` | VARCHAR | Nation. |
| `population` | BIGINT | Population. |
| `pop_share` | DOUBLE | Share of UK population in this set of regions. |
| `baseline_mult` | DOUBLE | Organic sales per head vs average (1.2 = buys 20% more). |
| `yearly_growth` | DOUBLE | Organic growth per year (0.06 = 6%). |
| `media_response_mult` | DOUBLE | How strongly the region responds to ads vs average. **MMM won't know this.** |
| `cpm_mult` | DOUBLE | How expensive it is to reach people here (London ×1.3 extra). |
| `tv_reach_mult` | DOUBLE | How TV impressions over/under-deliver vs population. |
| `alloc_meta` | DOUBLE | Media buyer's bias: share of Meta budget vs population share. |
| `alloc_google_nonbrand` | DOUBLE | Same, Google non-brand. |
| `alloc_tiktok` | DOUBLE | Same, TikTok. |
| `alloc_brand_search` | DOUBLE | Same, brand search (not used: brand spend is driven by searches). |

> Explains why some regions are better geo-test markets than others.

## demand_index

True national demand: what people would buy with no ads.

- **Grain:** one row per day · key `date`
- **Rows:** 731
- **Written by notebook:** 01

| Column | Type | Meaning |
|---|---|---|
| `date` | TIMESTAMP | Day. |
| `weekly` | DOUBLE | Day-of-week multiplier. |
| `yearly` | DOUBLE | Seasonal multiplier (winter peak, small summer bump). |
| `events` | DOUBLE | Black Friday, Christmas, bank holiday multipliers. |
| `demand_index` | DOUBLE | weekly × yearly × events. |
| `planner_forecast` | DOUBLE | What the media planner **expected** demand to be. Budgets follow this → **confounding**. |

## promotions_truth

Promotions plus the lift they really caused.

- **Grain:** one row per promo × region
- **Rows:** 325
- **Written by notebook:** 01

| Column | Type | Meaning |
|---|---|---|
| `promo_name` | VARCHAR | Promotion. |
| `region_id` | VARCHAR | Region. |
| `start_date` | TIMESTAMP | Start. |
| `end_date` | TIMESTAMP | End. |
| `discount` | DOUBLE | Discount. |
| `true_lift` | DOUBLE | **True** % sales lift during the promo. |

## media_daily_clean

Media delivery before any issues were planted.

- **Grain:** one row per date × region × channel
- **Rows:** 146,200
- **Written by notebook:** 01 → 02

| Column | Type | Meaning |
|---|---|---|
| `date` | TIMESTAMP | Day. |
| `region_id` | VARCHAR | Region. |
| `channel` | VARCHAR | Channel. |
| `spend` | DOUBLE | £ spent (NaN for TV). |
| `impressions` | BIGINT | Impressions. |
| `clicks` | BIGINT | Clicks. |
| `cpm` | DOUBLE | Realised £ cost per 1,000 impressions (truth only). |
| `ctr` | DOUBLE | Realised click-through rate (truth only). |

> Compare with `observed.media_daily` to see exactly what notebook 03 changed.

## media_national_clean

National media before any issues were planted.

- **Grain:** one row per date × channel
- **Rows:** 3,655
- **Written by notebook:** 01 → 02

| Column | Type | Meaning |
|---|---|---|
| `date` | TIMESTAMP | Day. |
| `channel` | VARCHAR | Channel. |
| `spend` | DOUBLE | £ spent. |
| `impressions` | BIGINT | Impressions. |
| `clicks` | BIGINT | Clicks. |

## sales_daily_clean

Sales before any issues were planted. Notebook 03 builds `observed.sales_daily` from this.

- **Grain:** one row per date × region
- **Rows:** 29,240
- **Written by notebook:** 02

| Column | Type | Meaning |
|---|---|---|
| `date` | TIMESTAMP | Day. |
| `region_id` | VARCHAR | Region. |
| `orders` | BIGINT | Orders. |
| `revenue` | DOUBLE | £ revenue. |

## sales_truth

Expected (noise-free) sales.

- **Grain:** one row per date × region
- **Rows:** 29,240
- **Written by notebook:** 02

| Column | Type | Meaning |
|---|---|---|
| `date` | TIMESTAMP | Day. |
| `region_id` | VARCHAR | Region. |
| `expected_revenue` | DOUBLE | £ revenue before random noise = baseline + promo + all media. |
| `aov` | DOUBLE | Average order value that day. |
| `expected_orders` | DOUBLE | expected_revenue ÷ aov. |

> Observed sales = a noisy draw around this.

## contributions_daily

**Where every £ came from.** True revenue split into baseline, promotion and each channel.

- **Grain:** one row per date × region × component
- **Rows:** 204,680
- **Written by notebook:** 02

| Column | Type | Meaning |
|---|---|---|
| `date` | TIMESTAMP | Day. |
| `region_id` | VARCHAR | Region. |
| `revenue` | DOUBLE | £ revenue from this component. |
| `component` | VARCHAR | `baseline`, `promotion`, `meta`, `google_nonbrand`, `tiktok`, `youtube_tv`, `brand_search`. |

> Sum a channel's rows over a period = its **true incremental revenue**. This is what geo tests and MMM are scored against.

## channel_truth

**The main answer key**: how each channel really works.

- **Grain:** one row per channel · key `channel`
- **Rows:** 5
- **Written by notebook:** 02

| Column | Type | Meaning |
|---|---|---|
| `channel` | VARCHAR | Channel. |
| `adstock` | VARCHAR | `geometric` or `delayed` (TV). |
| `half_life_days` | DOUBLE | Days until the ad effect halves. |
| `decay_alpha_daily` | DOUBLE | Daily carryover rate = 0.5^(1/half-life). |
| `peak_delay_days` | BIGINT | Days until the effect peaks (TV only). |
| `hill_half_sat_per_head` | DOUBLE | Saturation: adstocked spend per head giving 50% of max effect. |
| `hill_shape` | DOUBLE | Saturation shape (1 = concave, >1 = S-curve). |
| `beta` | DOUBLE | £ per head at full saturation. |
| `total_spend` | DOUBLE | £ spent over 2 years. |
| `total_contribution` | DOUBLE | £ incremental revenue over 2 years. |
| `avg_iroas` | DOUBLE | total_contribution ÷ total_spend. |
| `marginal_iroas` | DOUBLE | £ return on the **next** £ (+1% spend). |
| `target_iroas` | DOUBLE | Value set in `world.yaml` (should equal avg_iroas). |

> marginal < avg → saturated; marginal > avg → room to grow (TV).

## brand_search_truth

Why people searched the brand: organic vs ad-driven.

- **Grain:** one row per date × region
- **Rows:** 29,240
- **Written by notebook:** 02

| Column | Type | Meaning |
|---|---|---|
| `date` | TIMESTAMP | Day. |
| `region_id` | VARCHAR | Region. |
| `queries` | BIGINT | Brand searches. |
| `expected_queries_organic` | DOUBLE | Searches from people who'd buy anyway. |
| `expected_queries_media` | DOUBLE | Searches caused by other ads (**mediator**). |
| `cpc` | DOUBLE | £ cost per click. |

> Shows why brand search looks great in platform reports but has low true iROAS (0.3).

## issue_register

**Answer key for data-quality checks**: every planted issue.

- **Grain:** one row per issue · key `issue_id`
- **Rows:** 7
- **Written by notebook:** 03

| Column | Type | Meaning |
|---|---|---|
| `issue_id` | BIGINT | 1, 2, 3 … |
| `issue` | VARCHAR | Short issue type. |
| `table_name` | VARCHAR | Table(s) affected. |
| `channel` | VARCHAR | Channel affected (if any). |
| `region_id` | VARCHAR | Region(s) affected (if any). |
| `start_date` | TIMESTAMP_NS | First affected day. |
| `end_date` | TIMESTAMP_NS | Last affected day. |
| `rows_affected` | BIGINT | Rows changed / added / removed. |
| `planted_in` | VARCHAR | Notebook that planted it. |
| `description` | VARCHAR | What was done. |
| `should_be_caught_by` | VARCHAR | Which check should find it. |
| `impact_if_missed` | VARCHAR | What goes wrong downstream. |

> Don't look at this until you've written your own checks, then score yourself.
