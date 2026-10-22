---
name: seasonal-skill
description: "Verify a cross-validated seasonal tercile hindcast against observations with africas2s: per-cell skill maps (RPSS, ROC, reliability, and others) and domain-mean scores. Rejects forecasts that weren't cross-validated, because scoring a fit on its own training years overstates skill. Use after seasonal-calibrate --cv loyo or on the hindcast output of seasonal-outlook."
license: MIT
compatibility: Requires Python 3.12 and uv. Works offline once the inputs exist. The first run on a machine installs the ACCORD libraries (about a minute).
allowed-tools: Bash(uv run ${CLAUDE_SKILL_DIR}/scripts/seasonal_skill.py *)
metadata:
  catalog-group: transforms
  version: "0.1.0"
---

# seasonal-skill

Scores a leave-year-out tercile hindcast cell by cell and over the domain.

## Usage

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/seasonal_skill.py --forecast CV.zarr --obs OBS.zarr [--metrics rpss --metrics roc] [--options JSON] -o SKILL.zarr
```

### Arguments

- `--forecast`: a cross-validated tercile hindcast Zarr store: the output of `seasonal-calibrate --cv loyo`, or the hindcast output of `seasonal-outlook`. Required.
- `--obs`: seasonal observations Zarr store from `accord-fetch`, on the same grid and years. Required.
- `--metrics`: metric name. Repeat for several metrics. Default `rpss`. Others: `roc`, `reliability`, `groc`, `2afc`, or the preset `svslrf`.
- `--options`: JSON object forwarded to every metric, for example `{"bounded": true}` for RPSS.
- `--output`, `-o`: output Zarr store.

### Output

- One `(lat, lon)` variable per metric that has a map, each with `units = "1"`. Domain means are the `score_<metric>` attributes, alongside `metrics`, `cross_validated: true`, `forecast_method`, `tercile_method`, `cv_window`, and `hindcast_years`.

### Notes

- A file with `cross_validated: false`, such as the output of `seasonal-downscale` or a forecast from `seasonal-calibrate`, is rejected with a message that names where honest hindcasts come from.
- This version scores tercile files only.

### Example

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/seasonal_skill.py --forecast ccsm4_mam_cv.zarr --obs chirps_mam.zarr --metrics rpss --metrics roc -o ccsm4_mam_skill.zarr
```
