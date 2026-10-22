---
name: accord-fetch
description: "Fetch one ACCORD seasonal product from acmadDL's catalog as a weather-skills Zarr: a forecast model's multi-year hindcast (one init_time per year, members kept), its real-time forecast for an issuance month, or an observation product's seasonal mean per year. Use when a seasonal chain needs NMME or C3S model data or CHIRPS/ERA5 seasonal observations for a target season and box."
license: MIT
compatibility: Requires Python 3.12 and uv. nmme/* and obs/chirps-* need no credentials; c3s/* needs a Copernicus CDS key (CDSAPI_URL/CDSAPI_KEY or ~/.cdsapirc). First run on a machine installs the ACCORD libraries (about a minute); downloads are cached under ACMADDL_CACHE_DIR (default ~/.nuthatch/caches).
allowed-tools: Bash(uv run ${CLAUDE_SKILL_DIR}/scripts/accord_fetch.py *)
metadata:
  catalog-group: fetchers
  version: "0.1.0"
  variables:
    - precip
    - temp
    - sst
  availability:
    shape: month
    policy: none
    lag_days: 0
    note: Seasonal models are issued monthly; --probe-latest prints none in this version, so pass --init explicitly.
---

# accord-fetch

Fetches one product from acmadDL's seasonal catalog and writes it in the weather-skills standard shape. Three forms, one per call.

## Usage

```bash
# a model hindcast: one init_time per year, members kept
uv run ${CLAUDE_SKILL_DIR}/scripts/accord_fetch.py --product nmme/ccsm4 -v precip --init YYYY-MM --target MAM --hindcast FIRST LAST [--bbox N/W/S/E] [--grid-res DEG] -o hindcast.zarr
# the same model's real-time forecast for the issuance month
uv run ${CLAUDE_SKILL_DIR}/scripts/accord_fetch.py --product nmme/ccsm4 -v precip --init YYYY-MM --target MAM [--bbox N/W/S/E] -o forecast.zarr
# seasonal observations, one value per year
uv run ${CLAUDE_SKILL_DIR}/scripts/accord_fetch.py --product obs/chirps-v3-monthly -v precip --target MAM --hindcast FIRST LAST [--bbox N/W/S/E] -o obs.zarr
uv run ${CLAUDE_SKILL_DIR}/scripts/accord_fetch.py --product nmme/ccsm4 -v precip --target MAM --probe-latest
```

### Arguments
- `--product` — acmadDL product id. Forecast models: `nmme/*` (e.g. `nmme/ccsm4`, `nmme/cfsv2`, `nmme/geoss2s`, `nmme/cansipsic4`, `nmme/spear`, `nmme/cesm1`) and `c3s/*`. Observations: `obs/*` (e.g. `obs/chirps-v3-monthly` rainfall, `obs/era5` temperature). Required.
- `--variable`, `-v` — `precip`, `temp` or `sst`. Required.
- `--init` — issuance month `YYYY-MM`. Required for forecast models; ignored for `obs/*`.
- `--target` — target season as month initials (`MAM`, `JJAS`, `OND`, `DJF`, ...). Required.
- `--bbox` — `N/W/S/E` decimal degrees. Default: the product's full domain.
- `--hindcast` — `FIRST LAST`, inclusive years. With a model: fetch the hindcast; without: the real-time forecast. Required for `obs/*`.
- `--grid-res` — interpolate onto a regular lat/lon grid of this spacing in degrees over `--bbox` (needs `--bbox`). Fetch a model and its observations with the same `--grid-res` when `seasonal-calibrate` will take both; it does not regrid.
- `--probe-latest` — print `none` and exit (acmadDL has no issuance probe yet); no `-o`.
- `--output`, `-o` — output Zarr.

### Output
- Hindcast: dims `(init_time, lead_time, member, lat, lon)`, `init_time` the first of `--init`'s month in each hindcast year, one `lead_time` holding the nominal offset to the season's first day. Variable attrs: `target_season`, `init_month`, `aggregation_period` (`3 month` for a three-month season), `cell_methods: time: mean`, pint-parseable `units` (`mm day-1` for model rainfall).
- Real-time forecast: the same with a scalar `time` (the issuance) and a one-step `step` axis instead of `init_time`, the layout Rhiza's own fetchers write.
- Observations: dims `(time, lat, lon)`, `time` the first day of the season in each year; the value is the seasonal mean rate (`mm month-1` for CHIRPS monthly, `mm day-1` for GPCP/ERA5), `cell_methods: time: mean`, `aggregation_period` stamped. Run `convert-to-totals` for a seasonal amount.
- Attrs: `weather_skills_source = acmaddl:<product>`, `acmaddl_version`, `africas2s_version`.

### Notes
- This fetcher is seasonal-shaped: it collapses the target season. For sub-seasonal and daily products use Rhiza's own fetchers.
- A first fetch of a new box and season downloads from the source (minutes); repeats hit the cache.
- Wrap-around seasons (`DJF`, `NDJF`) are not yet supported for `obs/*` predictands by acmadDL.

### Example
```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/accord_fetch.py --product nmme/ccsm4 -v precip --init 2025-02 --target MAM --hindcast 1993 2016 --bbox 5/34/-5/42 -o ccsm4_mam_hindcast.zarr
```
Writes CCSM4's February-issued MAM hindcast over Kenya, 1993–2016, members kept.
