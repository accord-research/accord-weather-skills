---
name: seasonal-skill
description: "Verify a cross-validated seasonal tercile hindcast against observations with africas2s: per-cell skill maps (RPSS, ROC, reliability, ...) and domain-mean scores. Refuses forecasts that were not cross-validated, since scoring a fit on its own training years overstates skill. Use after seasonal-calibrate --cv loyo or on seasonal-outlook's hindcast output."
license: MIT
compatibility: Requires Python 3.12 and uv. Offline once the inputs exist. First run on a machine installs the ACCORD libraries (about a minute).
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
- `--forecast` — a cross-validated tercile hindcast Zarr: the output of `seasonal-calibrate --cv loyo`, or the hindcast output of `seasonal-outlook`. Required.
- `--obs` — seasonal observations Zarr from `accord-fetch` on the same grid and years. Required.
- `--metrics` — metric name, repeatable. Default `rpss`. Others: `roc`, `reliability`, `groc`, `2afc`, or the preset `svslrf`.
- `--options` — JSON object forwarded to every metric, e.g. `{"bounded": true}` for RPSS.
- `--output`, `-o` — output Zarr.

### Output
- One `(lat, lon)` variable per metric that has a map (`units = "1"`); domain means as attrs `score_<metric>`; `metrics`, `cross_validated: true`, `forecast_method`, `tercile_method`, `cv_window`, `hindcast_years`.

### Notes
- A file with `cross_validated: false` (from `seasonal-downscale`, or a forecast from `seasonal-calibrate`) is refused with a message naming where honest hindcasts come from.
- Version 1 scores tercile files only.

### Example
```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/seasonal_skill.py --forecast ccsm4_mam_cv.zarr --obs chirps_mam.zarr --metrics rpss --metrics roc -o ccsm4_mam_skill.zarr
```
