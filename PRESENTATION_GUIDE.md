# Hounde Blast Optimization — Client Presentation Guide

## TL;DR — what to show

**Pit `VIM3`, Bench `291`** is pre-selected as the demo bench. It has the most
blasts with measured fragmentation (5), the most patterns (17) and 6 376
clean QA/QC holes. Other pits/benches will work but the data is thinner and the
calibration noisier — keep them as backup.

| Pit         | Best bench | Why                                                           |
| **VIM3 **   | **291**    | 17 patterns · 5 frag blasts · 6 376 holes — **demo this one** |
| KARIWEST    | 290        | 8 patterns · 3 frag blasts · 3 788 holes                      |
| VIM2        | 153        | 12 patterns · 3 frag blasts · 4 272 holes                     |
| KARIPUMP    | 250        | 7 patterns · 3 frag blasts · 2 871 holes                      |
| VIM1        | 261        | only 2 frag blasts — **skip if possible**                     |

---

## How to launch

```bash
streamlit run Baseline_Analysis.py
```

Open the URL it prints (usually `http://localhost:8501`).

The **sidebar** (left) is the only global control. It selects the pit. The main
area below the title shows pit-level KPIs and the 5 tabs of the workflow.

---

## The 5 tabs — what they are and how to talk through them

### Tab 1 · Data Linking — *"This is the evidence we built the analysis on"*

**What's on screen:**
- Top KPIs: linkage coverage, median measured D50/D80, average actual powder
  factor.
- A **bench data-quality ranking** for the selected pit. The top bench is the
  one pre-selected on tabs 2/3/4.
