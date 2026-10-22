---
name: seasonal-calibrate
description: "Calibrate one or several seasonal models' output against observations into tercile probabilities on the observation grid, with africas2s's ensemble regression (ereg), logistic (logit), or smoothed-regression methods. With --cv loyo it returns the leave-year-out cross-validated hindcast that seasonal-skill scores. Use after accord-fetch when the model is already on the observation grid."
license: MIT
compatibility: Requires Python 3.12 and uv. Works offline once the inputs exist. The first run on a machine installs the ACCORD libraries (about a minute).
allowed-tools: Bash(uv run ${CLAUDE_SKILL_DIR}/scripts/seasonal_calibrate.py *)
metadata:
  catalog-group: transforms
  version: "0.1.0"
---

# seasonal-calibrate

Applies model output statistics without changing resolution: fits the chosen method per grid cell on the hindcast against the observations, then either issues one forecast or refits with each year held out to produce an honest hindcast.

## Usage

```bash
# A forecast for one issuance.
uv run ${CLAUDE_SKILL_DIR}/scripts/seasonal_calibrate.py --hindcast HIND.zarr --obs OBS.zarr --forecast FC.zarr [--forecast-year YYYY] [--method ereg] -o OUT.zarr
# The cross-validated hindcast that seasonal-skill scores.
uv run ${CLAUDE_SKILL_DIR}/scripts/seasonal_calibrate.py --hindcast HIND.zarr --obs OBS.zarr --cv loyo [--cv-window 5] -o CV.zarr
# Several models, averaged.
uv run ${CLAUDE_SKILL_DIR}/scripts/seasonal_calibrate.py --hindcast A.zarr --hindcast B.zarr --obs OBS.zarr --forecast A_fc.zarr --forecast B_fc.zarr -o OUT.zarr
```

### Arguments

- `--hindcast`: model hindcast Zarr store from `accord-fetch`, already on the observation grid. Repeat for several models. Required.
- `--obs`: seasonal observations Zarr store from `accord-fetch`. Required.
- `--forecast`: the model's real-time forecast (one issuance), one per `--hindcast` and in the same order.
- `--method`: `ereg` (default), `logit`, or `smoothed_regression`.
- `--cv`: `loyo` returns the leave-year-out cross-validated hindcast instead of a forecast.
- `--cv-window`: years left out per fold. Default 1; 5 matches PyCPT.
- `--output-type`: `tercile` (default) or `deterministic` (for `ereg` and `smoothed_regression`).
- `--forecast-year`: the year the forecast is for. Default: the forecast file's year.
- `--options`: JSON object of extra keyword arguments for the method, for example `{"clip_negative": true}` for rainfall.
- `--init-month`, `--target`: needed only when the hindcast lacks the `init_month` and `target_season` attributes.
- `--output`, `-o`: output Zarr store.

### Output

- Tercile: `prob_below`, `prob_normal`, and `prob_above`, each with `units = "1"`. A forecast is one issuance (scalar `time` plus `step`), and a `--cv loyo` hindcast has one `init_time` per year. Attributes: `cross_validated` (true only with `--cv`), `method`, `tercile_method`, `cv_window`, and `hindcast_years`.
- Deterministic: one variable named after the observations.

### Notes

- Besides `seasonal-outlook`, `--cv loyo` is the only way to produce a hindcast that `seasonal-skill` accepts.
- This skill doesn't regrid. Fetch the model and the observations with the same `accord-fetch --grid-res` so that they share a grid (NMME is 1°, CHIRPS 0.05°).

### Example

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/seasonal_calibrate.py --hindcast ccsm4_mam_hindcast.zarr --obs chirps_mam.zarr --cv loyo --cv-window 5 -o ccsm4_mam_cv.zarr
```
