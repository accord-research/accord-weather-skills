# accord-weather-skills

ACCORD's seasonal forecasting stack ([acmadDL](https://github.com/ACMAD-Niamey/acmadDL) for data, [africas2s](https://github.com/ACMAD-Niamey/africas2s) for downscaling, calibration and verification) packaged as [weather skills](https://github.com/weather-skills/weather-skills-catalog): one self-contained script per capability, each with a `SKILL.md` an agent can read, built on `weather-skills-core`. This repository is a provider for the catalog, which pins it as a submodule and publishes the skills under `skills/accord-weather-skills/`.

Every script wraps a public verb of acmadDL or africas2s, the same verbs the two libraries' MCP servers wrap. No statistics and no data access live here; what the repository owns is the translation between ACCORD's shapes and the weather-skills standard dataset, in one module copied beside each script.

## Skills

| Skill | Group | What it does |
| --- | --- | --- |
| `accord-fetch` | fetchers | One acmadDL seasonal product as a Zarr: a model hindcast (one `init_time` per year, members kept), its real-time forecast, or seasonal observations. |
| `seasonal-downscale` | transforms | `africas2s.downscale`: fit a method (BCSD, CCA, quantile mapping, ...) on the hindcast and issue one forecast on the observation grid. Not cross-validated. |
| `seasonal-calibrate` | transforms | `africas2s.calibrate`: ensemble regression, logit or smoothed regression without regridding; `--cv loyo` gives the leave-year-out hindcast. |
| `seasonal-ensemble` | transforms | `africas2s.ensemble`: combine tercile files with uniform, skill-weighted or drop-worst weights. |
| `seasonal-skill` | transforms | `africas2s.skill`: per-cell RPSS/ROC/... maps and domain means for a cross-validated hindcast. Refuses anything else. |
| `seasonal-outlook` | transforms | The whole workflow in one call: fetch the models and observations, `africas2s.seasonal_mme` with leave-year-out CV, write the forecast, the hindcast and the map. |
| `plot-terciles` | figure | `africas2s.plot_terciles`: the dominant-tercile map as a PNG, in the packaged RCC colour languages. |

### Two ways to a Kenya outlook

One call:

```bash
uv run skills/seasonal-outlook/scripts/seasonal_outlook.py --init 2025-09 --target OND --bbox 5/34/-5/42 \
  -o kenya_ond_2025.zarr -o kenya_ond_cv.zarr -o kenya_ond_2025.png
```

Or the building blocks, which let an agent choose each step:

```bash
F=skills; B=5/34/-5/42
uv run $F/accord-fetch/scripts/accord_fetch.py --product nmme/ccsm4 -v precip --init 2025-09 --target OND --hindcast 1993 2016 --bbox $B --grid-res 1 -o ccsm4_hind.zarr
uv run $F/accord-fetch/scripts/accord_fetch.py --product nmme/ccsm4 -v precip --init 2025-09 --target OND --bbox $B --grid-res 1 -o ccsm4_fc.zarr
uv run $F/accord-fetch/scripts/accord_fetch.py --product obs/chirps-v3-monthly -v precip --target OND --hindcast 1993 2016 --bbox $B --grid-res 1 -o chirps_ond.zarr
uv run $F/seasonal-calibrate/scripts/seasonal_calibrate.py --hindcast ccsm4_hind.zarr --obs chirps_ond.zarr --cv loyo --cv-window 5 -o ccsm4_cv.zarr
uv run $F/seasonal-skill/scripts/seasonal_skill.py --forecast ccsm4_cv.zarr --obs chirps_ond.zarr --metrics rpss --metrics roc -o ccsm4_skill.zarr
uv run $F/seasonal-calibrate/scripts/seasonal_calibrate.py --hindcast ccsm4_hind.zarr --obs chirps_ond.zarr --forecast ccsm4_fc.zarr -o ccsm4_ond_2025.zarr
uv run $F/plot-terciles/scripts/plot_terciles.py -i ccsm4_ond_2025.zarr --title "OND 2025 rainfall, CCSM4" --style icpac -o ccsm4_ond_2025.png
```

`seasonal-calibrate` does not regrid, so the model and the observations are fetched onto one grid with `--grid-res` (NMME is 1°, CHIRPS 0.05°). `seasonal-outlook` handles that itself.

## The honesty rule

