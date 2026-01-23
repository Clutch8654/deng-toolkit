# Marimo Notebook Outline (Technical Peer Review) — v2

## 0. Front Matter

**Inputs:** None (metadata only)
**Outputs:** Rendered header cell

| Item | Content |
|------|---------|
| Title | `[EVENT]` Hazard Model: Technical Documentation & Peer Review |
| Version | Semantic version (e.g., v1.0.0) + Git SHA |
| Authors | Primary analyst, reviewers |
| Last Run | Auto-populated timestamp |
| Environment | Python version, key package versions (lifelines, polars, scikit-survival) |
| Data Access | Server names, required credentials, VPN notes |
| Run Instructions | `uv run marimo run notebook.py` or equivalent |
| Review Status | Draft / Under Review / Approved |

**Key checks:** Environment reproducibility; data access confirmed
**Notes for reviewers:** Confirm you can execute end-to-end before detailed review

---

## 0.5 Model Card (Governance Summary)

**Inputs:** Model metadata
**Outputs:** Single-page summary for governance

| Field | Content |
|-------|---------|
| **Model Name** | `[EVENT]` Hazard Model v`[VERSION]` |
| **Intended Use** | Risk stratification for `[DECISION]`; targeting interventions |
| **Out-of-Scope Use** | Causal inference; individual-level guarantees; automated decisions without human review |
| **Training Data** | `[SOURCE]`, `[DATE_RANGE]`, N=`[N]` |
| **Target Definition** | `[EVENT]` occurring after `[TIME_ORIGIN]` |
| **Primary Metric** | C-index = `[VALUE]` on held-out temporal test set |
| **Key Limitations** | `[LIMITATION_1]`; `[LIMITATION_2]`; `[LIMITATION_3]` |
| **Fairness Assessment** | Subgroup analysis performed on `[SEGMENTS]`; no material disparities observed within available data |
| **Monitoring Plan** | `[CADENCE]` performance tracking; drift detection on `[FEATURES]` |
| **Owner** | `[NAME/TEAM]` |
| **Escalation Contact** | `[NAME/EMAIL]` |
| **Approval Date** | `[DATE]` or Pending |

**Key checks:** All fields populated; limitations honest
**Notes for reviewers:** Use this card for quick governance review; details follow

---

## 1. Executive Summary (Technical)

**Inputs:** Final model outputs
**Outputs:** Summary table, key metrics

### 1.1 Problem Statement
- Business context for predicting `[EVENT]`
- Why time-to-event framing vs. point-in-time classification
- Decision(s) this model enables

### 1.2 Modeling Stance: Predictive vs. Inferential

| Aspect | This Model's Approach |
|--------|----------------------|
| **Primary purpose** | Risk stratification and targeting (PREDICTIVE) |
| **Interpretation of coefficients** | Associational drivers, not causal effects |
| **Emphasis** | Calibrated risk scores and ranking accuracy > p-values |
| **What we can claim** | "`[FEATURE]` is associated with higher/lower `[EVENT]` risk" |
| **What we cannot claim** | "`[FEATURE]` causes `[EVENT]`" without further causal analysis |

> **Note:** Hazard ratios (HRs) throughout this document represent conditional associations after adjusting for other model features. They should NOT be interpreted as causal effects. For causal inference, a separate analysis with explicit confounding control (DAG, instrumental variables, etc.) would be required.

### 1.3 Model Summary Table

| Metric | Value | Interpretation |
|--------|-------|----------------|
| Model Type | Cox PH / Discrete-time logistic | — |
| C-index (test) | `[VALUE]` | Discrimination (ranking accuracy) |
| Lift in top decile | `[X]`× | Targeting efficiency |
| Top 10% captures | `[Y]%` of events | Concentration of risk |
| Calibration slope | `[VALUE]` | 1.0 = perfect calibration |
| N (events/censored) | `[N_events]` / `[N_censored]` | Statistical power |
| Key risk factors | Top 3 features | Associational drivers |

### 1.4 Key Findings (3-5 bullets)
### 1.5 Limitations Summary
### 1.6 Recommendation

**Key checks:** Summary consistent with detailed sections; predictive stance clear
**Notes for reviewers:** Read this first; flag any surprises before diving deeper

---

## 2. Problem Definition & Target Specification

**Inputs:** Business requirements, data dictionaries
**Outputs:** Formal definitions table

### 2.1 Event Definition

| Component | Definition | Rationale |
|-----------|------------|-----------|
| `[EVENT]` | Precise operational definition | Why this captures the business outcome |
| Positive case | Exact criteria (status codes, flags) | — |
| Negative case | What does NOT count as event | Exclusions matter |

### 2.2 Time Origin (`[TIME_ORIGIN]`)

| Component | Definition |
|-----------|------------|
| Time zero | When clock starts (e.g., first activation date) |
| Justification | Why this is the correct "at-risk" starting point |
| Edge cases | How handled (e.g., missing dates → exclude) |

### 2.3 Censoring Definition

| Type | Definition | Assumption |
|------|------------|------------|
| Right censoring | Still active at observation cutoff | Non-informative censoring assumed |
| Administrative censoring | Study end date: `[DATE]` | — |
| Loss to follow-up | `[CRITERIA]` | Document if present |

**Censoring assumption justification:**
- Non-informative censoring assumed: censoring mechanism is independent of the unobserved event time
- Evidence: `[ARGUMENT]` (e.g., censoring is purely administrative, or censoring rate similar across risk groups)
- Potential violations: `[RISKS]`

