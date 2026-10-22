---
name: accord-fetch
description: "Fetch one ACCORD seasonal product from acmadDL's catalog as a weather-skills Zarr: a forecast model's multi-year hindcast (one init_time per year, members kept), its real-time forecast for an issuance month, or an observation product's seasonal mean per year. Use when a seasonal chain needs NMME or C3S model data or CHIRPS/ERA5 seasonal observations for a target season and box."
license: MIT
compatibility: Requires Python 3.12 and uv. nmme/* and obs/chirps-* need no credentials; c3s/* needs a Copernicus CDS key (CDSAPI_URL/CDSAPI_KEY or ~/.cdsapirc). The first run on a machine installs the ACCORD libraries (about a minute). Downloads are cached under ACMADDL_CACHE_DIR (default ~/.nuthatch/caches).
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
    note: Seasonal models are issued monthly. --probe-latest prints none in this version, so pass --init explicitly.
---

# accord-fetch

Fetches one product from acmadDL's seasonal catalog and writes it in the weather-skills standard shape. Each call takes one of the following forms.

## Usage

```bash
# A model hindcast: one init_time per year, members kept.
uv run ${CLAUDE_SKILL_DIR}/scripts/accord_fetch.py --product nmme/ccsm4 -v precip --init YYYY-MM --target MAM --hindcast FIRST LAST [--bbox N/W/S/E] [--grid-res DEG] -o hindcast.zarr
# The same model's real-time forecast for the issuance month.
uv run ${CLAUDE_SKILL_DIR}/scripts/accord_fetch.py --product nmme/ccsm4 -v precip --init YYYY-MM --target MAM [--bbox N/W/S/E] -o forecast.zarr
# Seasonal observations, one value per year.
uv run ${CLAUDE_SKILL_DIR}/scripts/accord_fetch.py --product obs/chirps-v3-monthly -v precip --target MAM --hindcast FIRST LAST [--bbox N/W/S/E] -o obs.zarr
# The latest-issuance probe.
uv run ${CLAUDE_SKILL_DIR}/scripts/accord_fetch.py --product nmme/ccsm4 -v precip --target MAM --probe-latest
```

### Arguments

- `--product`: acmadDL product ID. Required. Forecast models are `nmme/*` (for example, `nmme/ccsm4`, `nmme/cfsv2`, `nmme/geoss2s`, `nmme/cansipsic4`, `nmme/spear`, and `nmme/cesm1`) and `c3s/*`. Observations are `obs/*` (for example, `obs/chirps-v3-monthly` for rainfall and `obs/era5` for temperature).
- `--variable`, `-v`: `precip`, `temp`, or `sst`. Required.
- `--init`: issuance month as `YYYY-MM`. Required for forecast models and ignored for `obs/*`.
- `--target`: target season as month initials, such as `MAM`, `JJAS`, `OND`, or `DJF`. Required.
- `--bbox`: bounding box as `N/W/S/E` in decimal degrees. Default: the product's full domain.
- `--hindcast`: `FIRST LAST`, inclusive years. With a model, fetches the hindcast; without it, the real-time forecast. Required for `obs/*`.
- `--grid-res`: interpolates onto a regular latitude-longitude grid with this spacing in degrees over `--bbox`. Requires `--bbox`. If you plan to pass a model and its observations to `seasonal-calibrate`, which doesn't regrid, fetch both with the same `--grid-res`.
- `--probe-latest`: prints `none` and exits, because acmadDL has no issuance probe yet. Takes no `-o`.
- `--output`, `-o`: output Zarr store.

### Output

- Hindcast: dimensions `(init_time, lead_time, member, lat, lon)`. `init_time` is the first of the `--init` month in each hindcast year, and the single `lead_time` holds the nominal offset to the season's first day. Variable attributes: `target_season`, `init_month`, `aggregation_period` (`3 month` for a three-month season), `cell_methods: time: mean`, and pint-parseable `units` (`mm day-1` for model rainfall).
- Real-time forecast: the same, with a scalar `time` (the issuance) and a one-step `step` axis instead of `init_time`. This is the layout that Rhiza's own fetchers write.
- Observations: dimensions `(time, lat, lon)`, where `time` is the first day of the season in each year. The value is the seasonal mean rate (`mm month-1` for CHIRPS monthly, `mm day-1` for GPCP and ERA5), with `cell_methods: time: mean` and `aggregation_period` stamped. For a seasonal total, run `convert-to-totals`.
- Dataset attributes: `weather_skills_source = acmaddl:<product>`, `acmaddl_version`, and `africas2s_version`.

### Notes

- This fetcher is seasonal-shaped: it collapses the target season. For sub-seasonal and daily products, use Rhiza's own fetchers.
- The first fetch of a new box and season downloads from the source, which takes minutes. Later fetches use the cache.
- acmadDL doesn't yet support wrap-around seasons (`DJF`, `NDJF`) for `obs/*` predictands.

### Example

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/accord_fetch.py --product nmme/ccsm4 -v precip --init 2025-02 --target MAM --hindcast 1993 2016 --bbox 5/34/-5/42 -o ccsm4_mam_hindcast.zarr
```

Writes CCSM4's February-issued MAM hindcast over Kenya, 1993 to 2016, with members kept.
