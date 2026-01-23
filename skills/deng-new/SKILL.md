---
name: deng-new
description: Use when scaffolding a new data science project for survival analysis, churn prediction, or time-to-event modeling. Use when user wants to create an isolated project with agents, hooks, skills, marimo notebooks, and proper test structure.
---

# Data Science Project Scaffolder

## Overview

Creates isolated, production-ready data science projects with local agents for each DS workflow phase, hooks for safety guardrails, skills for phase execution, and a Marimo notebook following the technical review template.

## Workflow Position

```
Claude Code (iterate/model) → Marimo (interactive analysis) → Quarto (present)
```

| Tool | Role | What Belongs Here |
|------|------|-------------------|
| **Claude Code** | Model development, iteration | Experimentation, debugging, src/ modules |
| **Marimo** | Interactive exploration | Widgets, reactive state, technical_review.py |
| **Quarto** | Narrative and publishing | Executive summaries, stakeholder reports |

**Build and iterate in CC first. Present interactively in Marimo. Publish via Quarto.**

## When to Use

- Starting a new survival analysis / churn prediction project
- Creating isolated environment for time-to-event modeling
- Setting up a data science workflow with proper structure
- User says "create a new DS project" or "scaffold a churn model"

## Invocation

```
/deng-new <project_slug>
```

Or if no argument provided, prompt for project slug.

## Interactive Questions

**You MUST ask these questions using AskUserQuestion before scaffolding:**

### Question 1: Project Slug
If not provided as argument, ask:
- Header: "Project name"
- Question: "What is the project slug (lowercase, hyphens, no spaces)?"

### Question 2: Business Track
- Header: "Track"
- Question: "Which business track is this project for?"
- Options:
  - `generic` (Recommended) - General purpose survival analysis
  - `customer_success` - Customer retention / churn focus
  - `sales` - Sales pipeline / booking execution
  - `finance` - Revenue forecasting / financial events

### Question 3: Target Event
- Header: "Event"
- Question: "What is the target event name (e.g., CHURN, CANCEL, DEFAULT)?"
- Default: "EVENT"

### Question 4: Time Origin
- Header: "Time origin"
- Question: "What is the time origin (e.g., ACTIVATION_DATE, CONTRACT_START)?"
- Default: "TIME_ORIGIN"

### Question 5: Modeling Approach
- Header: "Model type"
- Question: "Which modeling approach will you use?"
- Options:
  - `both` (Recommended) - Cox PH and discrete-time logistic
  - `cox_ph` - Cox Proportional Hazards only
  - `discrete_time` - Discrete-time logistic hazard only

### Question 6: Prediction Horizons
- Header: "Horizons"
- Question: "What prediction horizons (in days) do you need?"
- Default: "90, 180, 365"

### Question 7: Tech Stack
- Header: "Data stack"
- Question: "Which data manipulation library do you prefer?"
- Options:
  - `polars` (Recommended) - Better performance, modern API
  - `pandas` - Traditional, wider ecosystem

## Scaffolding Process

After collecting answers, create the following structure:

```
./<project_slug>/
├── .claude/
│   ├── settings.json
│   ├── agents/
│   │   ├── ds-data-explorer.md
│   │   ├── ds-feature-ideator.md
│   │   ├── ds-modeler.md
│   │   ├── ds-validator.md
│   │   └── ds-reviewer.md
│   ├── hooks/
│   │   ├── pre_bash_guard.sh
│   │   ├── post_format.sh
│   │   └── post_tests.sh
│   └── skills/
│       ├── deng-phase/SKILL.md
│       └── deng-review/SKILL.md
├── configs/
│   └── project.toml
├── docs/
│   ├── MARIMO_TECHNICAL_REVIEW_OUTLINE.md
│   ├── DECISION_CANVAS.md
│   └── ASSUMPTIONS.md
├── notebooks/
│   └── technical_review.py
├── reports/
│   └── executive_summary.qmd
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── data.py
│   ├── cohort.py
│   ├── features.py
│   ├── modeling.py
│   ├── eval.py
│   ├── plots.py
│   ├── utils.py
│   └── guardrails.py
├── artifacts/
│   ├── catalog/          # Data catalog snapshots (from /deng-catalog-refresh)
│   ├── tables/
│   ├── figures/
│   └── exports/
├── tests/
│   ├── conftest.py
│   ├── test_project_structure.py
│   ├── test_config_valid.py
│   └── test_notebook_smoke.py
├── README.md
├── pyproject.toml
├── .python-version
└── .gitignore
```

---

## File Templates

### configs/project.toml

```toml
[project]
slug = "{project_slug}"
track = "{track}"
event = "{event}"
time_origin = "{time_origin}"
created_at = "{iso_date}"

[model]
type = "{model_type}"  # cox_ph, discrete_time, or both
penalizer = 0.1

[horizons]
primary = {primary_horizon}
secondary = [{horizons_list}]

[cohort]
min_tenure_days = 180
exclude_admin_cancels = true

[features]
stack = "{stack}"  # polars or pandas
```

### .claude/settings.json

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [{"type": "command", "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/pre_bash_guard.sh"}]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {"type": "command", "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/post_format.sh"},
          {"type": "command", "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/post_tests.sh"}
        ]
      }
    ]
  }
}
```

### .claude/hooks/pre_bash_guard.sh

```bash
#!/bin/bash
# Pre-bash guard - blocks dangerous commands

input=$(cat)
command=$(echo "$input" | jq -r '.tool_input.command // empty')

