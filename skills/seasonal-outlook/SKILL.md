---
name: seasonal-outlook
description: "ACMAD's standard seasonal rainfall (or temperature) outlook in one call: fetch the NMME/C3S models and the observations for a season and box, run africas2s's multi-model pipeline with leave-year-out cross-validation, and write the tercile probability forecast (with skill scores), the cross-validated hindcast, and the dominant-tercile map. Use when a task asks for a seasonal outlook for a region."
license: MIT
compatibility: Requires Python 3.12 and uv. Needs network access for the fetches (NMME and CHIRPS need no credentials; c3s/* needs a CDS key). The first run for a new region downloads six models and CHIRPS and runs cross-validation, which takes 15 to 25 minutes. Repeats on the same machine take about 30 seconds (acmadDL cache under ACMADDL_CACHE_DIR, default ~/.nuthatch/caches). The first run on a machine also installs the ACCORD libraries (about a minute).
allowed-tools: Bash(uv run ${CLAUDE_SKILL_DIR}/scripts/seasonal_outlook.py *)
metadata:
  catalog-group: transforms
  version: "0.1.0"
---

# seasonal-outlook

Runs the same recipe as the hosted ACCORD service: models and observations in, a cross-validated multi-model tercile outlook out.

## Usage

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/seasonal_outlook.py --init YYYY-MM --target MAM --bbox N/W/S/E [--models nmme/ccsm4 --models nmme/cfsv2 ...] [--predictand obs/chirps-v3-monthly] [-v precip|temp] [--hindcast 1993 2016] [--method cca] [--cv-window 5] [--title TEXT] -o FORECAST.zarr -o HINDCAST.zarr -o MAP.png
```

Pass three `-o` flags, in this order: the forecast, the cross-validated hindcast, and the map.

### Arguments

- `--init`: issuance month as `YYYY-MM`. Required.
- `--target`: target season as month initials, such as `MAM`, `JJAS`, or `OND`. Required.
- `--bbox`: bounding box as `N/W/S/E` in decimal degrees. Required.
- `--models`: acmadDL forecast product ID. Repeat for several models. Default: the six NMME precipitation models (`nmme/ccsm4`, `nmme/cfsv2`, `nmme/geoss2s`, `nmme/cansipsic4`, `nmme/spear`, and `nmme/cesm1`). Keep several, because with one model the pooled probabilities collapse to 0 or 1 except under `cca`.
- `--predictand`: observation product. Default `obs/chirps-v3-monthly` (rainfall). For temperature, use `obs/era5`.
- `--variable`, `-v`: `precip` (default) or `temp`.
- `--hindcast`: `FIRST LAST` years. Default `1993 2016`.
- `--method`: `cca` (default, PyCPT-style), `bcsd`, `qm`, `dqm`, `delta`, `climatology` (a no-skill baseline), or `rank-analog`.
- `--cv-window`: years left out per cross-validation fold. Default 5, which matches PyCPT.
- `--title`: map title. Default: built from the request.
- `--output`, `-o`: three outputs: the forecast Zarr store, the hindcast Zarr store, and the map PNG.

### Output

- Forecast Zarr store: `prob_below`, `prob_normal`, and `prob_above` for the issuance, with `cross_validated: false`. Attributes: `score_rpss` and the other domain-mean skill scores of the cross-validated hindcast, `models`, `predictand`, `method`, `tercile_method`, and `hindcast_years`.
- Hindcast Zarr store: the same three variables with one `init_time` per hindcast year, `cross_validated: true`, and `cv_window`. This is the file that `seasonal-skill` scores and `seasonal-ensemble` weights.
- Map PNG: the dominant-tercile map with provenance embedded.

### Notes

- Skill scores are computed on held-out years. Treat a `score_rpss` below 0 as no skill, below 0.05 as marginal, and below 0.15 as modest.
- acmadDL doesn't yet support wrap-around seasons (`DJF`) for the CHIRPS predictand.

### Example

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/seasonal_outlook.py --init 2025-09 --target OND --bbox 5/34/-5/42 -o kenya_ond_2025.zarr -o kenya_ond_cv.zarr -o kenya_ond_2025.png
```

Writes Kenya's OND 2025 rainfall outlook from the six NMME models with CCA, issued in September.
