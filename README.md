# accord-weather-skills

ACCORD's seasonal forecasting stack, packaged as [weather skills](https://github.com/weather-skills/weather-skills-catalog): [acmadDL](https://github.com/ACMAD-Niamey/acmadDL) fetches the data, and [africas2s](https://github.com/ACMAD-Niamey/africas2s) downscales, calibrates, and verifies it. Each skill is one self-contained script with a `SKILL.md` file that an agent can read, built on `weather-skills-core`. This repository is a provider for the catalog, which pins it as a submodule and publishes the skills under `skills/accord-weather-skills/`.

Every script wraps a public verb of acmadDL or africas2s, the same verbs that the two libraries' MCP servers wrap. No statistics and no data access live here. What this repository owns is the translation between ACCORD's data shapes and the weather-skills standard dataset, in one module that is copied into each skill.

## Skills

| Skill | Group | What it does |
| --- | --- | --- |
| `accord-fetch` | fetchers | Fetches one acmadDL seasonal product as a Zarr store: a model hindcast (one `init_time` per year, members kept), its real-time forecast, or seasonal observations. |
| `seasonal-downscale` | transforms | Runs `africas2s.downscale`: fits a method (BCSD, CCA, quantile mapping, and others) on the hindcast and issues one forecast on the observation grid. Not cross-validated. |
| `seasonal-calibrate` | transforms | Runs `africas2s.calibrate`: ensemble regression, logit, or smoothed regression without regridding. With `--cv loyo`, it returns the leave-year-out hindcast. |
| `seasonal-ensemble` | transforms | Runs `africas2s.ensemble`: combines tercile files with uniform, skill-weighted, or drop-worst weights. |
| `seasonal-skill` | transforms | Runs `africas2s.skill`: per-cell RPSS, ROC, and other maps, plus domain means, for a cross-validated hindcast. Rejects anything else. |
| `seasonal-outlook` | transforms | Runs the whole workflow in one call: fetches the models and observations, runs `africas2s.seasonal_mme` with leave-year-out cross-validation, and writes the forecast, the hindcast, and the map. |
| `plot-terciles` | figure | Runs `africas2s.plot_terciles`: draws the dominant-tercile map as a PNG in the packaged RCC color schemes. |

## Run a skill

You can run the skills in three ways. For a hands-on walkthrough of every skill, see the [tutorial](docs/tutorial.md).

### From a clone

Each script declares its own dependencies (PEP 723), including acmadDL and africas2s pinned to commits, so `uv run` builds the environment for you:

```bash
uv run skills/<name>/scripts/<script>.py --help
```

### As a command-line tool

Install the repository as a uv tool to get an `accord-weather-skills` command that lists and runs the skills:

```bash
uv tool install git+https://github.com/accord-research/accord-weather-skills
accord-weather-skills                     # lists the skills
accord-weather-skills seasonal-outlook --help
```

Don't use `uvx --from ...` for this. uvx keeps the scripts inside uv's cache, and `uv run` returns an error for a script in that location.

### Through the catalog