### 2.4 Time-at-Risk Definition
- Duration column calculation: `[FORMULA]`
- Unit of time: `[UNIT]` (days / months / discrete intervals)
- Minimum observation period filter: `[THRESHOLD]` (e.g., >180 days)
- Justification for minimum: `[REASON]`

### 2.5 Competing Risks & Recurrent Events

| Decision Point | This Analysis | Rationale |
|----------------|---------------|-----------|
| **Competing events exist?** | Yes / No | `[LIST]` if yes |
| **Competing events handling** | Cause-specific hazard / Fine-Gray / Treat as censoring | `[JUSTIFICATION]` |
| **Recurrent events possible?** | Yes / No | Can `[ENTITY]` experience `[EVENT]` multiple times? |
| **Recurrent events handling** | First event only / Andersen-Gill / PWP / Other | `[JUSTIFICATION]` |

**If competing risks:**
- Competing event definition: `[DEFINITION]`
- Are competing events truly "precluding" (make `[EVENT]` impossible) or "informative censoring" (correlated with `[EVENT]` risk)?
- Interpretation: Cause-specific = "hazard among those still at risk"; Fine-Gray = "cumulative incidence accounting for competing events"

**If recurrent events possible but using first-event-only:**
- Business justification: `[REASON]` (e.g., intervention targets first occurrence; subsequent events have different dynamics)

**Key checks:** Definitions unambiguous; no overlap between event/censoring; competing risks addressed
**Notes for reviewers:** This section defines ground truth—scrutinize heavily

---

## 3. Cohort Construction

**Inputs:** Raw data tables
**Outputs:** Cohort flow diagram, final analytic dataset

### 3.1 Inclusion Criteria
| Criterion | Filter Logic | N Remaining |
|-----------|--------------|-------------|
| Has `[ENTITY]` record | `table.filter(...)` | `[N]` |
| Within date range | `[START]` to `[END]` | `[N]` |
| Minimum tenure | `> [DAYS]` days | `[N]` |
| ... | ... | ... |

### 3.2 Exclusion Criteria
| Criterion | Rationale | N Excluded |
|-----------|-----------|------------|
| Test accounts | Not real customers | `[N]` |
| Data quality flags | Missing critical fields | `[N]` |
| ... | ... | ... |

### 3.3 Cohort Flow Diagram
```
[VISUAL: Sankey or waterfall showing N at each step]
```

### 3.4 Final Cohort Summary
| Metric | Value |
|--------|-------|
| Total N | `[N]` |
| Events | `[N_events]` (`[%]`) |
| Censored | `[N_censored]` (`[%]`) |
| Median follow-up | `[TIME]` |
| Event rate | `[RATE]` per 1,000 person-`[UNIT]` |

**Key checks:** No unexpected drops; exclusions justified
**Notes for reviewers:** Verify exclusions don't introduce selection bias

---

## 4. Data Sources & Definitions

**Inputs:** Database schemas, ETL documentation
**Outputs:** Data dictionary, lineage diagram

### 4.1 Data Source Inventory

| Source | Server | Database.Table | Grain | Purpose |
|--------|--------|----------------|-------|---------|
| `[SOURCE_1]` | `[SERVER]` | `[DB.TABLE]` | `[GRAIN]` | `[PURPOSE]` |
| ... | ... | ... | ... | ... |

### 4.2 Join Logic
```sql
-- Pseudocode showing key joins
[TABLE_A].key → [TABLE_B].key → [TABLE_C].key
```

### 4.3 Timestamp Logic
| Field | Source | Timezone | Granularity |
|-------|--------|----------|-------------|
| `[FIELD]` | `[TABLE.COL]` | UTC / Local | Day / Second |

### 4.4 Label Construction
- Step-by-step derivation of `event_occurred` and `duration`
- Code reference: `[module/function]`

### 4.5 Leakage Controls
| Potential Leakage | Control Implemented |
|-------------------|---------------------|
| Future information in features | Features use only data available at `[TIME_ORIGIN]` |
| Target encoded in features | `[SPECIFIC_CHECK]` |
| Temporal ordering | Train/test split respects time |

### 4.6 Dataset Lineage Diagram
```
[RAW_TABLE_1] ──┐
                ├──► [INTERMEDIATE_1] ──┐
[RAW_TABLE_2] ──┘                       ├──► [ANALYTIC_DATASET]
                                        │
[RAW_TABLE_3] ──────────────────────────┘
```

**Key checks:** All sources documented; joins validated; no leakage
**Notes for reviewers:** Request sample rows if definitions unclear

---

## 5. Survival Data Sanity Checks

**Inputs:** Analytic dataset with event/duration
**Outputs:** Diagnostic plots, sanity statistics

> **Purpose:** Validate that survival data is correctly constructed BEFORE any feature engineering or modeling. Catches label/time-origin bugs and weird censoring patterns.

### 5.1 Event-Time Distribution

```
[PLOT: Histogram of duration for events vs. censored observations]
[PLOT: ECDF of duration, stratified by event status]
```

| Statistic | Events | Censored |
|-----------|--------|----------|
| N | `[N]` | `[N]` |
| Mean duration | `[TIME]` | `[TIME]` |
| Median duration | `[TIME]` | `[TIME]` |
| Min | `[TIME]` | `[TIME]` |
| Max | `[TIME]` | `[TIME]` |

**Sanity checks:**
- [ ] Events have reasonable duration distribution (not clustered at min/max)
- [ ] Censored observations have longer durations on average (expected for right-censoring)
- [ ] No impossible durations (negative, > study period)

### 5.2 Overall Kaplan-Meier Curve

```
[PLOT: KM survival curve with 95% CI and number-at-risk table]
```