# Blocked patterns
dangerous_patterns=(
    'rm -rf /'
    'rm -rf ~'
    'rm -rf $HOME'
    'DROP DATABASE'
    'DROP TABLE'
    'TRUNCATE'
    'chmod 777'
    'chmod -R 777'
    '> /dev/sda'
    'dd if='
    'mkfs.'
    ':(){:|:&};:'
)

for pattern in "${dangerous_patterns[@]}"; do
    if [[ "$command" == *"$pattern"* ]]; then
        echo "BLOCKED: Dangerous command pattern detected: $pattern"
        echo "This command has been blocked by pre_bash_guard.sh"
        exit 2
    fi
done

exit 0
```

### .claude/hooks/post_format.sh

```bash
#!/bin/bash
# Post-edit formatter - runs ruff on edited Python files

input=$(cat)
file_path=$(echo "$input" | jq -r '.tool_input.file_path // empty')

# Exit if no file path
if [ -z "$file_path" ]; then
    exit 0
fi

# Only process .py files
if [[ ! "$file_path" =~ \.py$ ]]; then
    exit 0
fi

# Check if file exists
if [ ! -f "$file_path" ]; then
    exit 0
fi

# Run ruff format if available
if command -v uvx &> /dev/null; then
    uvx ruff format "$file_path" 2>/dev/null || true
fi

exit 0
```

### .claude/hooks/post_tests.sh

```bash
#!/bin/bash
# Post-edit test runner - runs pytest after code changes

input=$(cat)
file_path=$(echo "$input" | jq -r '.tool_input.file_path // empty')

# Exit if no file path
if [ -z "$file_path" ]; then
    exit 0
fi

# Only process .py files in src/ or tests/
if [[ ! "$file_path" =~ \.py$ ]]; then
    exit 0
fi

if [[ ! "$file_path" =~ (src/|tests/) ]]; then
    exit 0
fi

# Find project root (where pyproject.toml is)
dir=$(dirname "$file_path")
for _ in {1..10}; do
    if [ -f "$dir/pyproject.toml" ]; then
        echo "Running tests..."
        cd "$dir" && uv run pytest tests/ -x --tb=short 2>&1 || echo "WARNING: Some tests failed"
        break
    fi
    parent=$(dirname "$dir")
    if [ "$parent" = "$dir" ]; then
        break
    fi
    dir="$parent"
done

exit 0
```

### .claude/agents/ds-data-explorer.md

```markdown
---
name: ds-data-explorer
description: Use for read-only exploration, metadata profiling, cohort sanity checks. Does NOT do feature engineering or modeling.
model: sonnet
color: blue
---

You are a Data Science Explorer focused on survival/time-to-event data exploration.

## Catalog-First Protocol

**CRITICAL: Always use the data catalog before running database queries.**

1. **NEVER scan databases directly** unless catalog is missing/stale
2. **Start with `/deng-find-data`** to identify candidate tables
3. **Review `artifacts/catalog/DATA_CATALOG_SUMMARY.md`** for join paths
4. **Propose a shortlist** of tables before requesting deeper profiling
5. **Only request `/deng-catalog-refresh`** if catalog is >7 days old or missing

### Catalog Search Examples

```bash
# Find cancellation-related tables
uv run --with polars python ~/.deng-toolkit/scripts/catalog_query.py "order cancel status"

# Find customer entity tables
uv run --with polars python ~/.deng-toolkit/scripts/catalog_query.py "company account customer"

# Get table details
uv run --with polars python ~/.deng-toolkit/scripts/catalog_query.py --table Orders.OrderItem

# Find join paths
uv run --with polars python ~/.deng-toolkit/scripts/catalog_query.py --joins OrderItem
```

## Your Role
- Read-only exploration and profiling
- Metadata analysis and data quality assessment
- Cohort sanity checks
- Kaplan-Meier curves and censoring pattern analysis
- Cross-database join validation
- NO feature engineering or modeling

## Tools You May Use
- Read, Glob, Grep for file exploration
- Bash for catalog queries (always first!)
- Bash for read-only SQL queries (SELECT only, after catalog search)
- NO Edit or Write tools

## Key Tasks
1. **Search catalog first** for relevant tables
2. Profile raw data sources (after identifying via catalog)
3. Validate survival data construction (event, duration, censoring)
4. Generate KM curves for directional validation
5. Check censoring patterns
6. Validate cross-database joins
7. Document data quality issues

## Output Format
Always produce:
- Catalog search results (which tables were identified)
- Summary statistics tables
- Data quality findings
- Sanity check pass/fail status
- Recommendations for next steps
```

### .claude/agents/ds-feature-ideator.md

```markdown
---
name: ds-feature-ideator
description: Use for feature idea generation with leakage prevention. Proposes features with time-window awareness.
model: sonnet
color: green
---

You are a Feature Engineering Ideator for survival analysis.

## Your Role
- Generate feature ideas with time-window awareness
- Flag potential leakage sources
- Document lookback periods and anchor points
- Reference guardrails.py constraints
- NO actual feature implementation

## Key Principles
1. **Time-Zero Awareness**: Features MUST use only information available at or before time origin
2. **Lookback Windows**: Define explicit windows (e.g., "30 days before activation")
3. **Leakage Detection**: Flag any feature that could encode future information
4. **Domain Grounding**: Ground features in business logic

## Output Format
For each feature idea:
| Feature | Definition | Window | Leakage Risk | Rationale |
|---------|------------|--------|--------------|-----------|