- Blast-level summary table (one row per blast).
- Linked hole sample (each row = one drill hole + its blast's fragmentation).

**What to say to the client:**
> *"We have two independent records. QA/QC is what was actually drilled and
> loaded — hole positions, charge weight, stemming. Data_Frag is the
> image-analysis result of what came out of the bench — D20, D50, D80. We
> link them by blast name, then we keep only benches where this evidence is
> strong. For VIM3, that's bench 291."*

**Watch for:** linkage coverage **above 20 %** is workable; below 10 % means
this pit is data-poor and you should switch.

---

### Tab 2 · Bench Fragmentation 3D — *"This is the bench they live with today"*

**What's on screen:**
- A 3D scatter: each dot is a hole at its real position, colored by its blast's
  measured D80, marker shape = pattern.
- A 2-D plan view of the same data (easier to read pattern boundaries).
- A per-pattern table with median D50/D80 and **% of holes within the 350 mm
  target**.

**What to say:**
> *"This is what the bench actually looks like today. Green areas are well
> fragmented, red is oversize — material the crusher and shovels will struggle
> with. You can see fragmentation is uneven inside the same bench, and that
> some patterns systematically perform worse. That's the room for
> improvement."*

**Watch for:** patterns with `Pct_within_target` below 30 % are the pain
points. Mention them by name.

---

### Tab 3 · Rock Factor Calibration — *"Now we calibrate the model on the real rock"*

**What's on screen:**
- An **equations** expander (open it if a technical person is in the room — it
  lists Kuznetsov, Cunningham, Rosin-Rammler, with references).
- KPI: how many blasts were calibrated, median Rock Factor A, the range of A.
- Histogram of A across the pit (rock variability).
- RF vs powder factor scatter (sanity check).
- Per-blast calibration table.
- For the chosen bench: a **2-D RF map**, a **2-D recalculated D80 map**, and
  a **3-D RF map**.

**What to say:**
> *"The Rock Factor A captures how hard the rock is to break — it's a single
> number per blast we back-calculate from measured D50 using the Kuz-Ram
> equations. For VIM3 the median A is around X. The map on the right shows the
> rock isn't uniform — there are softer and harder zones inside the same
> bench. That's why one fixed pattern can't be optimal everywhere."*

**Watch for:** if A is below ~3 or above ~22, we have noisy data — flag it.
Median in the 6–12 range is healthy.

---

### Tab 4 · Old vs Actual vs Rioflex FX Adapt — *"What changes if we move to Rioflex"*

This is the **money slide**.

**What's on screen:**
- 3 KPI cards on top: median predicted D80 + % of holes within target, for
  Old / Actual / Rioflex FX.
- Three side-by-side 3-D bench maps — same X, Y, Z, **same rock**, same
  Rock Factor — only the product/pattern changes.
- A boxplot showing the distribution shift across the bench.
- A Rosin-Rammler passing-curve plot with the 350 mm target line.

**What to say:**
> *"Same bench, same calibrated rock factor — we just swap in three loading
> strategies. The left map is what fragmentation would look like with the old
> product and old pattern. Middle is what we actually got. Right is the
> prediction with Rioflex FX Adapt: same drilling effort, higher RWS, plus the
> +10 % uniformity index we observe in the field. You can see the right map
> goes mostly green — more holes meet the 350 mm target."*

**The Rioflex slider:** the **Δn slider** controls the uniformity boost. The
default `+0.10` is the field-observed lift for Rioflex FX. Move it down to
`+0.05` for a conservative pitch, up to `+0.15` if asked "what's the upside?".

---

### Tab 5 · Suggestions & Savings — *"Here's the value for the next benches"*

**What's on screen:**
- A **pattern-expansion sweep**: many possible Burden × Spacing combinations,
  colored by predicted D80, with `circle = within target`, `× = oversize`.
- A green callout proposing the recommended Burden × Spacing for the next
  benches, plus the % area expansion vs. the current pattern.
- A cost calculator: input rock volume + unit costs, get total savings,
  $/m³ savings, holes saved.
- A per-parameter comparison table.

**What to say:**
> *"With Rioflex FX Adapt and the same Rock Factor, we can open the pattern up
> by ~Z%. That means N fewer holes drilled per bench, M kg less explosive, and
> roughly $X savings per 100 000 m³ blasted, while still meeting the 350 mm
> target."*

The "Download full client report (Excel)" button at the bottom packages
everything you've shown into a single workbook for the client to keep.

---

## Common questions from the client

**"Why this bench and not another?"**
> *"The bench data-quality ranking on Tab 1 shows that bench 291 has the
> largest sample of holes with both QA/QC and measured fragmentation. The
> other benches in this pit have less measured data, so calibration would be
> noisier."*

**"What if our Rock Factor is wrong?"**
> *"It's not assumed — it's back-calculated from your own measured D50 using
> the Kuz-Ram equation. Tab 3 shows the distribution and you can see the
> spread. We use the median for predictions."*

**"Where does the +10 % uniformity boost come from?"**
> *"It's the field-observed improvement of Rioflex FX Adapt over standard
> emulsion at equivalent powder factor — better energy distribution along the
> column. The slider on Tab 4 lets you scale it up or down to test
> sensitivity."*

**"What about safety / vibrations / fly-rock?"**
> Out of scope here — this app is fragmentation and economics. Refer to the
> blast-vibration / monitoring records.

---

## Failure modes & how to recover

| Symptom | Cause | What to do |
|---|---|---|
| Tab 2 says "No linked fragmentation data for this bench" | The bench has QA/QC but no Data_Frag rows | Pick another bench from the ranking on Tab 1 |
| Tab 3 calibration table is empty / "No blasts with measured D50" | Pit has zero linked frag rows | Switch pit (avoid VIM1) |
| Rock Factor A values look extreme (<2 or >25) | Bad stemming/charge values for that blast | Drop the bad row from the table — it's an outlier |
| Rioflex 3D map is similar to Actual | Δn slider was set to 0 or RWS values are equal | Reset Δn to 0.10, RWS Old=100, Rioflex=115 |
| All numbers look wrong after switching pit | Streamlit cache | Use the **⟳ Rerun** button (top right) |

---

## Key numbers to memorise before the meeting

- **Target:** D80 ≤ 350 mm (client agreed)
- **Old product RWS:** 100 (ANFO equivalent)
- **Rioflex FX Adapt RWS:** 115 (default)
- **Uniformity boost:** +10 % (field-observed)
- **Bench height VIM3:** 12 m (291 → 279)
- **Demo bench:** VIM3 / 291

Good luck.