| Time Point | Survival Probability | 95% CI | N at Risk |
|------------|---------------------|--------|-----------|
| `[T1]` | `[S(t)]` | `[CI]` | `[N]` |
| `[T2]` | `[S(t)]` | `[CI]` | `[N]` |
| ... | ... | ... | ... |

**Sanity checks:**
- [ ] Curve shape matches domain expectation (e.g., early vs. late events)
- [ ] No unexpected plateaus or drops
- [ ] Median survival time plausible

### 5.3 KM Curves by Key Segments (Directional Validation)

```
[PLOT: KM curves stratified by 2-3 obvious segments with known directional effects]
Example: Tenure band, customer size, product type
```

**Expected directions:**
| Segment | Expected Effect | Observed | ✓/✗ |
|---------|-----------------|----------|-----|
| `[SEGMENT_1]` | Higher risk | `[OBSERVED]` | `[CHECK]` |
| `[SEGMENT_2]` | Lower risk | `[OBSERVED]` | `[CHECK]` |

**Sanity checks:**
- [ ] Known risk factors show expected directional effect
- [ ] Curves separate in expected direction
- [ ] If unexpected: investigate before proceeding

### 5.4 Censoring Pattern Analysis

```
[PLOT: Censoring rate over follow-up time]
[PLOT: Cumulative censoring by calendar time (if relevant)]
```

| Follow-up Band | N Entering | N Events | N Censored | Censoring % |
|----------------|------------|----------|------------|-------------|
| 0-90 days | `[N]` | `[N]` | `[N]` | `[%]` |
| 91-180 days | `[N]` | `[N]` | `[N]` | `[%]` |
| ... | ... | ... | ... | ... |

**Sanity checks:**
- [ ] Not heavily censored early (would indicate data quality issues)
- [ ] Censoring pattern consistent with administrative censoring (end of study)
- [ ] No suspicious spikes in censoring at specific times

### 5.5 Person-Time Accounting

| Metric | Value |
|--------|-------|
| Total person-`[UNIT]` at risk | `[TOTAL]` |
| Events | `[N_EVENTS]` |
| Event rate per 1,000 person-`[UNIT]` | `[RATE]` |
| Expected events at baseline rate | `[EXPECTED]` |

**Sanity checks:**
- [ ] Event rate consistent with domain knowledge
- [ ] Person-time totals are plausible

### 5.6 Duplicate / Overlapping Risk Checks

| Check | Result |
|-------|--------|
| Duplicate `[ENTITY_ID]` | `[N]` found → `[HANDLING]` |
| Overlapping risk periods (if recurrent) | `[N]` found → `[HANDLING]` |
| Multiple events per entity | `[N]` entities → `[HANDLING]` |

**Key checks:** All sanity checks pass; directional effects match expectations
**Notes for reviewers:** Any failures here require investigation before model fitting

---

## 6. Feature Engineering

**Inputs:** Analytic dataset, domain knowledge
**Outputs:** Feature matrix, feature dictionary

### 6.1 Feature Inventory

| Feature | Definition | Type | Window | Source | Leakage Risk |
|---------|------------|------|--------|--------|--------------|
| `[FEATURE_1]` | `[CALCULATION]` | Binary/Continuous | `[WINDOW]` | `[TABLE]` | `[LOW/MED/HIGH]` |
| ... | ... | ... | ... | ... | ... |

### 6.2 Time Windows & Feature Availability

- **Principle:** Features computed using ONLY information available at or before `[TIME_ORIGIN]`
- **Window definitions:**

| Feature Group | Lookback Window | Anchor Point |
|---------------|-----------------|--------------|
| Static attributes | As of `[TIME_ORIGIN]` | — |
| Behavioral | `[N]` days before `[TIME_ORIGIN]` | `[TIME_ORIGIN]` |
| ... | ... | ... |

### 6.3 Time-Varying Covariates (if applicable)

| Covariate | Update Frequency | Handling | Leakage Control |
|-----------|------------------|----------|-----------------|
| `[COVARIATE]` | `[FREQUENCY]` | Extended Cox / Discrete intervals | Feature value as of interval START |

**If discrete-time model:**
- Person-period expansion: Each `[ENTITY]` × interval row uses features available at INTERVAL START
- Verification: `[CODE_REFERENCE]` confirms feature timestamp < interval start

### 6.4 Transformations

| Original | Transformation | Rationale |
|----------|----------------|-----------|
| `[VAR]` | Log / Binning / Polynomial | Linearity assumption / Interpretability |

### 6.5 Missingness Strategy

| Feature | Missing % | Strategy | Justification |
|---------|-----------|----------|---------------|
| `[FEATURE]` | `[%]` | Fill with 0 / Impute / Indicator | `[REASON]` |

### 6.6 Outliers

- Detection method: IQR / Domain limits / `[METHOD]`
- Handling: Winsorize at `[PERCENTILE]` / Exclude / Flag

### 6.7 Encoding

- Categorical: One-hot / Target encoding (with nested CV to prevent leakage)
- Ordinal: Numeric mapping

### 6.8 Features Excluded (Policy/Fairness)

| Feature | Reason for Exclusion |
|---------|---------------------|
| `[FEATURE]` | Proxy for protected attribute |
| `[FEATURE]` | Unstable / data quality concerns |
| `[FEATURE]` | Regulatory constraint |

**Key checks:** No look-ahead bias; missingness handled consistently; exclusions documented
**Notes for reviewers:** Verify feature windows don't leak future info

---

## 7. Modeling Approach

**Inputs:** Feature matrix, survival outcomes
**Outputs:** Fitted model object, specification details

### 7.1 Model Selection Rationale