## Leakage Red Flags
- Features using data after time origin
- Features encoding the outcome variable
- Features with future-looking aggregations
- Target leakage through related entities
```

### .claude/agents/ds-modeler.md

```markdown
---
name: ds-modeler
description: Use for fitting survival models (Cox PH, discrete-time). Handles temporal splits, PH assumptions, and metrics.
model: opus
color: purple
---

You are a Survival Modeling Specialist.

## Your Role
- Fit Cox PH and discrete-time logistic models
- Validate temporal train/test splits
- Test proportional hazards assumptions
- Compute C-index, calibration, and lift metrics
- Generate horizon-specific risk predictions

## Modeling Checklist
1. **Temporal Split**: Train BEFORE test chronologically
2. **PH Assumption**: Test via Schoenfeld residuals
3. **Regularization**: Use penalized models (L2 default)
4. **Stratification**: Consider if baseline hazards differ by segment
5. **Horizons**: Compute S(t) at specified horizons

## Key Metrics
- C-index (discrimination)
- Calibration slope and intercept
- Time-dependent AUC
- Brier score at horizons
- Lift in top deciles

## Output Format
- Model specification summary
- Coefficient table with HRs and CIs
- Diagnostic plots
- Performance metrics table
```

### .claude/agents/ds-validator.md

```markdown
---
name: ds-validator
description: Use for model evaluation and robustness checks. Lift analysis, calibration, subgroup parity, sensitivity analyses.
model: sonnet
color: orange
---

You are a Model Validation Specialist.

## Your Role
- Comprehensive model evaluation
- Lift and capture curve analysis
- Calibration at multiple horizons
- Subgroup performance parity checks
- Sensitivity analyses
- Bootstrap uncertainty quantification

## Validation Checklist
1. **Discrimination**: C-index, time-dependent AUC
2. **Calibration**: Predicted vs observed by decile
3. **Lift Analysis**: Top decile capture rate
4. **Subgroups**: Performance across key segments
5. **Temporal Stability**: Backtesting over multiple windows
6. **Robustness**: Sensitivity to assumptions

## Key Questions
- Does the model rank well (C-index > 0.65)?
- Is calibration acceptable (slope ~ 1.0)?
- Does top decile capture significant events?
- Is performance stable across subgroups?
- Are findings robust to sensitivity analyses?

## Output Format
- Evaluation metrics table
- Lift/capture curves
- Calibration plots by horizon
- Subgroup performance table
- Sensitivity analysis summary
```

### .claude/agents/deng-reviewer.md

```markdown
---
name: deng-reviewer
description: Use for peer review against the technical review checklist. Produces REVIEW_NOTES.md with findings.
model: opus
color: red
---

You are a Peer Reviewer for survival analysis models.

## Your Role
- Review against MARIMO_TECHNICAL_REVIEW_OUTLINE.md Section 14 checklist
- Check assumptions, leakage, diagnostics
- Produce REVIEW_NOTES.md with findings
- Flag blocking issues vs suggestions

## Review Checklist (Section 14)

### Data & Definitions
- [ ] Event definition unambiguous and correct
- [ ] Time origin appropriate
- [ ] Censoring definition valid
- [ ] No data leakage in features

### Methodology
- [ ] Model choice justified
- [ ] Predictive vs inferential stance clear
- [ ] Assumptions tested and satisfied
- [ ] Train/test split respects time ordering

### Evaluation
- [ ] Discrimination adequate (C-index, lift)
- [ ] Calibration acceptable at horizons
- [ ] Performance stable across subgroups
- [ ] Backtesting performed

### Robustness
- [ ] Sensitivity analyses performed
- [ ] Uncertainty quantified
- [ ] Limitations stated

### Operationalization
- [ ] Score definition unambiguous
- [ ] Thresholds justified
- [ ] Monitoring plan adequate

## Output Format
Write findings to docs/REVIEW_NOTES.md:
- PASS / NEEDS_ATTENTION / BLOCKING for each item
- Specific findings with file:line references
- Recommendations for remediation
```

### .claude/skills/deng-phase/SKILL.md

```markdown
---
name: deng-phase
description: Use when executing a named DS workflow phase. Coordinates agents and tracks progress.
---

# DS Phase Executor

## Usage

```
/deng-phase <phase_name>
```

## Phases

| Phase | Agent | Description |
|-------|-------|-------------|
| `cohort` | ds-data-explorer | Cohort construction + sanity checks |
| `features` | ds-feature-ideator → ds-data-explorer | Feature engineering + leakage checks |
| `modeling` | ds-modeler | Model fitting + diagnostics |
| `evaluation` | ds-validator | Metrics + calibration + lift |
| `robustness` | ds-validator | Sensitivity + bootstrap |
| `interpretability` | ds-modeler | Forest plots + risk profiles |
| `operationalization` | ds-modeler | Thresholds + monitoring |
| `review` | ds-reviewer | Full peer review |

## Workflow

1. Load configs/project.toml for context
2. Dispatch appropriate agent(s)
3. Update relevant notebook section
4. Summarize phase completion
5. Suggest next phase

## Phase Details

### cohort
- Build inclusion/exclusion logic
- Generate cohort flow diagram
- Run survival data sanity checks (Section 5)
- Update notebook Sections 3, 5

### features
- Generate feature ideas
- Validate time windows
- Check for leakage
- Update notebook Section 6

### modeling
- Fit specified model type(s)
- Test assumptions
- Generate coefficients
- Update notebook Sections 7, 8

### evaluation
- Compute all metrics
- Generate lift curves
- Calibration at horizons
- Update notebook Section 9

