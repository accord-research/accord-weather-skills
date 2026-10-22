---
name: seasonal-calibrate
description: "Calibrate one or several seasonal models' output against observations into tercile probabilities on the observation grid, with africas2s's ensemble regression (ereg), logistic (logit) or smoothed-regression methods; with --cv loyo it returns the leave-year-out cross-validated hindcast that seasonal-skill scores. Use after accord-fetch when the model is already on the observation grid."
license: MIT
compatibility: Requires Python 3.12 and uv. Offline once the inputs exist. First run on a machine installs the ACCORD libraries (about a minute).
allowed-tools: Bash(uv run ${CLAUDE_SKILL_DIR}/scripts/seasonal_calibrate.py *)
metadata:
  catalog-group: transforms
  version: "0.1.0"
---

# seasonal-calibrate

Model output statistics without a change of resolution: fits the chosen method per grid cell on the hindcast against the observations, then either issues one forecast or re-fits with each year held out to produce an honest hindcast.

## Usage

```bash
# a forecast for one issuance
uv run ${CLAUDE_SKILL_DIR}/scripts/seasonal_calibrate.py --hindcast HIND.zarr --obs OBS.zarr --forecast FC.zarr [--forecast-year YYYY] [--method ereg] -o OUT.zarr
# the cross-validated hindcast seasonal-skill scores
uv run ${CLAUDE_SKILL_DIR}/scripts/seasonal_calibrate.py --hindcast HIND.zarr --obs OBS.zarr --cv loyo [--cv-window 5] -o CV.zarr
# several models, averaged
uv run ${CLAUDE_SKILL_DIR}/scripts/seasonal_calibrate.py --hindcast A.zarr --hindcast B.zarr --obs OBS.zarr --forecast A_fc.zarr --forecast B_fc.zarr -o OUT.zarr
```

### Arguments
- `--hindcast` — model hindcast Zarr from `accord-fetch`, already on the observation grid. Repeat for several models. Required.
- `--obs` — seasonal observations Zarr from `accord-fetch`. Required.
- `--forecast` — the model's real-time forecast (one issuance); one per `--hindcast`, in the same order.
- `--method` — `ereg` (default), `logit`, or `smoothed_regression`.
- `--cv` — `loyo`: return the leave-year-out cross-validated hindcast instead of a forecast.
- `--cv-window` — years left out per fold (default 1; 5 matches PyCPT).
- `--output-type` — `tercile` (default) or `deterministic` (ereg and smoothed_regression).
- `--forecast-year` — the year the forecast is for; defaults to the forecast file's year.
- `--options` — JSON object of extra keyword arguments for the method, e.g. `{"clip_negative": true}` for rainfall.
- `--init-month`, `--target` — only needed when the hindcast lacks `init_month`/`target_season` attrs.
- `--output`, `-o` — output Zarr.

### Output
- Tercile: `prob_below`, `prob_normal`, `prob_above` (`units = "1"`); a forecast is one issuance (scalar `time` + `step`), a `--cv loyo` hindcast has one `init_time` per year. Attrs: `cross_validated` (true only with `--cv`), `method`, `tercile_method`, `cv_window`, `hindcast_years`.
- Deterministic: one variable named after the observations.

### Notes
- `--cv loyo` is the only way, besides `seasonal-outlook`, to produce a hindcast that `seasonal-skill` accepts.
- This skill does not regrid: fetch the model and the observations with the same `accord-fetch --grid-res` so they share a grid (NMME is 1°, CHIRPS 0.05°).

### Example
```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/seasonal_calibrate.py --hindcast ccsm4_mam_hindcast.zarr --obs chirps_mam.zarr --cv loyo --cv-window 5 -o ccsm4_mam_cv.zarr
```
