# observed.duckdb: data schema

**What it is:** the data a client would send you. Messy on purpose (see notebook 03).
**Rule:** every analysis notebook (data-quality checks, attribution, geo test, MMM) reads **only** this file.
**Built by:** `01_build_world` → `02_sales_layer` → `03_plant_issues` (run in that order).

```
regions ──┬── media_daily (date, region_id, channel)
          ├── sales_daily (date, region_id)
          └── promotions  (promo_name, region_id)
calendar ─┴── joins on date
media_national_daily (date, channel): national totals; only home of TV spend
```

## Tables at a glance

| Table | Rows | Grain | Purpose |
|---|---|---|---|
| [`regions`](#regions) | 40 | one row per region | Master list of the 40 UK regions. |
| [`calendar`](#calendar) | 731 | one row per day | Date dimension: one row per day, 2024-01-01 to 2025-12-31. |
| [`promotions`](#promotions) | 325 | one row per promo × region | Promotions the client ran: when, where, how big the discount. |
| [`media_daily`](#media_daily) | 146,240 | one row per date × region × channel (should be!) | Daily ad delivery per region and channel, as exported from the ad platforms. |
| [`media_national_daily`](#media_national_daily) | 3,641 | one row per date × channel | Daily ad delivery for the whole UK, per channel. |
| [`sales_daily`](#sales_daily) | 29,240 | one row per date × region | Daily orders and revenue per region from the client's sales system. |

## regions

Master list of the 40 UK regions.

- **Grain:** one row per region · key `region_id`
- **Rows:** 40
- **Written by notebook:** 01

| Column | Type | Meaning |
|---|---|---|
| `region_id` | VARCHAR | Region code `R01`–`R40` (ordered by population). |
| `name` | VARCHAR | City / area name. |
| `nation` | VARCHAR | England, Scotland, Wales or Northern Ireland. |
| `population` | BIGINT | Population (people). |

> Hidden region traits (baseline, growth, ad response) are **not** here; they're in `truth.region_params`.

## calendar

Date dimension: one row per day, 2024-01-01 to 2025-12-31.

- **Grain:** one row per day · key `date`
- **Rows:** 731
- **Written by notebook:** 01

| Column | Type | Meaning |
|---|---|---|
| `date` | TIMESTAMP | Day. |
| `year` | INTEGER | Calendar year. |
| `day_of_week` | INTEGER | 0 = Monday … 6 = Sunday. |
| `day_of_year` | INTEGER | 1–366. |
| `iso_week` | BIGINT | ISO week number. |
| `is_bank_holiday` | BOOLEAN | UK bank holiday flag. |
| `is_black_friday` | BOOLEAN | Black Friday flag. |

> Use it to build seasonality / holiday features for the MMM.

## promotions

Promotions the client ran: when, where, how big the discount.

- **Grain:** one row per promo × region · key `promo_name, region_id`
- **Rows:** 325
- **Written by notebook:** 01

| Column | Type | Meaning |
|---|---|---|
| `promo_name` | VARCHAR | Promotion name. |
| `region_id` | VARCHAR | Region the promo ran in. |
| `start_date` | TIMESTAMP | First day (inclusive). |
| `end_date` | TIMESTAMP | Last day (inclusive). |
| `discount` | DOUBLE | Discount rate (0.15 = 15% off). |

> The sales lift each promo caused is **not** here (`truth.promotions_truth.true_lift`). `scotland_pop_up` is Scotland-only, a regional shock to remember when choosing geo-test markets.

## media_daily

Daily ad delivery per region and channel, as exported from the ad platforms.

- **Grain:** one row per date × region × channel (should be!) · key `date, region_id, channel`
- **Rows:** 146,240
- **Written by notebook:** 01 → 02 → **03 (issues planted)**

| Column | Type | Meaning |
|---|---|---|
| `date` | TIMESTAMP | Day. |
| `region_id` | VARCHAR | Region code. |
| `channel` | VARCHAR | `meta`, `google_nonbrand`, `tiktok`, `youtube_tv`, `brand_search`. |
| `spend` | DOUBLE | £ spent. **NaN for `youtube_tv`**: TV is bought nationally, so there is no regional spend. |
| `impressions` | BIGINT | Ad impressions delivered (TV: estimated regional viewers). |
| `clicks` | BIGINT | Clicks (0 for TV). |

> Planted issues: TikTok rows missing 12–25 Aug 2024; every row duplicated 7–9 Oct 2024; negative Google non-brand spend on 20 Jan 2025 in 3 regions.

## media_national_daily

Daily ad delivery for the whole UK, per channel.

- **Grain:** one row per date × channel · key `date, channel`
- **Rows:** 3,641
- **Written by notebook:** 01 → 02 → **03 (issues planted)**

| Column | Type | Meaning |
|---|---|---|
| `date` | TIMESTAMP | Day. |
| `channel` | VARCHAR | Channel name. |
| `spend` | DOUBLE | £ spent nationally (**the only place TV spend exists**). |
| `impressions` | BIGINT | Total impressions. |
| `clicks` | BIGINT | Total clicks. |

> Use this for TV ROAS. Planted issue: TikTok rows missing 12–25 Aug 2024. Regional sums won't match national on the duplicated / negative-spend days.

## sales_daily

Daily orders and revenue per region from the client's sales system.

- **Grain:** one row per date × region · key `date, region_id`
- **Rows:** 29,240
- **Written by notebook:** 02 → **03 (issues planted)**

| Column | Type | Meaning |
|---|---|---|
| `date` | TIMESTAMP | Day. |
| `region_id` | VARCHAR | Region code (**watch for codes not in `regions`**). |
| `orders` | BIGINT | Number of orders. |
| `revenue` | DOUBLE | £ revenue (orders × basket value, with noise). |

> Planted issues: Manchester `R06` becomes `MCR01` from 1 Apr 2025; last 3 days of 2025 incomplete (85% / 60% / 30%).