| Consideration | Cox PH | Discrete-Time Logistic |
|---------------|--------|------------------------|
| Continuous time | ✓ Native | Requires binning |
| Time-varying covariates | Extended Cox | Natural via panel structure |
| Baseline hazard | Unspecified (semi-parametric) | Fully specified (time dummies/spline) |
| Interpretability | Hazard ratios | Odds ratios per interval |
| Prediction output | S(t), h(t) | P(event in interval \| survived to interval) |
| **Choice for this analysis** | `[SELECTED]` | `[REASON]` |

### 7.2 Model Specification

**If Cox PH:**
```python
CoxPHFitter(
    penalizer=0.1,        # L2 regularization
    l1_ratio=0.0,         # Pure ridge
    strata=['SEGMENT'],   # If stratified (separate baseline hazards)
)
```

**If Discrete-Time:**
```python
# Interval definition
intervals = [0, 90, 180, 365, 730, ...]  # days

# Time handling
time_representation = 'dummies' / 'spline' / 'linear'
# Justification: [REASON]

# Model
LogisticRegression(
    penalty='l2',
    C=1.0,
    class_weight='balanced',  # If imbalanced intervals
)
```

### 7.3 Baseline Hazard / Time Effects

**For Cox PH:**
- Baseline hazard: Left unspecified (semi-parametric)
- Stratification: `[VARIABLES]` have separate baseline hazards (if used)
- Time interactions: `[VARIABLES]` × time (if PH violated and addressed)

```
[PLOT: Estimated cumulative baseline hazard H₀(t)]
```

**For Discrete-Time:**
- Time representation: `[DUMMIES/SPLINE/OTHER]`
- Justification: `[REASON]` (e.g., flexibility vs. smoothness)
- Number of parameters for time: `[N]`

```
[PLOT: Estimated baseline hazard by interval (time coefficients)]
```

### 7.4 Regularization

| Aspect | Specification |
|--------|---------------|
| Type | L1 / L2 / Elastic Net |
| Tuning method | `[METHOD]` (time-respecting CV) |
| Selected penalty | `[VALUE]` |
| Justification | `[REASON]` |

### 7.5 Stratification (if applicable)

- Strata variables: `[VARIABLES]`
- Rationale: Different baseline hazards by `[SEGMENT]`; allows features to have same HR across strata

### 7.6 Interactions

- Tested interactions: `[LIST]`
- Included in final model: `[LIST]` (if any)
- Selection criterion: `[CRITERION]`

### 7.7 Validation Design

| Split | N | Events | Date Range | Purpose |
|-------|---|--------|------------|---------|
| Train | `[N]` | `[N_events]` | `[START]` - `[END]` | Model fitting |
| Validation | `[N]` | `[N_events]` | `[START]` - `[END]` | Hyperparameter tuning |
| Test | `[N]` | `[N_events]` | `[START]` - `[END]` | Final evaluation |

**Temporal split design:**
- Split method: Calendar time cutoffs (NOT random)
- Train period ends: `[DATE]`
- Test period starts: `[DATE]`
- Gap period (if any): `[DURATION]` — to prevent leakage from lagged features

**Nested cross-validation (for hyperparameters):**
- Outer loop: Time-based splits (rolling origin / expanding window)
- Inner loop: Time-based splits within training folds
- Verification: No future data used in any fold

**Backtesting across multiple test windows:**

| Test Window | Train End | Test Period | N | Events | C-index |
|-------------|-----------|-------------|---|--------|---------|
| Window 1 | `[DATE]` | `[PERIOD]` | `[N]` | `[N]` | `[VALUE]` |
| Window 2 | `[DATE]` | `[PERIOD]` | `[N]` | `[N]` | `[VALUE]` |
| ... | ... | ... | ... | ... | ... |

**Key checks:** Temporal split used; no leakage in validation; stable across test windows
**Notes for reviewers:** Confirm train/test have similar feature distributions; check for temporal drift

---

## 8. Assumptions & Diagnostics

**Inputs:** Fitted model, residuals
**Outputs:** Diagnostic plots, assumption test results

### 8.1 Proportional Hazards Assumption (Cox PH)

| Test | Method | Result | Interpretation |
|------|--------|--------|----------------|
| Global test | Schoenfeld residuals | p = `[VALUE]` | `[PASS/INVESTIGATE]` |
| Per-covariate | Scaled Schoenfeld vs. time | `[TABLE]` | — |

```
[PLOT: Scaled Schoenfeld residuals vs. time for each covariate]
```

**Per-covariate results:**

| Covariate | Test Statistic | p-value | Interpretation |
|-----------|----------------|---------|----------------|
| `[FEATURE_1]` | `[VALUE]` | `[P]` | `[INTERPRETATION]` |
| ... | ... | ... | ... |

**If PH violated:**

| Violation | Severity | Remediation Applied |
|-----------|----------|---------------------|
| `[COVARIATE]` | Minor / Major | Stratified / Time interaction / None (acknowledged) |

### 8.2 Functional Form (Linearity)

| Continuous Covariate | Test | Result | Action |
|---------------------|------|--------|--------|
| `[VAR_1]` | Martingale residuals vs. covariate | `[LINEAR/NONLINEAR]` | `[TRANSFORM/KEEP]` |

```
[PLOT: Martingale residuals vs. continuous covariates with LOWESS smoother]
```

### 8.3 Influential Observations

| Metric | Threshold | Flagged N | Action |
|--------|-----------|-----------|--------|
| dfbeta | > 2/√n | `[N]` | `[INVESTIGATED/EXCLUDED]` |
| Deviance residuals | \|z\| > 2 | `[N]` | `[INVESTIGATED/EXCLUDED]` |