When this provider is in the catalog, the skills appear in the catalog's own `weather-skills` command alongside the other providers' skills, and [skillkit](https://github.com/rohitg00/skillkit) can install their `SKILL.md` files into an agent's project. For both routes, see the [catalog README](https://github.com/weather-skills/weather-skills-catalog#getting-started).

### What to expect

The first run on a machine builds the script environment, which takes about a minute for 250 packages. Later runs start in seconds. The first `seasonal-outlook` for a new region downloads six models and CHIRPS and runs cross-validation, which takes 15 to 25 minutes. Repeats on the same machine take about 30 seconds, because acmadDL caches downloads under `ACMADDL_CACHE_DIR` (default `~/.nuthatch/caches`). The first `plot-terciles` might download Natural Earth borders.

Credentials: `nmme/*` and `obs/chirps-*` need none. `c3s/*` needs a Copernicus CDS key, set through `CDSAPI_URL` and `CDSAPI_KEY` or `~/.cdsapirc`.

## Get a Kenya outlook

You can produce the outlook in one call:

```bash
uv run skills/seasonal-outlook/scripts/seasonal_outlook.py --init 2025-09 --target OND --bbox 5/34/-5/42 \
  -o kenya_ond_2025.zarr -o kenya_ond_cv.zarr -o kenya_ond_2025.png
```

Or you can run the building blocks, which let an agent choose each step:

1. Fetch the model hindcast, the model forecast, and the observations onto one grid:

   ```bash
   F=skills; B=5/34/-5/42
   uv run $F/accord-fetch/scripts/accord_fetch.py --product nmme/ccsm4 -v precip --init 2025-09 --target OND --hindcast 1993 2016 --bbox $B --grid-res 1 -o ccsm4_hind.zarr
   uv run $F/accord-fetch/scripts/accord_fetch.py --product nmme/ccsm4 -v precip --init 2025-09 --target OND --bbox $B --grid-res 1 -o ccsm4_fc.zarr
   uv run $F/accord-fetch/scripts/accord_fetch.py --product obs/chirps-v3-monthly -v precip --target OND --hindcast 1993 2016 --bbox $B --grid-res 1 -o chirps_ond.zarr
   ```

2. Build the cross-validated hindcast and score it:

   ```bash
   uv run $F/seasonal-calibrate/scripts/seasonal_calibrate.py --hindcast ccsm4_hind.zarr --obs chirps_ond.zarr --cv loyo --cv-window 5 -o ccsm4_cv.zarr
   uv run $F/seasonal-skill/scripts/seasonal_skill.py --forecast ccsm4_cv.zarr --obs chirps_ond.zarr --metrics rpss --metrics roc -o ccsm4_skill.zarr
   ```

3. Issue the forecast and draw it:

   ```bash
   uv run $F/seasonal-calibrate/scripts/seasonal_calibrate.py --hindcast ccsm4_hind.zarr --obs chirps_ond.zarr --forecast ccsm4_fc.zarr -o ccsm4_ond_2025.zarr
   uv run $F/plot-terciles/scripts/plot_terciles.py -i ccsm4_ond_2025.zarr --title "OND 2025 rainfall, CCSM4" --style icpac -o ccsm4_ond_2025.png
   ```

`seasonal-calibrate` doesn't regrid, so step 1 fetches the model and the observations onto one grid with `--grid-res` (NMME is 1°, CHIRPS 0.05°). `seasonal-outlook` handles that itself.

## The honesty rule

A probability file states how it was made and whether it is cross-validated, in its `cross_validated` attribute. `seasonal-skill` scores only files with `cross_validated: true`, which come from `seasonal-calibrate --cv loyo` and from the hindcast output of `seasonal-outlook`. `seasonal-downscale` and a plain `seasonal-calibrate --forecast` issue forecasts. Scoring a fit on its own training years would overstate skill, so `seasonal-skill` rejects those files with a message that names the honest sources.

## Data shapes

The weather-skills vocabulary has no year axis and no tercile dimension, so the translation is explicit:

- A hindcast on ACCORD's `year` axis becomes an `init_time` axis (the first of the issuance month in each year) with one `lead_time`, the nominal offset to the target season. The variable carries `target_season`, `init_month`, `aggregation_period`, and `cell_methods`: `time: sum` for an amount such as NMME's seasonal totals in `mm`, `time: mean` for a rate or a temperature. Probabilities carry no `cell_methods`.
- A single issuance is written the way Rhiza's own fetchers write forecasts: a scalar `time` plus a one-step `step` axis.
- Seasonal observations become a `time` axis, one step per year at the season's first day. Precipitation stays the seasonal mean rate that acmadDL returns (`mm month-1` for CHIRPS monthly), labeled `cell_methods: time: mean`. For a seasonal total, run `convert-to-totals`.
- Tercile probabilities are three variables, `prob_below`, `prob_normal`, and `prob_above`, each with `units = "1"`. The dataset carries `method`, `tercile_method`, `cv_window`, `hindcast_years`, and `cross_validated`.

`tools/accord_contract.py` implements all of this. It is copied into each skill as `scripts/accord_contract/__init__.py`, a package directory rather than a second script, because the catalog runner runs the one `.py` file directly inside `scripts/`, and `uv run` puts that directory on `sys.path`. `tools/sync_contract.py` keeps the copies identical, and a test fails when one drifts.

## Known gaps in this version

- `accord-fetch --probe-latest` prints `none`. acmadDL has no issuance probe for its own products yet, so pass `--init` explicitly.
- A fetch's provenance history has one entry, the fetch itself. The `weather_skills_source` and `acmaddl_version` attributes say where the data came from.
- `seasonal-ensemble` offers `uniform`, `skill_weighted`, and `drop_worst`. `bma` and `--optimize-ensemble` need continuous hindcasts, which the library doesn't take from tercile files. Skill-based weights are fit in sample, so only a uniform ensemble of hindcasts stays `cross_validated: true`.
- A `lead_time` is nominal: the offset from the issuance to the season's first day in a non-leap year, and zero when the issuance month opens the season. `target_season` is the authoritative label.
- `accord-fetch` is seasonal-shaped (`nmme/*`, `c3s/*`, `obs/*`). For acmadDL's sub-seasonal and daily products, use Rhiza's own fetchers.

## Develop

```bash
uv sync
uv run pytest -q -m "not integration"      # offline tests
uv run pytest -q -m integration            # live fetches (network, credentials)
uv run tools/sync_contract.py              # copy the contract module into every skill (--check only compares)
uvx --from "git+https://github.com/rhiza-research/weather-skills-core@main" weather-skills-core lint skills --strict error
```

The tests import each script in-process and call it with an argv list, which is Rhiza's own test pattern. acmadDL's network verbs are stubbed by `tests/helpers.py`. To bump the acmadDL or africas2s pin, edit the same commit in every script's header and in `pyproject.toml`.

## Join the catalog

The catalog pins providers as git submodules on its `catalog` branch. Once this repository is public with CI green, the whole contribution is a pull request there that adds `[submodule "accord-weather-skills"]` with the HTTPS URL, pinned to a tagged commit. Their CI lints the skills, and the publish step copies them to `skills/accord-weather-skills/<name>/` on `main`.

## License

MIT, like acmadDL and africas2s.