### robustness
- Bootstrap CIs
- Sensitivity analyses
- Feature ablation
- Update notebook Section 10

### interpretability
- Forest plot
- Risk profiles
- Survival curves by factors
- Update notebook Section 11

### operationalization
- Decision curve analysis
- Threshold selection
- Monitoring plan
- Update notebook Section 13
```

### .claude/skills/deng-review/SKILL.md

```markdown
---
name: deng-review
description: Use when running formal peer review against the technical checklist.
---

# DS Review Executor

## Usage

```
/deng-review
```

## Process

1. Invoke ds-reviewer agent
2. Walk through Section 14 checklist
3. Write findings to docs/REVIEW_NOTES.md
4. Summarize pass/fail status

## Review Sections

1. **Data & Definitions** - Event, time origin, censoring, leakage
2. **Methodology** - Model choice, assumptions, validation design
3. **Evaluation** - Discrimination, calibration, subgroups, backtesting
4. **Robustness** - Sensitivity, uncertainty, limitations
5. **Fairness & Governance** - Subgroup parity, policy compliance
6. **Operationalization** - Score definition, thresholds, monitoring

## Output

### docs/REVIEW_NOTES.md

```markdown
# Peer Review Notes

**Reviewer:** Claude
**Date:** {date}
**Status:** PASS / NEEDS_ATTENTION / BLOCKING

## Summary
{overall_assessment}

## Checklist Results

### Data & Definitions
| Item | Status | Finding |
|------|--------|---------|
| Event definition | PASS/FAIL | {finding} |
...

## Blocking Issues
{list_or_none}

## Recommendations
{prioritized_list}
```
```

### src/__init__.py

```python
"""
{project_slug}: {event} prediction using survival analysis.

Track: {track}
Created: {iso_date}
"""

__version__ = "0.1.0"
```

### src/config.py

```python
"""Configuration loading and validation."""

from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib


def load_config(config_path: Path | str | None = None) -> dict:
    """Load project configuration from TOML file."""
    if config_path is None:
        config_path = Path(__file__).parent.parent / "configs" / "project.toml"

    config_path = Path(config_path)

    with open(config_path, "rb") as f:
        return tomllib.load(f)


def get_horizons(config: dict) -> list[int]:
    """Get prediction horizons from config."""
    horizons = config.get("horizons", {})
    primary = horizons.get("primary", 365)
    secondary = horizons.get("secondary", [90, 180, 365])
    return sorted(set([primary] + secondary))


def get_model_type(config: dict) -> str:
    """Get model type from config."""
    return config.get("model", {}).get("type", "both")


def get_data_stack(config: dict) -> str:
    """Get data stack preference from config."""
    return config.get("features", {}).get("stack", "polars")
```

### src/data.py

```python
"""Data loading and preprocessing utilities."""

from pathlib import Path

from .config import get_data_stack, load_config


def load_data(path: Path | str, config: dict | None = None):
    """Load data using configured stack (polars or pandas)."""
    if config is None:
        config = load_config()

    stack = get_data_stack(config)
    path = Path(path)

    if stack == "polars":
        import polars as pl

        if path.suffix == ".parquet":
            return pl.read_parquet(path)
        elif path.suffix == ".csv":
            return pl.read_csv(path)
        else:
            raise ValueError(f"Unsupported file type: {path.suffix}")
    else:
        import pandas as pd

        if path.suffix == ".parquet":
            return pd.read_parquet(path)
        elif path.suffix == ".csv":
            return pd.read_csv(path)
        else:
            raise ValueError(f"Unsupported file type: {path.suffix}")
```

### src/cohort.py

```python
"""Cohort construction utilities."""

from .config import load_config


def build_cohort(df, config: dict | None = None):
    """
    Build analysis cohort with inclusion/exclusion criteria.

    Returns cohort dataframe and flow statistics.
    """
    if config is None:
        config = load_config()

    min_tenure = config.get("cohort", {}).get("min_tenure_days", 180)
    exclude_admin = config.get("cohort", {}).get("exclude_admin_cancels", True)

    flow = {"initial": len(df)}

    # TODO: Implement inclusion/exclusion logic
    # This is a placeholder - implement based on your data

    return df, flow


def compute_survival_fields(df, event_col: str, time_col: str):
    """
    Compute event indicator and duration fields.

    Returns dataframe with 'event' (0/1) and 'duration' columns.
    """
    # TODO: Implement based on your data structure
    pass
```

### src/features.py

```python
"""Feature engineering utilities with leakage prevention."""

from datetime import datetime
from typing import Callable

from .config import load_config
from .guardrails import validate_feature_window


def engineer_features(df, time_origin_col: str, config: dict | None = None):
    """
    Engineer features with time-window awareness.

    All features use only information available at or before time_origin.
    """
    if config is None:
        config = load_config()

    # TODO: Implement feature engineering
    # Each feature should be validated against time_origin

    return df


def create_feature(
    df,
    name: str,
    calculation: Callable,
    lookback_days: int,
    time_origin_col: str,
) -> None:
    """
    Create a single feature with explicit lookback window.

    Validates that feature does not use future information.
    """
    # Validate window
    validate_feature_window(
        df=df,
        feature_name=name,
        time_origin_col=time_origin_col,
        lookback_days=lookback_days,
    )

    # TODO: Apply calculation
    pass
```

### src/modeling.py

```python
"""Survival modeling utilities."""

from .config import get_horizons, get_model_type, load_config