```
[PLOT: Influential observation diagnostics (dfbeta, deviance residuals)]
```

### 8.4 Discrete-Time Specific Diagnostics (if applicable)

| Diagnostic | Result |
|------------|--------|
| Interval width sensitivity | `[STABLE/SENSITIVE]` to `[CHANGE]` |
| Goodness-of-fit per interval (Hosmer-Lemeshow) | `[RESULTS]` |
| Time representation adequacy | `[ASSESSMENT]` |

### 8.5 Independence & Non-Informative Censoring

| Assumption | Assessment Method | Evidence |
|------------|-------------------|----------|
| Independent observations | `[METHOD]` | `[RESULT]` (e.g., no clustering issues) |
| Non-informative censoring | Comparison of censored vs. events | `[RESULT]` |

**Potential informative censoring concerns:**
- `[CONCERN_1]`: `[ASSESSMENT]`
- Mitigation: `[ACTION]`

**Key checks:** PH assumption validated (or violations addressed); functional forms appropriate
**Notes for reviewers:** Flag any concerning diagnostics for discussion

---

## 9. Model Evaluation

**Inputs:** Model predictions, test set outcomes
**Outputs:** Performance metrics, evaluation plots

### 9.1 Discrimination

| Metric | Train | Test | Interpretation |
|--------|-------|------|----------------|
| Harrell's C-index | `[VALUE]` | `[VALUE]` | Overall ranking ability |
| Time-dependent AUC (τ=`[T1]`) | `[VALUE]` | `[VALUE]` | Discrimination at horizon |
| Time-dependent AUC (τ=`[T2]`) | `[VALUE]` | `[VALUE]` | — |

```
[PLOT: Time-dependent AUC curve over multiple horizons]
```

### 9.2 Targeting Efficiency (Lift Analysis)

| Risk Decile | % of Population | % of Events Captured | Lift | Event Rate |
|-------------|-----------------|---------------------|------|------------|
| Top 10% | 10% | `[Y]%` | `[X]`× | `[RATE]` |
| Top 20% | 20% | `[Y]%` | `[X]`× | `[RATE]` |
| Top 30% | 30% | `[Y]%` | `[X]`× | `[RATE]` |
| ... | ... | ... | ... | ... |
| Bottom 30% | 30% | `[Y]%` | `[X]`× | `[RATE]` |

```
[PLOT: Cumulative lift curve / Lorenz curve]
[PLOT: Capture curve - % events captured vs. % population targeted]
```

### 9.3 Calibration

**Calibration by risk decile:**

| Decile | Mean Predicted Risk (τ=`[HORIZON]`) | Observed Event Rate | Ratio |
|--------|-------------------------------------|---------------------|-------|
| 1 (lowest) | `[P]` | `[O]` | `[R]` |
| ... | ... | ... | ... |
| 10 (highest) | `[P]` | `[O]` | `[R]` |

```
[PLOT: Calibration curve - predicted vs. observed by decile at τ=[HORIZON]]
```

**Calibration at multiple horizons:**

| Horizon τ | Calibration Slope | Calibration Intercept | Interpretation |
|-----------|-------------------|----------------------|----------------|
| `[T1]` (e.g., 90 days) | `[VALUE]` | `[VALUE]` | Slope=1, Int=0 is perfect |
| `[T2]` (e.g., 1 year) | `[VALUE]` | `[VALUE]` | — |
| `[T3]` (e.g., 2 years) | `[VALUE]` | `[VALUE]` | — |

```
[PLOT: Calibration curves at multiple horizons (small multiples)]
```

### 9.4 Brier Score & Integrated Metrics

| Metric | Value | Interpretation |
|--------|-------|----------------|
| Brier Score (τ=`[T1]`) | `[VALUE]` | Lower = better (0-0.25 typical range) |
| Brier Score (τ=`[T2]`) | `[VALUE]` | — |
| Integrated Brier Score (IBS) | `[VALUE]` | Overall calibration + discrimination |

```
[PLOT: Brier score over time (τ on x-axis, Brier on y-axis)]
```

### 9.5 Subgroup Performance

| Segment | N | Events | C-index | Calibration Slope | Notes |
|---------|---|--------|---------|-------------------|-------|
| `[SEGMENT_1]` | `[N]` | `[N]` | `[VALUE]` | `[VALUE]` | — |
| `[SEGMENT_2]` | `[N]` | `[N]` | `[VALUE]` | `[VALUE]` | — |

**Segments with notably different performance:**
- `[SEGMENT]`: `[ISSUE]` — `[INTERPRETATION]`

### 9.6 Temporal Stability (Backtesting)

| Test Period | C-index | Event Rate | Calibration Slope | Notes |
|-------------|---------|------------|-------------------|-------|
| `[PERIOD_1]` | `[VALUE]` | `[RATE]` | `[VALUE]` | — |
| `[PERIOD_2]` | `[VALUE]` | `[RATE]` | `[VALUE]` | — |
| `[PERIOD_3]` | `[VALUE]` | `[RATE]` | `[VALUE]` | — |

```
[PLOT: C-index and calibration over rolling test windows]
```

### 9.7 Comparison to Baseline

| Model | C-index | Δ vs. Baseline | Top-decile Lift |
|-------|---------|----------------|-----------------|
| Baseline (tenure only) | `[VALUE]` | — | `[X]`× |
| + Key feature | `[VALUE]` | `[DELTA]` | `[X]`× |
| Full model | `[VALUE]` | `[DELTA]` | `[X]`× |

**Key checks:** No train/test gap; stable across subgroups and time; calibration acceptable
**Notes for reviewers:** Investigate any subgroup with notably worse performance

