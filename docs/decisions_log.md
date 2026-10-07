# Research & decisions log

My notes on external research: what I read, what I think about it, and how it shapes the project.
Newest entry at the bottom.

**Template for each entry:**

```markdown
## YYYY-MM-DD · Topic
**Question:** what I was trying to figure out
**Sources:** links
**What the research says:** key findings, in my own words
**My thinking:** what I make of it, caveats, how it connects
**Applied in the project:** the decision it led to (file / setting)
**Open questions:** what I still need to check
```

---

## 2026-10-07 · How should each channel's true iROAS be set?

**Question:** Are the true iROAS values in `config/world.yaml` realistic, and where do they come from?

**Sources:**
- [Blake, Nosko & Tadelis (2015): Consumer heterogeneity and paid search effectiveness (eBay)](https://faculty.haas.berkeley.edu/stadelis/BNT_ECMA_rev.pdf)
- [Ruler Analytics: ROAS benchmarks by channel and measurement type](https://www.ruleranalytics.com/blog/reporting/roas-benchmarks/)

**What the research says:**
- **Brand search has very low incrementality.** When eBay switched off its brand search ads, most of that traffic simply came through the free (organic) search result instead. The paper finds brand search has essentially no measurable short-term incremental benefit.
- **Platform-reported ROAS overstates incrementality.** Published "ROAS benchmarks" are mostly attributed ROAS, so they're usually higher than true iROAS.

**My thinking:**
- People searching for a brand name are usually **already intending to buy from that brand**. Turn off the paid ad and they click the organic result instead, so the ad generates little extra business.
- **High attributed ROAS ≠ high incremental ROAS.** Someone who clicks an eBay brand ad and then buys would be credited to the ad, but they would often have bought from eBay anyway.
- Brands may still bid on their own brand keywords **defensively**: otherwise competitors could appear above them and capture some of those customers.
- No single "industry standard" iROAS exists. It varies a lot by brand, product and market, so a believable **ranking** matters more than exact numbers.

**Applied in the project:**
- True iROAS values are **illustrative**: Meta 2.0, Google non-brand 1.5, YouTube/TV 1.2, TikTok 1.0, brand search 0.3.
- Brand search is set lowest (0.3) and built as a **mediator**: other ads make people Google the brand, so brand search looks great in platform reports but causes few sales itself.
- This is fine for the project's purpose: it tests whether each method can *recover* the true value, whatever it is.

**Open questions:**
- Find a source for the other channels' rough ranking (Meta vs TikTok vs YouTube), ideally one not funded by a platform.
- Does defensive bidding mean brand search's *true* value should be higher in a market with aggressive competitors? (Not modelled here: no competitors in the simulation.)