def fit_cox_ph(df, duration_col: str, event_col: str, feature_cols: list[str], config: dict | None = None):
    """
    Fit Cox Proportional Hazards model.

    Returns fitted model and diagnostics.
    """
    if config is None:
        config = load_config()

    from lifelines import CoxPHFitter

    penalizer = config.get("model", {}).get("penalizer", 0.1)

    cph = CoxPHFitter(penalizer=penalizer)
    cph.fit(
        df[[duration_col, event_col] + feature_cols],
        duration_col=duration_col,
        event_col=event_col,
    )

    return cph


def fit_discrete_time(df, interval_col: str, event_col: str, feature_cols: list[str], config: dict | None = None):
    """
    Fit discrete-time logistic hazard model.

    Returns fitted model and diagnostics.
    """
    if config is None:
        config = load_config()

    # TODO: Implement discrete-time model
    pass


def predict_risk_at_horizon(model, df, horizon: int):
    """
    Predict cumulative risk at specified horizon.

    Returns P(event by horizon | covariates).
    """
    # For Cox: S(t|X) = S_0(t)^exp(beta*X)
    # Risk = 1 - S(t|X)
    survival_func = model.predict_survival_function(df)

    # Find closest time point to horizon
    times = survival_func.index
    closest_idx = (times - horizon).abs().argmin()

    return 1 - survival_func.iloc[closest_idx]
```

### src/eval.py

```python
"""Model evaluation utilities."""

from .config import get_horizons, load_config


def compute_c_index(model, df, duration_col: str, event_col: str):
    """Compute Harrell's concordance index."""
    return model.concordance_index_


def compute_calibration(predicted_risks, actual_events, n_bins: int = 10):
    """
    Compute calibration metrics.

    Returns calibration slope, intercept, and binned statistics.
    """
    import numpy as np

    # Bin by predicted risk
    bins = np.percentile(predicted_risks, np.linspace(0, 100, n_bins + 1))
    bin_indices = np.digitize(predicted_risks, bins[1:-1])

    calibration_data = []
    for i in range(n_bins):
        mask = bin_indices == i
        if mask.sum() > 0:
            calibration_data.append({
                "bin": i + 1,
                "n": mask.sum(),
                "mean_predicted": predicted_risks[mask].mean(),
                "observed_rate": actual_events[mask].mean(),
            })

    return calibration_data


def compute_lift(predicted_risks, actual_events, n_deciles: int = 10):
    """
    Compute lift statistics by risk decile.

    Returns lift table with capture rates.
    """
    import numpy as np

    # Sort by predicted risk descending
    order = np.argsort(-predicted_risks)
    sorted_events = actual_events[order]

    total_events = sorted_events.sum()
    n = len(predicted_risks)
    decile_size = n // n_deciles

    lift_data = []
    cumulative_events = 0

    for i in range(n_deciles):
        start = i * decile_size
        end = (i + 1) * decile_size if i < n_deciles - 1 else n

        decile_events = sorted_events[start:end].sum()
        cumulative_events += decile_events

        lift_data.append({
            "decile": i + 1,
            "n": end - start,
            "events": decile_events,
            "event_rate": decile_events / (end - start),
            "cumulative_capture": cumulative_events / total_events,
            "lift": (decile_events / (end - start)) / (total_events / n),
        })

    return lift_data
```

### src/plots.py

```python
"""Visualization utilities."""


def plot_km_curve(durations, events, ax=None, label: str = "Overall", ci: bool = True):
    """Plot Kaplan-Meier survival curve."""
    from lifelines import KaplanMeierFitter

    kmf = KaplanMeierFitter()
    kmf.fit(durations, events, label=label)

    return kmf.plot_survival_function(ax=ax, ci_show=ci)


def plot_forest(model, ax=None, sort_by: str = "hr"):
    """Plot forest plot of hazard ratios."""
    import matplotlib.pyplot as plt

    if ax is None:
        fig, ax = plt.subplots(figsize=(10, max(6, len(model.params_) * 0.4)))

    summary = model.summary

    if sort_by == "hr":
        summary = summary.sort_values("exp(coef)")

    # TODO: Implement forest plot

    return ax


def plot_calibration(calibration_data, horizon: int, ax=None):
    """Plot calibration curve."""
    import matplotlib.pyplot as plt

    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 8))

    predicted = [d["mean_predicted"] for d in calibration_data]
    observed = [d["observed_rate"] for d in calibration_data]

    ax.scatter(predicted, observed, s=100, alpha=0.7)
    ax.plot([0, 1], [0, 1], "k--", label="Perfect calibration")
    ax.set_xlabel(f"Mean Predicted Risk at {horizon} days")
    ax.set_ylabel("Observed Event Rate")
    ax.set_title(f"Calibration Plot (Horizon = {horizon} days)")
    ax.legend()

    return ax


def plot_lift_curve(lift_data, ax=None):
    """Plot cumulative lift/capture curve."""
    import matplotlib.pyplot as plt

    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 6))

    deciles = [d["decile"] for d in lift_data]
    capture = [d["cumulative_capture"] for d in lift_data]

    ax.plot(deciles, capture, "b-o", label="Model", linewidth=2)
    ax.plot([1, 10], [0.1, 1.0], "k--", label="Random")
    ax.set_xlabel("Risk Decile (1 = Highest Risk)")
    ax.set_ylabel("Cumulative % of Events Captured")
    ax.set_title("Capture Curve")
    ax.legend()
    ax.set_xticks(range(1, 11))

    return ax
```

### src/utils.py

```python
"""General utilities."""