---

## 10. Uncertainty & Robustness

**Inputs:** Model, sensitivity parameters
**Outputs:** Confidence intervals, sensitivity analysis results

### 10.1 Coefficient Confidence Intervals

| Feature | HR | 95% CI | p-value | Significant? |
|---------|-----|--------|---------|--------------|
| `[FEATURE_1]` | `[HR]` | [`[LOWER]`, `[UPPER]`] | `[P]` | `[Y/N]` |
| ... | ... | ... | ... | ... |

```
[PLOT: Forest plot with confidence intervals, sorted by HR]
```

### 10.2 Bootstrap Analysis

| Metric | Point Estimate | Bootstrap 95% CI (N=`[B]`) |
|--------|----------------|---------------------------|
| C-index | `[VALUE]` | [`[LOWER]`, `[UPPER]`] |
| Top-decile lift | `[VALUE]` | [`[LOWER]`, `[UPPER]`] |
| Key HR (`[FEATURE]`) | `[VALUE]` | [`[LOWER]`, `[UPPER]`] |

### 10.3 Sensitivity Analyses

| Sensitivity Test | Variation | C-index | Key HR Change | Conclusion |
|------------------|-----------|---------|---------------|------------|
| Censoring definition | Alternative cutoff date | `[VALUE]` | `[DELTA]` | `[ROBUST/SENSITIVE]` |
| Feature window | 90d vs. 180d lookback | `[VALUE]` | `[DELTA]` | `[ROBUST/SENSITIVE]` |
| Cohort definition | Include/exclude `[GROUP]` | `[VALUE]` | `[DELTA]` | `[ROBUST/SENSITIVE]` |
| Minimum tenure | 90d vs. 180d vs. 365d | `[VALUE]` | `[DELTA]` | `[ROBUST/SENSITIVE]` |
| Time origin | Alternative definition | `[VALUE]` | `[DELTA]` | `[ROBUST/SENSITIVE]` |
| Competing risks handling | Cause-specific vs. censor | `[VALUE]` | `[DELTA]` | `[ROBUST/SENSITIVE]` |

### 10.4 Feature Ablation

| Features Removed | C-index | Δ | Interpretation |
|------------------|---------|---|----------------|
| None (full model) | `[VALUE]` | — | Baseline |
| `[FEATURE_1]` | `[VALUE]` | `[DELTA]` | Importance of feature |
| `[FEATURE_GROUP]` | `[VALUE]` | `[DELTA]` | Importance of group |

### 10.5 Robustness Summary

| Category | Assessment |
|----------|------------|
| Conclusions robust to | `[LIST]` |
| Sensitive to | `[LIST]` |
| Not tested | `[LIST]` |
| Overall confidence level | High / Moderate / Low |

**Key checks:** Key findings stable across sensitivity analyses
**Notes for reviewers:** Challenge any sensitivity not tested

---

## 11. Interpretability

**Inputs:** Fitted model
**Outputs:** Effect interpretations, partial effect plots

### 11.1 Associational Effect Interpretation Table

> **Reminder:** These are ASSOCIATIONAL effects, not causal. HRs represent conditional associations after adjusting for other model features.

| Feature | HR | Plain Language (Association) | Business Relevance |
|---------|-----|------------------------------|-------------------|
| `[FEATURE_1]` = 1 | `[HR]` | Associated with `[HR]`× higher/lower hazard of `[EVENT]` | `[RELEVANCE]` |
| ... | ... | ... | ... |

### 11.2 Effect Size Classification

| Effect Size | HR Threshold | Features |
|-------------|--------------|----------|
| Large | HR > 2.0 or < 0.5 | `[LIST]` |
| Moderate | HR 1.5-2.0 or 0.5-0.67 | `[LIST]` |
| Small | HR 1.2-1.5 or 0.67-0.83 | `[LIST]` |
| Negligible | HR 0.83-1.2 | `[LIST]` |

### 11.3 Survival Curves by Key Factors

```
[PLOT: KM or model-based survival curves stratified by top 2-3 risk factors]
```

### 11.4 Risk Profiles (Archetypes)

| Profile | Feature Values | Predicted 1-Year Risk | Predicted Median Survival |
|---------|----------------|----------------------|---------------------------|
| High-risk archetype | `[VALUES]` | `[RISK]` | `[TIME]` |
| Average | `[VALUES]` | `[RISK]` | `[TIME]` |
| Low-risk archetype | `[VALUES]` | `[RISK]` | `[TIME]` |

```
[PLOT: Predicted survival curves for archetypical profiles]
```

### 11.5 SHAP / Permutation Importance (if used — with caveats)

> **Caveats:**
> - SHAP for survival models requires careful interpretation (not directly applicable to hazards)
> - Feature importance ≠ causal effect
> - Used for EXPLORATORY analysis only, not inference
> - Interactions may not be captured correctly

```
[PLOT: SHAP summary — IF APPROPRIATE AND CAVEATED]
```

### 11.6 Risk Stratification Tiers

| Risk Tier | Definition | N | Event Rate | 1-Year Risk | Median Survival |
|-----------|------------|---|------------|-------------|-----------------|
| High | Top decile | `[N]` | `[RATE]` | `[RISK]` | `[TIME]` |
| Medium | Deciles 4-9 | `[N]` | `[RATE]` | `[RISK]` | `[TIME]` |
| Low | Bottom 3 deciles | `[N]` | `[RATE]` | `[RISK]` | `[TIME]` |

```
[PLOT: KM curves by risk tier with number-at-risk table]
```

