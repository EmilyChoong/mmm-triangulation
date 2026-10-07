# Start here: the project in plain English

Read this first. No MMM knowledge assumed.

---

## 1. The question

- A company advertises on several channels (Meta, TikTok, Google, YouTube/TV).
- It wants to know: **how many extra sales did each channel actually cause?**
- There are 3 common ways to measure this, and they give **different answers**.
- This project asks: **which method is closest to the truth, why do the others miss, and what should a marketer do?**

## 2. Why we use fake data

- With real data, nobody knows the true answer, so you can't tell which method is right.
- So we **build a fake company** where we set the true answer ourselves.
- Then we hand the methods only what a real client would give them and check how close each gets.

## 3. The fake company

- A UK online shop selling in **40 regions** (London, Leeds, Glasgow, …).
- **2 years** of daily data (2024–2025).
- Advertises on **5 channels**: Meta, Google non-brand search, TikTok, YouTube/TV, Google brand search.

## 4. How sales are made (the recipe)

Every day, in every region:

```
sales = baseline  +  promotions  +  sales caused by ads
```

- **Baseline:** what people would buy with **no ads at all**. Bigger regions buy more, there's a weekly and yearly pattern, and Black Friday / Christmas spike.
- **Promotions:** discounts (e.g. summer sale) give a temporary boost.
- **Sales caused by ads:** each channel, worked out with the same 4 steps:

| Step | Plain meaning |
|---|---|
| 1. Spend per head | £ spent in that region ÷ population |
| 2. Adstock | an ad keeps working for a few days after it's shown (carryover) |
| 3. Saturation | the more you spend, the less each extra £ adds (diminishing returns) |
| 4. × beta | converts the result into £ of sales |

- Each channel has its **own** settings for steps 2–4. Those settings *are* the true answer, and they're hidden in the truth file.
- Finally, random noise is added so the data looks real.

## 5. Why measuring this is hard

- **Ads and busy seasons happen together.** The company spends more in Q4, when people buy more anyway. So it's hard to tell how much of the Q4 rise came from the ads and how much would have happened regardless.
- **Sales don't record which ad caused them.** You only see total sales per region per day.
- **Some channels move together** (e.g. TikTok copies Meta for a few months), so their effects are hard to separate.
- **The data is messy** (missing days, duplicates, a region renamed), just like real client data.

## 6. The data: two files

| File | What it is | Who reads it |
|---|---|---|
| `data/observed.duckdb` | what the client sends you (messy) | **all your analysis** |
| `truth/truth.duckdb` | the answer key | only at the end, to mark your work |

**The observed tables you'll actually use:**

- `sales_daily`: orders and revenue per **region per day**. No channel info.
- `media_daily`: spend, impressions and clicks per **region per day per channel**.
- `media_national_daily`: the same, but UK totals per day per channel. This is the only place TV spend exists.
- `calendar` and `promotions`: dates, holidays, sale periods.

**The truth tables you'll use to mark your work:**

- `channel_truth`: each channel's true return on spend (iROAS).
- `contributions_daily`: how much revenue each channel *really* caused, per region per day.
- `issue_register`: the list of data problems that were planted.

Full column-by-column details: `01_schema_observed.md` and `02_schema_truth.md`.

## 7. What are impressions and clicks for?

- **Impressions** = number of times an ad was shown. **Clicks** = number of times it was clicked.
- In this fake world, **sales are driven by spend**, not impressions.
- They're there because real client data has them, and two later steps use them:
  - **Platform attribution** (below) works off clicks.
  - The **data-quality checks** look for odd values in them.
- **For the MMM you can ignore them.**

## 8. The three methods

| Method | How it works | Typical problem |
|---|---|---|
| **Platform attribution** | Meta/TikTok/Google count sales from people who clicked or saw their ad, and claim them | claims sales that would have happened anyway, and every platform claims the same sale |
| **Geo experiment** | switch Meta up in some regions, keep others normal, compare their sales | accurate, but only tests one channel at a time, and TV can't be tested this way |
| **MMM** (Marketing Mix Model) | a statistical model that explains total sales over time using each channel's spend | can be fooled by the busy-season effect and channels moving together |

**Attribution rules:** when a customer saw several ads before buying, a rule decides which channel gets the credit:

| Rule | Who gets credit for the sale |
|---|---|
| Last click | the last ad clicked before buying |
| First click | the first ad clicked |
| Linear | split equally across every ad clicked |
| Time decay | split, with more credit to ads closer to the purchase |
| Position-based (U-shaped) | most credit to first and last (e.g. 40/40), the rest split across the middle |
| Data-driven | a model learns the split from customer journeys |

- **What they all share:** they only **share out** the credit for sales that happened. None of them asks whether the sale would have happened **without** the ad, so none measures incrementality.
- **Attribution window:** how long after a click or view a sale can still be credited (e.g. 7-day click, 1-day view). Changing it changes the reported numbers overnight (planted for Meta later).

- **Calibration:** use the geo experiment's result to correct the MMM.
- **Triangulation:** put all three side by side against the truth and explain each gap.

## 9. Key words (only these)

- **Incremental:** sales that would **not** have happened without the ad.
- **iROAS:** incremental £ revenue per £1 spent. 2.0 = £2 back for every £1.
- **Adstock:** ad effect that carries over into the following days.
- **Saturation:** diminishing returns from spending more.
- **Confounding:** something else (season) moves both spend and sales, faking an ad effect.
- **Geo test:** an experiment run by region.

## 10. True answers (the answer key, 2-year average)

| Channel | True iROAS | In plain words |
|---|---|---|
| Meta | 2.0 | £2 back per £1 |
| Google non-brand | 1.5 | |
| YouTube/TV | 1.2 | |
| TikTok | 1.0 | breaks even |
| Brand search | 0.3 | looks great in platform reports, barely causes sales |

## 11. Steps and progress

1. ✅ **Build the world**: regions, demand, media spend (`01_build_world`)
2. ✅ **Make sales** from the recipe above (`02_sales_layer`)
3. ✅ **Make the data messy** (`03_plant_issues`)
4. ⬜ **Data-quality checks**: find the mess using SQL, without looking at truth
5. ⬜ **Platform attribution**: what the platforms would claim
6. ⬜ **Geo experiment** on Meta
7. ⬜ **MMM**: plain, then calibrated with the geo result
8. ⬜ **Compare all three to the truth** and write it up

Run order for the data: `01 → 02 → 03`. Re-running 01 or 02 resets the mess, so always finish with 03.

## 12. Safe to ignore for now

- The exact maths in `sales.py` (PyMC, Negative Binomial noise). Sales are a noisy version of the recipe in section 4.
- Region-level hidden traits (`region_params`). They only matter when picking geo-test regions.
- Impressions and clicks, until the attribution step.
