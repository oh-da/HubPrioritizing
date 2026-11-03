# How a Hub Gets Its Score — the Calculation Workbook, Step by Step

*A plain-language guide to `hub_scoring_calculation.xlsx`, written to be turned into a presentation.*

---

## The big idea (one sentence)

**Every hub is scored the same way, on five simple questions, compared only with hubs of its own kind, and the workbook lets anyone check every number with a formula.**

If someone remembers only one thing from the presentation, it should be this.

---

## Who this is for, and why it matters

- **You are:** a planner, a decision-maker, or a reviewer who needs to trust a ranking of transport hubs (מתח"מים) without reading Python code.
- **The problem:** rankings that come out of a "black box" are hard to trust and hard to defend in a discussion with a ministry, a municipality or a metropolitan authority.
- **What the workbook gives you:** the whole calculation, in Excel, one step per sheet. Nothing is hidden. Change a number and you see what happens.

---

## How to read this guide

Each step has the same layout, so each one can become one or two slides:

| Part | What it gives you |
|---|---|
| **Slide title** | The message of the step, in one line |
| **In plain words** | What happens, with no jargon |
| **The rule** | The exact rule the formula follows |
| **Example** | The same three made-up hubs, all the way through |
| **Where to look** | The sheet and columns in the workbook |
| **Why we do it** | The reason behind the rule |

---

## Meet the three example hubs

To keep things concrete we follow three **made-up** metropolitan hubs (מטרופוליני) through every step. The numbers are invented to be easy to follow. They are not real results.

| Hub | Where | Passengers/day (2050) | Lines through it | Bus terminal nearby |
|---|---|---|---|---|
| **Hub A** | Tel Aviv, core | 32,000 | 2 Metro, 4 LRT, 2 BRT | Large terminal |
| **Hub B** | Tel Aviv, ring | 6,000 | 2 Suburban rail, 2 BRT | None |
| **Hub C** | Be'er Sheva, core | 48,000 | 4 Interurban rail, 2 Metro, 2 LRT | Small/medium terminal |

---

## The journey at a glance

```
 Inputs from the pipeline (blue numbers)
        │
 Step 0  Parameters        – the "control panel": every threshold and weight
 Step 1  Eligibility       – is it a hub at all?  which tier?
 Step 2  Location          ┐
 Step 3  Service & modes   │  five questions,
 Step 4  Passenger demand  │  each turned into a
 Step 5  Population & jobs │  1-to-10 grade
 Step 6  Bus terminal      ┘  within the tier
 Step 7  Monte Carlo       – how much each question counts
 Step 8  Final score       – grades × weights = score
 Step 9  Ranking           – who comes first, and among whom
        │
 Hub Explorer  – one hub, the whole story on one page
 Checks        – proof that Excel and the pipeline agree
```

**Slide idea:** this diagram is the "agenda" slide. Show it again, highlighted, before each section.

---

## Before we start: how to read the colours

| You see | It means |
|---|---|
| **Blue text** | A number that came from the pipeline (data). Don't change it. |
| **Black text** | A formula calculated in this workbook. |
| **Green text** | A formula that pulls a value from another sheet. |
| **Yellow cell** | A key parameter. Change it, and everything recalculates. |
| **Green cell** | A result (eligible, normalised grade, score, rank). |

**Where to look:** sheet `README`.

---

## Step 0 — Parameters: one control panel for the whole calculation

**Slide title:** *All the rules live in one place, so changing a rule never means hunting through formulas.*

**In plain words**
Every threshold and weight used anywhere in the workbook sits on one sheet. The formulas don't contain numbers like "1,000" or "50,000". They refer to named cells like `MinPassengers` or `NationalMinDemand`.

**What's on it (default values)**

| Group | Parameter | Value |
|---|---|---|
| Eligibility | Minimum passengers per day | 1,000 |
| | Minimum number of mass-transit modes | 2 |
| | Exclude rail-only groups | Yes |
| Tiers | National (ארצי) minimum passengers | 50,000 |
| | Metropolitan (מטרופוליני) minimum passengers | 5,000 |
| | Minimum lines to be a hub | 3 |
| Location | Region weight: Center / Tel Aviv | 0 |
| | Region weight: everywhere else | 1 |
| | Core / ring / outer | 3 / 2 / 1 |
| Service | Mode weights (per line) | BRT 4 · LRT 5 · Metro 6 · Suburban rail 6 · Interurban rail 7 · High-speed rail 8 |
| | Bonus per extra mode | 10% |
| Pop & jobs | Rings | 0–500, 500–1000, 1000–1500 m |
| | National / Metropolitan mix | 80% jobs, 20% population |
| | Local mix | 80% population, 20% jobs |
| Grades | Scale | 1 to 10 (5.5 if every hub in the tier is equal) |
| Monte Carlo | Iterations / seed / cap | 10,000 / 42 / 50% |

**Where to look:** sheet `Parameters`. Yellow cells are the ones worth playing with.

**Why we do it:** transparency. A reviewer can see every assumption in one table and test "what if" without touching a formula.

---

## Step 1 — Eligibility and tier: is it a hub, and what kind?

**Slide title:** *Only places with real demand and a real choice of modes become hubs, and each hub is put in its own league.*

**In plain words**
The pipeline has already grouped nearby stations into **hub groups** (stations within about 120 m of each other become one group). This step asks two questions about each group:

1. **Is it a hub at all?** (eligibility)
2. **If so, which tier is it?** National, Metropolitan or Local

**The rule: eligibility.** All three must be true:

| Test | Rule |
|---|---|
| Enough passengers | ≥ 1,000 passengers per day in 2050 |
| More than one mode | ≥ 2 planned mass-transit modes |
| Not rail-only | At least one mode other than suburban/interurban rail |

**The rule: tier.** These are checked in order, and the first match wins:

| Tier | Needs a mode of… | Lines | Passengers/day |
|---|---|---|---|
| **ארצי National** | High-speed or Interurban rail | ≥ 3 | ≥ 50,000 |
| **מטרופוליני Metropolitan** | Suburban rail, Metro, Interurban or High-speed rail | ≥ 3 | ≥ 5,000 |
| **עירוני Local** | BRT or LRT | ≥ 3 | ≥ 1,000 |
| Train Station | Rail, but only 1–2 lines | < 3 | — |
| Not Hub | Anything else | | |

**Example**

| Hub | Passengers ≥ 1,000? | Modes ≥ 2? | Not rail-only? | Eligible? | Tier |
|---|---|---|---|---|---|
| A | ✔ 32,000 | ✔ 3 modes | ✔ | **Yes** | Metropolitan (Metro, 8 lines, 32,000 < 50,000) |
| B | ✔ 6,000 | ✔ 2 modes | ✔ (has BRT) | **Yes** | Metropolitan (Suburban rail, 4 lines, ≥ 5,000) |
| C | ✔ 48,000 | ✔ 3 modes | ✔ | **Yes** | Metropolitan (has Interurban rail, but 48,000 < 50,000, so not National) |

Hub C is a nice discussion point: it has intercity rail, but it falls just short of the National threshold.

**Where to look:** sheet `1_Eligibility`. One row per hub group. The green columns **ELIGIBLE** and **Hub type (tier)** are the results.

**Why we do it:**
- Eligibility keeps out simple stops that are not interchanges.
- Tiers make sure hubs compete **only with hubs of their own kind**. A neighbourhood hub is never measured against Tel Aviv Savidor.

> **Good to know:** which hubs appear on the following sheets was fixed when the pipeline ran. If you change an eligibility threshold here, the ELIGIBLE flag updates, but rows are not added or removed on the later sheets.

---

## Steps 2–6 — The five questions

Every hub is asked five questions. Each answer starts as a **raw number** (in its own unit) and is turned into a **grade from 1 to 10**.

| # | Question | Criterion | Sheet |
|---|---|---|---|
| 1 | Is it in a place we want to strengthen? | Location | `2_Location` |
| 2 | How strong and varied is its service? | Service & modes | `3_Service` |
| 3 | How many people use it? | Passenger activity | `4_Demand` |
| 4 | How many people live and work around it? | Population & jobs | `5_PopJobs` |
| 5 | Is a bus terminal next to it? | Bus terminal | `6_BusTerminal` |

### The one trick used on all five sheets: grading 1 to 10 within the tier

**Slide title:** *Every criterion becomes a 1-to-10 grade, comparing a hub only with others of the same tier.*

**In plain words**
Raw numbers come in different units (passengers, lines, people), so they can't be added together. Each one is turned into a grade:

- the **lowest** hub in the tier gets **1**
- the **highest** hub in the tier gets **10**
- everyone else lands in between, in proportion

**The rule**

```
grade = 1 + (my value − tier minimum) × 9 ÷ (tier maximum − tier minimum)
```

If every hub in the tier has the same value, they all get **5.5**.

**Picture it as a ruler:** the worst hub in the league is at 1, the best at 10, and everyone else sits on the ruler according to their distance between the two.

**Where to look:** on each criterion sheet, the last three columns: **Tier minimum**, **Tier maximum**, and the green **…_Norm (1-10)**.

**Why we do it:** it puts all five criteria on the same 1–10 scale, so they can be added together, and keeps the comparison fair inside each tier.

---

## Step 2 — Location: favouring the periphery and the core

**Slide title:** *Location gives an advantage to hubs outside the Center, and more to those at the core of their metropolis.*

**In plain words**
Two simple ratings, multiplied:

1. **Region:** Center / Tel Aviv = **0**, anywhere else = **1**
2. **Position in the metropolis:** core (גלעין) = **3**, ring (טבעת) = **2**, outer = **1**

```
location raw = region × position
```

**Example**

| Hub | Region | Position | Raw | Grade (1–10) |
|---|---|---|---|---|
| A | Tel Aviv → 0 | Core → 3 | 0 × 3 = **0** | **1.0** |
| B | Tel Aviv → 0 | Ring → 2 | 0 × 2 = **0** | **1.0** |
| C | South → 1 | Core → 3 | 1 × 3 = **3** | **10.0** |

**Where to look:** sheet `2_Location`, columns *Region weight*, *Position score*, *RegionLocation (raw)*.

**Why we do it:** national equity. This criterion deliberately pushes investment towards the periphery.

> **Be upfront about this in the presentation:** because the Center weight is 0, **every hub in the Center gets the lowest location grade (1)**, whatever its position. That is a policy choice, not a data result, and it can be changed on `Parameters` (`RegionWeightCenter`).

---

## Step 3 — Service & modes: more lines, better modes, more variety

**Slide title:** *Service rewards lines of high-capacity modes, plus a bonus for every extra mode.*

**In plain words**
1. Count the lines of each mode passing through the hub (each direction counts as a separate line).
2. Multiply each count by the mode's **weight**: heavier modes count more (BRT 4, LRT 5, Metro 6, Suburban rail 6, Interurban rail 7, High-speed rail 8).
3. Add a **variety bonus**: +10% for each mode beyond the first.

```
service raw = (Σ lines × mode weight) × (1 + 10% × (number of modes − 1))
```

**Example**

| Hub | Weighted lines | Modes | Bonus | Raw | Grade |
|---|---|---|---|---|---|
| A | 2×6 + 4×5 + 2×4 = **40** | 3 | ×1.2 | **48** | **7.16** |
| B | 2×6 + 2×4 = **20** | 2 | ×1.1 | **22** | **1.00** |
| C | 4×7 + 2×6 + 2×5 = **50** | 3 | ×1.2 | **60** | **10.00** |

How hub A got 7.16: `1 + (48 − 22) × 9 ÷ (60 − 22) = 7.16`

**Where to look:** sheet `3_Service`. Row 3 shows the mode weights pulled from `Parameters`. Columns: *Weighted lines*, *Diversity multiplier*, *Service score (raw)*.

**Why we do it:** a hub with many lines of high-capacity modes, and a choice between modes, offers more connections and more resilience.

---

## Step 4 — Passenger activity: big matters, but not 10× big

**Slide title:** *Demand counts, but on a "log" scale, so mega-stations don't drown everyone else.*

**In plain words**
We take the 2050 daily passengers (boardings + alightings) and use the **log₁₀**, which roughly means "count the digits":

| Passengers | log₁₀ |
|---|---|
| 1,000 | 3 |
| 10,000 | 4 |
| 100,000 | 5 |

So a station 10× bigger gets **one** step more, not ten times more.

**Example**

| Hub | Passengers | log₁₀ | Grade |
|---|---|---|---|
| A | 32,000 | 4.51 | **8.25** |
| B | 6,000 | 3.78 | **1.00** |
| C | 48,000 | 4.68 | **10.00** |

Notice that A has two-thirds of C's passengers but gets a grade close to C's. That is the log at work.

**Where to look:** sheet `4_Demand`. (Hubs with 0 passengers are left out when finding the tier minimum and maximum.)

**Why we do it:** without the log, one or two giant stations would set the scale, and every other hub would be squeezed near 1.

---

## Step 5 — Population & jobs: who lives and works within walking distance

**Slide title:** *Catchment counts 2050 residents and jobs around the hub, with the closest ones counting most.*

**In plain words**
1. Draw three rings around the hub: **0–500 m**, **500–1,000 m**, **1,000–1,500 m**.
2. In each ring, count the 2050 **population** and **jobs**.
3. Mix them by tier:
   - National and Metropolitan hubs: **80% jobs, 20% population** (they serve employment centres)
   - Local hubs: **80% population, 20% jobs** (they serve neighbourhoods)
4. **Distance decay:** divide each ring by a number that grows with distance, so the inner ring counts most.

| Ring | Midpoint | Divisor (midpoint^1.5) |
|---|---|---|
| 0–500 m | 250 m | ≈ 3,953 |
| 500–1,000 m | 750 m | ≈ 20,540 |
| 1,000–1,500 m | 1,250 m | ≈ 44,194 |

```
pop & jobs raw = Σ over rings of (pop share × population + jobs share × jobs) ÷ ring divisor
```

**Example (Hub A, metropolitan, so 80% jobs)**

| Ring | Population | Jobs | Mix (20/80) | ÷ divisor | Contribution |
|---|---|---|---|---|---|
| 0–500 m | 3,000 | 20,000 | 16,600 | ÷ 3,953 | 4.20 |
| 500–1,000 m | 9,000 | 30,000 | 25,800 | ÷ 20,540 | 1.26 |
| 1,000–1,500 m | 15,000 | 40,000 | 35,000 | ÷ 44,194 | 0.79 |
| **Total** | | | | | **6.25** |

Results: A = 6.25 → **10.0**, B = 1.18 → **1.0**, C = 3.81 → **5.66**

Even though the outer ring of Hub A has more than twice the people and jobs of the inner ring, the inner ring contributes **five times** as much. That is distance decay.

**Where to look:** sheet `5_PopJobs`. Row 3 shows the decay divisors. Columns *Ring … (decayed)* and *PopEmp score (raw)*.

**Why we do it:** people within a short walk are the ones who will really use the hub, and the 2050 figures capture future development (TOD) potential.

---

## Step 6 — Bus terminal: is the bus network plugged in?

**Slide title:** *A planned bus terminal within 200 m signals strong bus integration, and bigger terminals score higher.*

**In plain words**
We look for 2050 bus terminals within **200 m** of the hub and take the largest one:

| Found within 200 m | Class |
|---|---|
| Nothing | 0 |
| Night parking (חניון לילה) | 1 |
| Small / medium terminal | 2 |
| Large terminal / integrated facility | 3 |

**Example**

| Hub | Terminal | Class | Grade |
|---|---|---|---|
| A | Large | 3 | **10.0** |
| B | None | 0 | **1.0** |
| C | Small/medium | 2 | **7.0** |

**Where to look:** sheet `6_BusTerminal`.

**Why we do it:** feeder buses are the first and last mile of most trips. A terminal next to the hub means the transfer is planned for.

---

## Summary of the five grades (example)

| Hub | Location | Service | Demand | Pop & jobs | Terminal |
|---|---|---|---|---|---|
| A | 1.0 | 7.16 | 8.25 | 10.0 | 10.0 |
| B | 1.0 | 1.00 | 1.00 | 1.0 | 1.0 |
| C | 10.0 | 10.00 | 10.00 | 5.66 | 7.0 |

**Slide idea:** a heat-map table like this one is the clearest single picture of "why hub X beats hub Y".

---

## Step 7 — Monte Carlo: how much should each question count?

**Slide title:** *Instead of arguing about weights, we try 10,000 random weightings and take the average.*

**In plain words**
How important is location compared with demand? Reasonable people disagree. So instead of picking one set of weights:

1. Draw **5 random numbers**, one per criterion.
2. If any of them is above **0.5**, throw the set away and draw again. This stops any single criterion from dominating.
3. Scale the five numbers so they add up to **100%**. That is one "weighting".
4. Repeat **10,000 times**, separately for each tier.
5. The workbook shows the **average weight** of each criterion.

Think of it as asking 10,000 imaginary experts, each with their own priorities, and listening to all of them.

**What comes out (default run):** the averages land very close to **20% for each criterion**.

| | Location | Service | Demand | Pop & jobs | Terminal |
|---|---|---|---|---|---|
| Average weight (≈) | 20% | 20% | 20% | 20% | 20% |

**A useful shortcut.** Averaging the score over 10,000 weightings gives exactly the same result as scoring once with the average weights. That's why the workbook can show the final score as a simple sum.

**Where to look:**
- `7b_MC_Draws`: all 10,000 random draws per tier (stored as values, generated from the same seed as the run, so they are identical)
- `7_MC_Weights`: the average weight per criterion and tier

**Why we do it:** it makes the ranking robust. No single criterion can dominate, and the result doesn't depend on one person's choice of weights.

> **Be precise if asked:** the 50% cap applies to the raw random draw, before scaling to 100%. A single weighting can still end up giving one criterion more than 50%. On average, though, every criterion counts the same.

---

## Step 8 — Final score: grades × weights, added up

**Slide title:** *A hub's score is its five grades, weighted and added, and you can see how many points each criterion contributes.*

**In plain words**

```
score = Σ (grade × average weight)
```

Because the weights add up to 100%, the score stays on the same **1-to-10** scale.

**Example (weights ≈ 20% each)**

| Hub | Location | Service | Demand | Pop & jobs | Terminal | **Score** |
|---|---|---|---|---|---|---|
| A | 0.20 | 1.43 | 1.65 | 2.00 | 2.00 | **7.28** |
| B | 0.20 | 0.20 | 0.20 | 0.20 | 0.20 | **1.00** |
| C | 2.00 | 2.00 | 2.00 | 1.13 | 1.40 | **8.53** |

(each cell = grade × 20%, the "points" that criterion adds)

**Where to look:** sheet `8_FinalScore`. The *Points: …* columns show the contributions; **TOTAL SCORE** is the green bold column.

**Why we do it:** the points columns answer the question everyone asks, "*why* is this hub ahead?". For example, C beats A mainly on location (2.00 vs 0.20 points).

---

## Step 9 — Ranking: who competes with whom

**Slide title:** *National hubs are ranked nationwide; metropolitan and local hubs are ranked within their own metropolitan area.*

**In plain words**
A higher score means a better rank, but the competition depends on the tier:

| Tier | Competes with |
|---|---|
| **ארצי National** | All national hubs in the country |
| **מטרופוליני Metropolitan** | Metropolitan hubs in the **same metro area** |
| **עירוני Local** | Local hubs in the **same metro area** |

**Example**

| Hub | Metro area | Score | Rank |
|---|---|---|---|
| A | Tel Aviv | 7.28 | **1** in Tel Aviv |
| B | Tel Aviv | 1.00 | **2** in Tel Aviv |
| C | South | 8.53 | **1** in the South |

**Where to look:**
- `8_FinalScore`: three ranks: overall, within the tier, and the official **RANK (RankByHubTypeMetro)**
- `9_Ranking`: the clean ranking table, tier by tier and area by area

**Why we do it:** a metropolitan hub in Haifa should be compared with other Haifa hubs, not with Tel Aviv's. Each region gets its own priority list.

---

## Hub Explorer: one hub, the whole story on one page

**Slide title:** *Pick any hub and see its whole calculation, from raw data to rank, on one screen.*

**In plain words**
Type or pick a group number in the yellow cell. The sheet shows:
- name, tier, metro area, passengers, modes, lines, eligibility
- for each of the five criteria: raw value → tier min/max → grade → weight → points
- the total score and the three ranks

**Where to look:** sheet `Hub_Explorer`.

**Slide idea:** do a live demo with a hub the audience knows. It's the most convincing moment of the presentation.

---

## Checks: proof that Excel and the pipeline agree

**Slide title:** *The workbook recalculates everything itself, and its results match the pipeline's to the last decimal.*

**In plain words**
For every hub, the `Checks` sheet puts side by side:
- the pipeline's own value (blue, fixed), and
- the workbook's formula result

for each grade, the total score, the rank and the tier. At the top it reports the **largest score difference**, the **number of rank mismatches** and the **number of tier mismatches**. With unchanged parameters, all three should be **0**.

If you change a parameter, the differences show you exactly which hubs moved.

**Where to look:** sheet `Checks`.

**Why we do it:** trust. The Excel is not a separate model that may drift. It is the same calculation, and it proves it.

---

## What you can safely change (and what you can't)

| You can… | Effect |
|---|---|
| Change a **yellow** parameter (e.g. mode weight, jobs share, Center region weight) | Every grade, score and rank recalculates |
| Pick a hub in `Hub_Explorer` | See its full calculation |
| Filter or sort `9_Ranking` | Explore the ranking |

| You can't (in this workbook) | Why |
|---|---|
| Add or remove hubs | The list of scored hubs is fixed by the pipeline run |
| Re-draw the Monte Carlo | Excel can't reproduce Python's random numbers, so the draws are stored as values |
| Create a new tier | It would have no Monte Carlo weights (you'll see an `#N/A` error) |

Requires Excel 2019 or Microsoft 365 (uses `MINIFS` / `MAXIFS`).

---

## Recap: the whole process in five lines

1. **Filter:** only places with ≥ 1,000 passengers and ≥ 2 modes (not rail-only) are hubs.
2. **Sort into leagues:** National, Metropolitan, Local.
3. **Ask five questions:** location, service, demand, population & jobs, bus terminal, each graded 1–10 within the league.
4. **Weigh fairly:** 10,000 random weightings, averaged (≈ 20% each).
5. **Rank:** national hubs nationwide, everyone else within their metro area.

---

## Suggested slide outline

Read just the titles in order. They tell the whole story:

1. Every hub is scored the same way, on five questions, inside its own league, and every number can be checked.
2. All the rules live in one place, so changing a rule never means hunting through formulas.
3. Only places with real demand and a real choice of modes become hubs, and each is put in its own league.
4. Every criterion becomes a 1-to-10 grade, comparing a hub only with others of the same tier.
5. Location gives an advantage to the periphery, and more to the metropolitan core.
6. Service rewards lines of high-capacity modes, plus a bonus for variety.
7. Demand counts on a log scale, so mega-stations don't drown everyone else.
8. Catchment counts 2050 residents and jobs nearby, with the closest counting most.
9. A planned bus terminal within 200 m signals strong bus integration.
10. Instead of arguing about weights, we try 10,000 random weightings and average them.
11. A hub's score is its weighted grades, and you can see what each criterion contributes.
12. National hubs are ranked nationwide; the others within their metro area.
13. Pick any hub and see its whole calculation on one screen *(live demo)*.
14. The workbook matches the pipeline exactly.
15. **Call to action:** review the parameters on the `Parameters` sheet, test the hubs you know in `Hub_Explorer`, and send any rule you disagree with as a proposed parameter change, so the next run reflects it.

---

## Glossary

| Term | Meaning |
|---|---|
| מתח"מ | Integrated transport hub: a place where people transfer between modes |
| ארצי / מטרופוליני / עירוני | National / Metropolitan / Local tier |
| Hub group | Stations within about 120 m of each other, treated as one hub |
| Mode | Type of transit: BRT, LRT (רק"ל), Metro, Suburban/Interurban/High-speed rail |
| Line | One route in one direction |
| Raw value | A criterion's value in its own unit (passengers, weighted lines, …) |
| Grade / normalised score | The raw value turned into 1–10 within the tier |
| log₁₀ | "Number of digits": 1,000 → 3, 10,000 → 4, 100,000 → 5 |
| Distance decay | Nearer people and jobs count more than farther ones |
| Monte Carlo | Repeating a calculation many times with random inputs and averaging |
| Seed | The starting number for the random draws; same seed gives the same draws |
| Tier minimum / maximum | The lowest / highest raw value among hubs of the same tier |

---

*Source of truth: `src/pipeline/calc_workbook.py` (how the workbook is built) and `src/pipeline/scoring.py` (the pipeline's scoring). The example hubs are illustrative; real values are in the workbook produced by `hubs run`.*