**Key checks:** Interpretations consistent with domain knowledge; caveats clear
**Notes for reviewers:** Flag any counterintuitive findings for discussion

---

## 12. Fairness & Policy Compliance

**Inputs:** Model predictions, segment definitions
**Outputs:** Fairness metrics, policy compliance assessment

### 12.1 Subgroup Performance Parity

| Segment | N | Events | C-index | Calibration Slope | FPR at τ | FNR at τ |
|---------|---|--------|---------|-------------------|----------|----------|
| `[GROUP_A]` | `[N]` | `[N]` | `[VALUE]` | `[VALUE]` | `[VALUE]` | `[VALUE]` |
| `[GROUP_B]` | `[N]` | `[N]` | `[VALUE]` | `[VALUE]` | `[VALUE]` | `[VALUE]` |

**Disparity assessment:**
- Discrimination parity: Δ C-index = `[VALUE]` (threshold: < 0.05)
- Calibration parity: Δ slope = `[VALUE]` (threshold: within `[RANGE]`)
- Error rate parity: Δ FPR = `[VALUE]`, Δ FNR = `[VALUE]`

### 12.2 Feature-Level Fairness Review

| Feature | Potential Concern | Assessment |
|---------|-------------------|------------|
| `[FEATURE]` | Proxy for `[ATTRIBUTE]`? | `[INCLUDED/EXCLUDED]` — `[REASON]` |

### 12.3 Policy Constraints

| Constraint | Compliance Status |
|------------|-------------------|
| `[REGULATION_1]` | `[COMPLIANT/ACTION_NEEDED]` |
| No use of `[PROTECTED_ATTRIBUTE]` | `[COMPLIANT]` |
| Human review required for `[ACTION]` | `[DESIGNED_IN]` |

### 12.4 Fairness Monitoring Plan

| Metric | Monitoring Frequency | Alert Threshold |
|--------|---------------------|-----------------|
| Subgroup C-index parity | `[FREQUENCY]` | Δ > `[VALUE]` |
| Calibration parity | `[FREQUENCY]` | Slope outside `[RANGE]` |

**Summary statement:**
> Fairness checks performed across available segments (`[LIST]`). No material disparities observed within the limits of available data. Ongoing monitoring planned per above schedule.

**Key checks:** Fairness metrics computed; policy constraints documented
**Notes for reviewers:** Challenge segment definitions and thresholds

---

## 13. Operationalization

**Inputs:** Model, business requirements
**Outputs:** Deployment specification

### 13.1 Scoring Cadence

| Aspect | Specification |
|--------|---------------|
| Frequency | Daily / Weekly / Monthly |
| Trigger | Scheduled / Event-driven |
| Latency requirement | `[TIME]` |

### 13.2 Risk Score Definition

> **Critical:** Specify exactly what the score represents to prevent implementation errors.

| Score Type | Definition | Range | Interpretation |
|------------|------------|-------|----------------|
| **Primary output** | Predicted risk of `[EVENT]` by horizon τ = `[TIME]` | 0-1 | P(event within τ \| covariates) |
| Alternative: Hazard ratio | Relative hazard vs. baseline | 0-∞ | Not directly interpretable as probability |

**Horizon-specific risk:**

| Use Case | Horizon τ | Score Definition |
|----------|-----------|------------------|
| Immediate intervention | `[SHORT]` (e.g., 90 days) | P(event within `[SHORT]`) |
| Planning / capacity | `[MEDIUM]` (e.g., 1 year) | P(event within `[MEDIUM]`) |

### 13.3 Threshold / Decision Policy

> **Note:** Thresholds are on predicted risk by horizon τ = `[HORIZON]`, NOT instantaneous hazard.

| Risk Tier | Threshold (P at τ=`[HORIZON]`) | Action | Expected Volume per `[PERIOD]` |
|-----------|-------------------------------|--------|-------------------------------|
| High | > `[T1]` (e.g., > 30%) | `[HIGH_RISK_ACTION]` | `[N]` |
| Medium | `[T2]` - `[T1]` (e.g., 15-30%) | `[MEDIUM_ACTION]` | `[N]` |
| Low | < `[T2]` (e.g., < 15%) | `[LOW_ACTION]` | `[N]` |

**Threshold selection rationale:**
- `[T1]` chosen to capture top `[X]%` of predicted events while limiting volume to `[CAPACITY]`
- `[T2]` chosen based on `[RATIONALE]`

### 13.4 Decision Curve Analysis

```
[PLOT: Net benefit vs. threshold probability]
```

**Interpretation:**
- Model provides benefit over "treat all" for thresholds > `[P1]`
- Model provides benefit over "treat none" for thresholds < `[P2]`
- Recommended operating range: `[P1]` to `[P2]`

### 13.5 Capacity vs. Coverage Tradeoff

```
[PLOT: x-axis = number of interventions (capacity), y-axis = % of events addressable]
```

| Capacity (interventions per `[PERIOD]`) | % of Events Captured | % of Population |
|----------------------------------------|---------------------|-----------------|
| `[N1]` | `[Y1]%` | `[X1]%` |
| `[N2]` | `[Y2]%` | `[X2]%` |
| `[N3]` | `[Y3]%` | `[X3]%` |

**Recommendation:** At capacity = `[N]`, capture `[Y]%` of events by targeting top `[X]%` of risk scores.

### 13.6 Monitoring Plan