from datetime import datetime
from pathlib import Path


def get_project_root() -> Path:
    """Get project root directory."""
    return Path(__file__).parent.parent


def get_timestamp() -> str:
    """Get ISO format timestamp."""
    return datetime.now().isoformat()


def ensure_dir(path: Path | str) -> Path:
    """Ensure directory exists."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path
```

### src/guardrails.py

```python
"""Data quality and leakage prevention guardrails."""

from datetime import datetime


class LeakageError(Exception):
    """Raised when potential data leakage is detected."""
    pass


class DataQualityError(Exception):
    """Raised when data quality checks fail."""
    pass


def validate_feature_window(
    df,
    feature_name: str,
    time_origin_col: str,
    lookback_days: int,
    feature_timestamp_col: str | None = None,
) -> None:
    """
    Validate that feature does not use future information.

    Raises LeakageError if potential leakage detected.
    """
    if feature_timestamp_col is not None:
        # Check that all feature timestamps are before time_origin
        # TODO: Implement based on your data stack
        pass


def validate_no_target_leakage(df, target_col: str, feature_cols: list[str]) -> None:
    """
    Check for features that directly encode the target.

    Raises LeakageError if high correlation detected.
    """
    # TODO: Implement correlation checks
    pass


def validate_temporal_split(train_df, test_df, time_col: str) -> None:
    """
    Validate that test data is strictly after training data.

    Raises LeakageError if temporal ordering violated.
    """
    # TODO: Implement temporal validation
    pass


def validate_survival_data(
    df,
    duration_col: str,
    event_col: str,
    min_duration: float = 0,
) -> dict:
    """
    Run survival data sanity checks.

    Returns dict of check results.
    """
    checks = {}

    # Check for negative durations
    negative_durations = (df[duration_col] < 0).sum()
    checks["no_negative_durations"] = negative_durations == 0

    # Check event indicator is binary
    unique_events = df[event_col].unique()
    checks["binary_event"] = set(unique_events).issubset({0, 1})

    # Check minimum duration
    below_min = (df[duration_col] < min_duration).sum()
    checks["above_min_duration"] = below_min == 0

    return checks
```

### tests/conftest.py

```python
"""Pytest configuration and fixtures."""

import sys
from pathlib import Path

import pytest

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))


@pytest.fixture
def project_root():
    """Return project root path."""
    return Path(__file__).parent.parent


@pytest.fixture
def config(project_root):
    """Load project configuration."""
    from config import load_config
    return load_config(project_root / "configs" / "project.toml")
```

### tests/test_project_structure.py

```python
"""Test project structure is complete."""

from pathlib import Path


def test_required_directories_exist(project_root):
    """Verify all required directories exist."""
    required_dirs = [
        "src",
        "configs",
        "docs",
        "notebooks",
        "reports",
        "tests",
        "artifacts",
        "artifacts/catalog",
        "artifacts/tables",
        "artifacts/figures",
        "artifacts/exports",
        ".claude",
        ".claude/agents",
        ".claude/hooks",
        ".claude/skills",
    ]

    for dir_name in required_dirs:
        dir_path = project_root / dir_name
        assert dir_path.is_dir(), f"Missing directory: {dir_name}"


def test_required_files_exist(project_root):
    """Verify all required files exist."""
    required_files = [
        "configs/project.toml",
        "README.md",
        "pyproject.toml",
        ".gitignore",
        "src/__init__.py",
        "src/config.py",
        "notebooks/technical_review.py",
        "reports/executive_summary.qmd",
        "docs/MARIMO_TECHNICAL_REVIEW_OUTLINE.md",
        ".claude/settings.json",
    ]

    for file_name in required_files:
        file_path = project_root / file_name
        assert file_path.is_file(), f"Missing file: {file_name}"
```

### tests/test_config_valid.py

```python
"""Test configuration validity."""

from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib


def test_config_parses(project_root):
    """Verify project.toml can be parsed."""
    config_path = project_root / "configs" / "project.toml"

    with open(config_path, "rb") as f:
        config = tomllib.load(f)

    assert isinstance(config, dict)


def test_required_keys_exist(project_root):
    """Verify required configuration keys exist."""
    config_path = project_root / "configs" / "project.toml"

    with open(config_path, "rb") as f:
        config = tomllib.load(f)

    # Project section
    assert "project" in config
    assert "slug" in config["project"]

    # Model section
    assert "model" in config
    assert "type" in config["model"]

    # Horizons section
    assert "horizons" in config
    assert "primary" in config["horizons"]
```

### tests/test_notebook_smoke.py

```python
"""Smoke tests for Marimo notebook."""

import subprocess
import sys
from pathlib import Path


def test_notebook_compiles(project_root):
    """Verify notebook has no syntax errors."""
    notebook_path = project_root / "notebooks" / "technical_review.py"

    # Try to compile the Python file
    with open(notebook_path, "r") as f:
        source = f.read()

    compile(source, notebook_path, "exec")


def test_marimo_check_passes(project_root):
    """Verify marimo check passes on notebook."""
    notebook_path = project_root / "notebooks" / "technical_review.py"

    result = subprocess.run(
        ["uvx", "marimo", "check", str(notebook_path)],
        capture_output=True,
        text=True,
    )

    # marimo check returns 0 if no issues
    assert result.returncode == 0, f"marimo check failed: {result.stderr}"
```

### pyproject.toml

```toml
[project]
name = "{project_slug}"
version = "0.1.0"
description = "{event} prediction using survival analysis"
requires-python = ">=3.11"
dependencies = [
    "polars>=0.20.0",
    "lifelines>=0.28.0",
    "matplotlib>=3.8.0",
    "altair>=5.0.0",
    "marimo>=0.7.0",
    "great-tables>=0.3.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "ruff>=0.3.0",
]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

### .python-version

```
3.11
```

### .gitignore

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
.Python
*.so

# Virtual environments
.venv/
venv/
ENV/

# IDE
.idea/
.vscode/
*.swp
*.swo

# Project artifacts
artifacts/tables/*
artifacts/figures/*
artifacts/exports/*
!artifacts/*/.gitkeep

# Catalog - keep summary, ignore large data files (covered by *.parquet below)
!artifacts/catalog/DATA_CATALOG_SUMMARY.md

# Data files (too large for git)
*.parquet
*.csv
*.xlsx

# Environment
.env
.env.local

# OS
.DS_Store
Thumbs.db

# Marimo
.marimo/

# Pytest
.pytest_cache/
.coverage
htmlcov/
```

### README.md

```markdown
# {project_slug}

{event} prediction using survival analysis.

## Overview

| Attribute | Value |
|-----------|-------|
| Track | {track} |
| Event | {event} |
| Time Origin | {time_origin} |
| Model Type | {model_type} |
| Data Stack | {stack} |

## Quick Start

```bash
# Install dependencies
uv sync

# Run notebook
uv run marimo edit notebooks/technical_review.py

# Run tests
uv run pytest
```

## Project Structure

```
.
├── configs/          # Project configuration
├── docs/             # Documentation and templates
├── notebooks/        # Marimo notebooks (interactive analysis)
├── reports/          # Quarto documents (stakeholder publishing)
├── src/              # Source code modules
├── tests/            # Test suite
└── artifacts/        # Generated outputs (tables, figures, exports)
```

## Tool Workflow

```
Claude Code (iterate/model) → Marimo (interactive analysis) → Quarto (present)
```

| Tool | Role | Location |
|------|------|----------|
| **Claude Code** | Model development, iteration | `src/` modules |
| **Marimo** | Interactive exploration, technical review | `notebooks/` |
| **Quarto** | Stakeholder reports, publishing | `reports/` |

**Build in CC. Explore in Marimo. Publish via Quarto.**

## DS Workflow

Use the local skills to execute workflow phases:

```
/deng-phase cohort       # Build cohort + sanity checks
/deng-phase features     # Feature engineering + leakage checks
/deng-phase modeling     # Fit models + diagnostics
/deng-phase evaluation   # Metrics + calibration
/deng-phase robustness   # Sensitivity analyses
/deng-review             # Formal peer review
```

## Agents

| Agent | Purpose |
|-------|---------|
| ds-data-explorer | Read-only exploration, profiling |
| ds-feature-ideator | Feature ideas with leakage prevention |
| ds-modeler | Model fitting and diagnostics |
| ds-validator | Evaluation and robustness |
| ds-reviewer | Peer review against checklist |

## References

- See `docs/MARIMO_TECHNICAL_REVIEW_OUTLINE.md` for the technical review template
- See `docs/ASSUMPTIONS.md` for documented assumptions
- See `docs/DECISION_CANVAS.md` for key decisions
```

### docs/DECISION_CANVAS.md

```markdown
# Decision Canvas

Document key decisions made during model development.

## Template

| Decision | Options Considered | Choice | Rationale | Date |
|----------|-------------------|--------|-----------|------|
| Example | A, B, C | B | Reason for B | 2024-01-01 |

## Decisions

| Decision | Options Considered | Choice | Rationale | Date |
|----------|-------------------|--------|-----------|------|
| | | | | |
```

### docs/ASSUMPTIONS.md

```markdown
# Assumptions Log

Document assumptions made during model development.

## Template

| Assumption | Category | Evidence | Risk if Violated | Validation Plan |
|------------|----------|----------|------------------|-----------------|
| Example | Data | Observed pattern | Medium - would bias estimates | Check in backtest |

## Assumptions

| Assumption | Category | Evidence | Risk if Violated | Validation Plan |
|------------|----------|----------|------------------|-----------------|
| | | | | |
```

### reports/executive_summary.qmd

```markdown
---
title: "{event} Prediction Model: Executive Summary"
author: "Data Science Team"
date: today
format:
  html:
    toc: true
    code-fold: true
  pdf:
    documentclass: article
jupyter: python3
execute:
  echo: false
  warning: false
  freeze: auto
---

## Overview

**Model:** {event} prediction using survival analysis
**Track:** {track}
**Status:** Draft

## Key Findings

```{{python}}
#| label: tbl-key-metrics
#| tbl-cap: "Model Performance Summary"

import polars as pl
from great_tables import GT

# Load pre-computed results from artifacts
metrics = pl.read_parquet("../artifacts/tables/model_metrics.parquet")
GT(metrics).tab_header(title="Performance Metrics")
```

::: {.callout-note}
Results are computed in `notebooks/technical_review.py` and exported to `artifacts/`.
:::

## Risk Stratification

```{{python}}
#| label: fig-lift
#| fig-cap: "Cumulative capture curve by risk decile"

import altair as alt
import polars as pl

# Load pre-computed lift data
lift = pl.read_parquet("../artifacts/tables/lift_analysis.parquet")
alt.Chart(lift).mark_line(point=True).encode(
    x="decile:O",
    y="cumulative_capture:Q"
).properties(width=600, height=400)
```

## Recommendations

TODO: Add recommendations after model finalization.

## Limitations

TODO: Document key limitations.

---

*See `notebooks/technical_review.py` for full technical documentation.*
```

### notebooks/technical_review.py (Marimo notebook skeleton)

```python
import marimo

__generated_with = "0.7.0"
app = marimo.App(width="full")


@app.cell
def _():
    import marimo as mo
    import polars as pl
    import altair as alt
    from pathlib import Path
    import sys

    # Add src to path
    sys.path.insert(0, str(Path.cwd().parent / "src"))

    return Path, alt, mo, pl, sys


@app.cell
def _(mo):
    mo.md(
        """
        # {event} Hazard Model: Technical Documentation & Peer Review

        **Version:** v0.1.0
        **Track:** {track}
        **Status:** Draft

        ---

        See `docs/MARIMO_TECHNICAL_REVIEW_OUTLINE.md` for the full template.
        """
    )
    return


@app.cell
def _(Path):
    # Load project configuration
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib

    config_path = Path.cwd().parent / "configs" / "project.toml"
    with open(config_path, "rb") as f:
        config = tomllib.load(f)

    config
    return config, config_path, tomllib


@app.cell
def _(config, mo):
    mo.md(
        f"""
        ## 0. Front Matter

        | Item | Content |
        |------|---------|
        | Project | {config['project']['slug']} |
        | Event | {config['project']['event']} |
        | Time Origin | {config['project']['time_origin']} |
        | Model Type | {config['model']['type']} |
        | Horizons | {config['horizons']['secondary']} |
        """
    )
    return


@app.cell
def _(mo):
    mo.md(
        """
        ## 0.5 Model Card (Governance Summary)

        TODO: Complete model card after model is finalized.
        """
    )
    return


@app.cell
def _(mo):
    mo.md(
        """
        ## 1. Executive Summary

        TODO: Complete after analysis is done.

        ### 1.1 Problem Statement

        ### 1.2 Modeling Stance

        ### 1.3 Model Summary Table

        ### 1.4 Key Findings

        ### 1.5 Limitations Summary

        ### 1.6 Recommendation
        """
    )
    return


@app.cell
def _(mo):
    mo.md(
        """
        ## 2. Problem Definition & Target Specification

        TODO: Define event, time origin, censoring.
        """
    )
    return


@app.cell
def _(mo):
    mo.md(
        """
        ## 3. Cohort Construction

        TODO: Build cohort with inclusion/exclusion criteria.
        """
    )
    return


@app.cell
def _(mo):
    mo.md(
        """
        ## 4. Data Sources & Definitions

        TODO: Document data sources and lineage.
        """
    )
    return


@app.cell
def _(mo):
    mo.md(
        """
        ## 5. Survival Data Sanity Checks

        TODO: Run sanity checks before modeling.
        """
    )
    return


@app.cell
def _(mo):
    mo.md(
        """
        ## 6. Feature Engineering

        TODO: Engineer features with leakage prevention.
        """
    )
    return


@app.cell
def _(mo):
    mo.md(
        """
        ## 7. Modeling Approach

        TODO: Document model specification.
        """
    )
    return


@app.cell
def _(mo):
    mo.md(
        """
        ## 8. Assumptions & Diagnostics

        TODO: Test and validate assumptions.
        """
    )
    return


@app.cell
def _(mo):
    mo.md(
        """
        ## 9. Model Evaluation

        TODO: Compute metrics and generate plots.
        """
    )
    return


@app.cell
def _(mo):
    mo.md(
        """
        ## 10. Uncertainty & Robustness

        TODO: Run sensitivity analyses.
        """
    )
    return


@app.cell
def _(mo):
    mo.md(
        """
        ## 11. Interpretability

        TODO: Generate forest plot and risk profiles.
        """
    )
    return


@app.cell
def _(mo):
    mo.md(
        """
        ## 12. Fairness & Policy Compliance

        TODO: Check subgroup performance parity.
        """
    )
    return


@app.cell
def _(mo):
    mo.md(
        """
        ## 13. Operationalization

        TODO: Define thresholds and monitoring plan.
        """
    )
    return


@app.cell
def _(mo):
    mo.md(
        """
        ## 14. Reviewer Checklist

        TODO: Complete peer review.
        """
    )
    return


@app.cell
def _(mo):
    mo.md(
        """
        ## 15. Appendix

        TODO: Add supplementary materials.
        """
    )
    return


if __name__ == "__main__":
    app.run()
```

---

## Scaffolding Execution

After collecting all answers via AskUserQuestion, execute the following:

1. **Create directory structure** using Bash mkdir commands
2. **Write all files** using Write tool with templates above
3. **Copy MARIMO_TECHNICAL_REVIEW_OUTLINE.md** from this skill's directory to docs/
4. **Make hooks executable** with chmod +x
5. **Initialize git** (optional, ask user)
6. **Run verification** - pytest and marimo check

## Verification Checklist

After scaffolding:

- [ ] All directories created
- [ ] All files written
- [ ] Hooks are executable
- [ ] `uv run pytest` passes
- [ ] `uvx marimo check notebooks/technical_review.py` passes
- [ ] Config loads without error

## Post-Scaffold Message

```
Project scaffolded successfully at ./{project_slug}/

Next steps:
1. cd {project_slug}
2. uv sync
3. Review configs/project.toml
4. Start with: /deng-phase cohort

Available phases:
- cohort, features, modeling, evaluation, robustness, interpretability, operationalization

Run /deng-review when ready for peer review.
```
