---
name: seasonal-outlook
description: "ACMAD's standard seasonal rainfall (or temperature) outlook in one call: fetch the NMME/C3S models and the observations for a season and box, run africas2s's multi-model pipeline with leave-year-out cross-validation, and write the tercile probability forecast (with skill scores), the cross-validated hindcast and the dominant-tercile map. Use when a task asks for a seasonal outlook for a region."
license: MIT
compatibility: Requires Python 3.12 and uv. Network for the fetches (NMME and CHIRPS need no credentials; c3s/* needs a CDS key). A first run for a new region downloads six models and CHIRPS and runs cross-validation, minutes to 15-25 minutes; repeats on the same machine take about 30 s (acmadDL cache under ACMADDL_CACHE_DIR, default ~/.nuthatch/caches). First run on a machine also installs the ACCORD libraries (about a minute).
allowed-tools: Bash(uv run ${CLAUDE_SKILL_DIR}/scripts/seasonal_outlook.py *)
metadata:
  catalog-group: transforms
  version: "0.1.0"
---

# seasonal-outlook

The same recipe the hosted ACCORD service runs: models and observations in, a cross-validated multi-model tercile outlook out.

## Usage

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/seasonal_outlook.py --init YYYY-MM --target MAM --bbox N/W/S/E [--models nmme/ccsm4 --models nmme/cfsv2 ...] [--predictand obs/chirps-v3-monthly] [-v precip|temp] [--hindcast 1993 2016] [--method cca] [--cv-window 5] [--title TEXT] -o FORECAST.zarr -o HINDCAST.zarr -o MAP.png
```

Three `-o` flags, in this order: the forecast, the cross-validated hindcast, the map.

### Arguments
- `--init` — issuance month `YYYY-MM`. Required.
- `--target` — target season as month initials (`MAM`, `JJAS`, `OND`, ...). Required.
- `--bbox` — `N/W/S/E` decimal degrees. Required.
- `--models` — acmadDL forecast product id, repeatable. Default: the six NMME precipitation models (`nmme/ccsm4`, `nmme/cfsv2`, `nmme/geoss2s`, `nmme/cansipsic4`, `nmme/spear`, `nmme/cesm1`). Keep several: with one model the pooled probabilities collapse to 0/1 except under `cca`.
- `--predictand` — observation product; default `obs/chirps-v3-monthly` (rainfall), use `obs/era5` for temperature.
- `--variable`, `-v` — `precip` (default) or `temp`.
- `--hindcast` — `FIRST LAST` years (default `1993 2016`).
- `--method` — `cca` (default, PyCPT-style), `bcsd`, `qm`, `dqm`, `delta`, `climatology` (no-skill baseline), `rank-analog`.
- `--cv-window` — years left out per cross-validation fold (default 5, PyCPT's).
- `--title` — map title; default built from the request.
- `--output`, `-o` — three outputs: forecast Zarr, hindcast Zarr, map PNG.

### Output
- Forecast Zarr: `prob_below`, `prob_normal`, `prob_above` for the issuance (`cross_validated: false`), attrs `score_rpss` and the other domain-mean skill scores of the cross-validated hindcast, `models`, `predictand`, `method`, `tercile_method`, `hindcast_years`.
- Hindcast Zarr: the same three variables with one `init_time` per hindcast year, `cross_validated: true`, `cv_window`; this is what `seasonal-skill` scores and `seasonal-ensemble` weights.
- Map PNG: the dominant-tercile map with provenance embedded.

### Notes
- Skill scores are computed on held-out years. Treat `score_rpss` below 0 as no skill, below 0.05 marginal, below 0.15 modest.
- Wrap-around seasons (`DJF`) are not yet supported for the CHIRPS predictand by acmadDL.

### Example
```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/seasonal_outlook.py --init 2025-09 --target OND --bbox 5/34/-5/42 -o kenya_ond_2025.zarr -o kenya_ond_cv.zarr -o kenya_ond_2025.png
```
Kenya's OND 2025 rainfall outlook from the six NMME models, CCA, September issuance.