A probability file states how it was made and whether it is cross-validated (`cross_validated` in its attrs). `seasonal-skill` scores only files with `cross_validated: true`, which come from `seasonal-calibrate --cv loyo` and from `seasonal-outlook`'s hindcast output. `seasonal-downscale` and a plain `seasonal-calibrate --forecast` issue forecasts; scoring a fit on its own training years would overstate skill, so those files are refused with a message naming the honest sources.

## Data shapes

The weather-skills vocabulary has no year axis and no tercile dimension, so the translation is explicit:

- A hindcast on ACCORD's `year` axis becomes an `init_time` axis (the first of the issuance month in each year) with one `lead_time`, the nominal offset to the target season; the variable carries `target_season`, `init_month`, `aggregation_period` and `cell_methods`.
- A single issuance is written the way Rhiza's own fetchers write forecasts: a scalar `time` plus a one-step `step` axis.
- Seasonal observations become a `time` axis, one step per year at the season's first day; precipitation stays the seasonal mean rate acmadDL returns (`mm month-1` for CHIRPS monthly), labelled `cell_methods: time: mean`; run `convert-to-totals` for an amount.
- Tercile probabilities are three variables, `prob_below`, `prob_normal`, `prob_above`, each `units = "1"`, with `method`, `tercile_method`, `cv_window`, `hindcast_years` and `cross_validated` on the dataset.

`tools/accord_contract.py` implements all of this and is copied verbatim beside every script (`uv run` puts a script's own directory on `sys.path`); `tools/sync_contract.py` keeps the copies identical and a test fails when one drifts.

## Running a skill

```bash
uv run skills/<name>/scripts/<script>.py --help
```

Each script declares its own dependencies (PEP 723), including acmadDL and africas2s pinned to commits. The first run on a machine builds that environment, about a minute for 250 packages; later runs start in seconds. A first `seasonal-outlook` for a new region downloads six models and CHIRPS and runs cross-validation, minutes to 15–25 minutes; repeats on the same machine take about 30 s because acmadDL caches downloads under `ACMADDL_CACHE_DIR` (default `~/.nuthatch/caches`). `plot-terciles` may download Natural Earth borders the first time.

Credentials: `nmme/*` and `obs/chirps-*` need none; `c3s/*` needs a Copernicus CDS key (`CDSAPI_URL`/`CDSAPI_KEY` or `~/.cdsapirc`).

## Known gaps in this version

- `accord-fetch --probe-latest` prints `none`: acmadDL has no issuance probe for its own products yet, so pass `--init` explicitly.
- A fetch's provenance history has one entry, the fetch itself; the `weather_skills_source` attr and `acmaddl_version` say where the data came from.
- `seasonal-ensemble` offers `uniform`, `skill_weighted` and `drop_worst`; `bma` and `--optimize-ensemble` need continuous hindcasts the library does not take from tercile files. Skill-based weights are fit in sample, so only a uniform ensemble of hindcasts stays `cross_validated: true`.
- A `lead_time` is nominal: the offset from the issuance to the season's first day in a non-leap year, zero when the issuance month opens the season. `target_season` is the authoritative label.
- `accord-fetch` is seasonal-shaped (`nmme/*`, `c3s/*`, `obs/*`); acmadDL's sub-seasonal and daily products are reachable through Rhiza's own fetchers instead.

## Development

```bash
uv sync
uv run pytest -q -m "not integration"      # offline tests
uv run pytest -q -m integration            # live fetches (network, credentials)
uv run tools/sync_contract.py              # copy tools/accord_contract.py beside every script (--check to compare)
uvx --from "git+https://github.com/rhiza-research/weather-skills-core@main" weather-skills-core lint skills --strict error
```

Tests import each script in-process and call it with an argv list (Rhiza's own test pattern), with acmadDL's network verbs stubbed by `tests/helpers.py`. Bumping the acmadDL or africas2s pin means editing the same commit in every script's header and in `pyproject.toml`.

## Joining the catalog

The catalog pins providers as git submodules on its `catalog` branch. Once this repository is public with CI green, a pull request there adding `[submodule "accord-weather-skills"]` with the HTTPS URL, pinned to a tagged commit, is the whole contribution; their CI lints the skills and the publish step copies them to `skills/accord-weather-skills/<name>/` on `main`.

## License

MIT, like acmadDL and africas2s.