| Metric | Frequency | Alert Threshold | Response |
|--------|-----------|-----------------|----------|
| C-index (rolling `[WINDOW]`) | `[FREQ]` | < `[VALUE]` | `[ACTION]` |
| Calibration slope | `[FREQ]` | Outside `[RANGE]` | `[ACTION]` |
| Feature drift (PSI) | `[FREQ]` | > `[VALUE]` | `[ACTION]` |
| Event rate shift | `[FREQ]` | > `[%]` change | `[ACTION]` |
| Prediction volume anomaly | `[FREQ]` | > `[X]`σ from expected | `[ACTION]` |

### 13.7 Retraining Triggers

| Trigger | Threshold | Action |
|---------|-----------|--------|
| Performance degradation | C-index < `[VALUE]` for `[N]` consecutive periods | Retrain |
| Calibration drift | Slope outside `[RANGE]` | Recalibrate or retrain |
| Feature drift | PSI > `[VALUE]` | Investigate; potentially retrain |
| Business change | New products, markets, policies | Evaluate; potentially retrain |
| Scheduled | Every `[PERIOD]` | Retrain regardless |

### 13.8 Governance

| Aspect | Specification |
|--------|---------------|
| Model owner | `[NAME/TEAM]` |
| Review cadence | `[FREQUENCY]` |
| Documentation location | `[PATH]` |
| Approval required for | Threshold changes, retraining, feature changes |
| Escalation path | `[PROCESS]` |

**Key checks:** Thresholds use risk-by-horizon; monitoring covers key failure modes
**Notes for reviewers:** Confirm operational feasibility with engineering

---

## 14. Reviewer Checklist

### 14.1 Data & Definitions
- [ ] Event definition unambiguous and correct
- [ ] Time origin appropriate for business question
- [ ] Censoring definition valid
- [ ] Competing risks / recurrent events addressed
- [ ] No data leakage in features
- [ ] Cohort construction reproducible
- [ ] Survival data sanity checks pass

### 14.2 Methodology
- [ ] Model choice justified
- [ ] Predictive vs. inferential stance clear
- [ ] Baseline hazard / time effects handled appropriately
- [ ] Assumptions tested and satisfied (or violations addressed)
- [ ] Train/test split respects time ordering
- [ ] Validation design is nested and leak-free
- [ ] Regularization appropriate

### 14.3 Evaluation
- [ ] Discrimination adequate for use case (C-index, lift)
- [ ] Calibration acceptable at relevant horizons
- [ ] Performance stable across subgroups
- [ ] Performance stable over time (backtesting)
- [ ] Brier score / integrated metrics reported

### 14.4 Robustness
- [ ] Key findings robust to sensitivity analyses
- [ ] Uncertainty properly quantified (CIs, bootstrap)
- [ ] Limitations clearly stated

### 14.5 Fairness & Governance
- [ ] Subgroup fairness metrics computed
- [ ] Policy constraints documented and satisfied
- [ ] Fairness monitoring planned

### 14.6 Operationalization
- [ ] Score definition unambiguous (risk by horizon τ)
- [ ] Thresholds justified and capacity-aware
- [ ] Monitoring plan adequate
- [ ] Retraining triggers defined
- [ ] Governance documented

### 14.7 Known Limitations & Open Questions

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| `[LIMITATION_1]` | `[IMPACT]` | `[MITIGATION]` |
| ... | ... | ... |

| Open Question | Owner | Target Resolution |
|---------------|-------|-------------------|
| `[QUESTION_1]` | `[NAME]` | `[DATE]` |
| ... | ... | ... |

**Notes for reviewers:** Sign off with comments on each checklist item

---

## 15. Appendix

### A. Full Feature Dictionary
### B. SQL Queries
### C. Model Coefficients (Full Table)
### D. Additional Diagnostic Plots
### E. Code Module Documentation
### F. Change Log
### G. Glossary

| Term | Definition |
|------|------------|
| Hazard | Instantaneous risk of event at time t, given survival to t |
| Hazard ratio (HR) | Ratio of hazards; HR=2 means 2× the hazard |
| Censoring | Observation ends before event; event time unknown |
| Risk by horizon τ | P(event by time τ \| covariates) |
| C-index | Probability model correctly ranks two random individuals |
| Calibration | Agreement between predicted probabilities and observed rates |

---

# Adaptation Notes

## If Cox Proportional Hazards:
- Report hazard ratios (HR) with 95% CI
- Validate PH assumption via Schoenfeld residuals; address violations via stratification or time interactions
- C-index is primary discrimination metric
- Baseline hazard is unspecified (semi-parametric); can plot cumulative baseline hazard
- Time-varying covariates require extended Cox formulation
- Predicted risk at horizon τ: S(τ|X) = S₀(τ)^exp(βX)

## If Discrete-Time Logistic Hazard:
- Report odds ratios per interval (approximately HR if intervals narrow)
- Include interval indicators (time dummies) or smooth time function (spline)
- Validate goodness-of-fit per interval (Hosmer-Lemeshow within intervals)
- Can directly output probability of event in each interval: P(Y_t=1 | Y_{t-1}=0, X)
- Cumulative risk: 1 - ∏(1 - p_t)
- Panel/person-period data structure required; ensure features use data available at interval START

## If Competing Risks:
- Choose between cause-specific hazards vs. Fine-Gray (subdistribution)
- **Cause-specific:** "Hazard of event A among those still at risk of any event"
  - Standard Cox on event A, treating competing events as censoring
  - Coefficients have causal interpretation under assumptions
- **Fine-Gray:** "Effect on cumulative incidence of event A"
  - Accounts for competing events in risk set
  - Coefficients have population-level interpretation
- Report cumulative incidence functions (CIF), not Kaplan-Meier (which overestimates)
- Validate that competing events are properly defined (truly preclude primary event)
- For exec deck: Simplify to "some [ENTITIES] exit for other reasons; we account for this"
