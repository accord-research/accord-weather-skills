# Tutorial: build a seasonal rainfall outlook for Kenya with weather skills

This tutorial walks you through every ACCORD weather skill, together with the Rhiza skills they work alongside. You fetch model and observation data, build and score a cross-validated hindcast, issue a forecast, combine two models, draw the map, read a point, audit the provenance, downscale, and finally run the whole workflow in one call.

The example is the October to December (OND) 2026 rainfall season over Kenya, issued in September 2026. Every command in this tutorial was run on 2026-10-26. The numbers you get differ slightly if the data sources have updated since then.

## Objectives

- Install the `weather-skills` and `accord-weather-skills` commands.
- Fetch a model hindcast, its real-time forecast, and observations as weather-skills Zarr stores.
- Produce a cross-validated hindcast and score it honestly.
- Issue a forecast, combine two models, and draw the result.
- Use Rhiza skills on ACCORD files: `resolve-region`, `inspect-zarr`, `point-value`, `provenance`, and `clip-region`.
- Downscale a model onto a finer grid.
- Run `seasonal-outlook`, which does the whole workflow in one call.

## Costs

Everything in this tutorial is free. The NMME models and CHIRPS need no credentials. Expect the following times on a laptop:

| Step | First time on a machine | Afterwards |
| --- | --- | --- |
| First run of any skill | About a minute to build its environment | Seconds |
| Fetching a model hindcast for a new region | 1 to 3 minutes | Seconds, from the cache |
| `seasonal-outlook` for a new region | 15 to 25 minutes | Under a minute |

Downloads are cached under `~/.nuthatch/caches`, or wherever `ACMADDL_CACHE_DIR` points.

## Before you begin

1. Install [uv](https://docs.astral.sh/uv/), the Python tool that runs the skills. On macOS or Linux:

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Install Rhiza's catalog command and the ACCORD command as uv tools:

   ```bash
   uv tool install git+https://github.com/weather-skills/weather-skills-catalog
   uv tool install git+https://github.com/accord-research/accord-weather-skills
   ```

   Don't use `uvx --from ...` for these. uvx keeps the scripts inside uv's cache, and `uv run` returns an error for a script in that location.

3. Confirm that both commands list their skills:

   ```bash
   weather-skills
   accord-weather-skills
   ```

   The first command lists about 57 skills. The second lists seven: `accord-fetch`, `plot-terciles`, `seasonal-calibrate`, `seasonal-downscale`, `seasonal-ensemble`, `seasonal-outlook`, and `seasonal-skill`.

4. Make a working directory and change into it. Every file in this tutorial is written there:

   ```bash
   mkdir kenya-ond && cd kenya-ond
   ```

To see what a skill does and which flags it takes, run it with `--help`, for example `accord-weather-skills seasonal-calibrate --help`.

## 1. Find the bounding box

The ACCORD skills take a region as `--bbox N/W/S/E` in decimal degrees. Rhiza's `resolve-region` skill turns a place name into that box:

```bash
weather-skills resolve-region Kenya
```

The output is Kenya's bounding box:

```text
5.430648327058691/33.91181945760195/-4.702209472788866/41.90625762938612
```

Round it to whole degrees so that the grid lines up neatly and the files are easy to share, and keep it in a shell variable for the rest of the tutorial:

```bash
BBOX=5/34/-5/42
```

## 2. Fetch the model and the observations

`accord-fetch` fetches one acmadDL product per call. You need three files for one model: its hindcast over past years, its real-time forecast for this issuance, and the observations for the same season. Fetch all three onto a 1° grid with `--grid-res 1`, because the calibration step in this tutorial doesn't regrid.

1. Fetch the CCSM4 hindcast for OND, issued in September, for 1993 to 2016:

   ```bash
   accord-weather-skills accord-fetch --product nmme/ccsm4 -v precip --init 2026-09 --target OND \
     --hindcast 1993 2016 --bbox $BBOX --grid-res 1 -o ccsm4_hindcast.zarr
   ```

   The first run builds the skill's environment and downloads 24 years of data from the IRI Data Library, which took about a minute and a half.

2. Fetch the same model's September 2026 forecast:

   ```bash
   accord-weather-skills accord-fetch --product nmme/ccsm4 -v precip --init 2026-09 --target OND \
     --bbox $BBOX --grid-res 1 -o ccsm4_forecast.zarr
   ```

3. Fetch the CHIRPS observations for OND over the same years. Observations take no `--init`:

   ```bash
   accord-weather-skills accord-fetch --product obs/chirps-v3-monthly -v precip --target OND \
     --hindcast 1993 2016 --bbox $BBOX --grid-res 1 -o chirps_ond.zarr
   ```

If a download fails with a message such as `DAP server error`, the data server refused the request. Wait a minute and run the same command again.

## 3. Look at what you fetched

Rhiza's `inspect-zarr` skill summarizes any weather-skills file, including the ACCORD ones:

```bash
weather-skills inspect-zarr -i ccsm4_hindcast.zarr
```

The summary starts like this:

```text
Dimensions:
  lead_time: 1
  init_time: 24
  member: 10
  lat: 11
  lon: 9

Coordinates:
  init_time (init_time) datetime64[ns]
    1993-09-01, 1994-09-01, 1995-09-01, ...
  lead_time (lead_time) timedelta64[ns]
    30 days
```

Each hindcast year became an `init_time` on the first of September, with one nominal `lead_time` of 30 days to the start of October. The ten ensemble members are kept. The `precip` variable is the OND total in `mm`, carrying `target_season`, `init_month`, and `aggregation_period: 3 month`.

The observations file has a `time` axis instead, one step per year, and holds the seasonal mean rate in `mm month-1`. If you want seasonal totals from it, Rhiza's `convert-to-totals` skill multiplies the rate by the stamped period:

```bash
weather-skills convert-to-totals -i chirps_ond.zarr -o chirps_ond_totals.zarr
```

## 4. Build a cross-validated hindcast

`seasonal-calibrate` fits a statistical model per grid cell between the hindcast and the observations. With `--cv loyo`, it refits with each year held out and returns the leave-year-out hindcast, which is the only kind of file that `seasonal-skill` scores. `--cv-window 5` leaves five years out per fold, which matches PyCPT:

```bash
accord-weather-skills seasonal-calibrate --hindcast ccsm4_hindcast.zarr --obs chirps_ond.zarr \
  --cv loyo --cv-window 5 -o ccsm4_cv.zarr
```

The output holds three variables, `prob_below`, `prob_normal`, and `prob_above`, one `init_time` per year, and the attribute `cross_validated: true`.

## 5. Score it

`seasonal-skill` computes skill maps and domain means for a cross-validated hindcast. Ask for the ranked probability skill score and the ROC areas:

```bash
accord-weather-skills seasonal-skill --forecast ccsm4_cv.zarr --obs chirps_ond.zarr \
  --metrics rpss --metrics roc -o ccsm4_skill.zarr
weather-skills inspect-zarr -i ccsm4_skill.zarr
```

The `rpss` variable is a map. In this run its domain mean was 0.057, with cells from -0.17 to 0.45. The ROC areas come back as domain-wide values near 0.5. Read a ranked probability skill score below 0 as no skill, below 0.05 as marginal, and below 0.15 as modest. The same numbers are stored as `score_rpss`, `score_roc_an`, and so on in the file's attributes, so other tools can read them without recomputing.

## 6. Issue a forecast, and see the honesty rule

Pass the real-time forecast to `seasonal-calibrate` to issue the OND 2026 probabilities:

```bash
accord-weather-skills seasonal-calibrate --hindcast ccsm4_hindcast.zarr --obs chirps_ond.zarr \
  --forecast ccsm4_forecast.zarr -o ccsm4_ond2026.zarr
```

This file has `cross_validated: false`, because it was fitted on all 24 years and then applied to 2026. Try to score it:

```bash
accord-weather-skills seasonal-skill --forecast ccsm4_ond2026.zarr --obs chirps_ond.zarr -o nope.zarr
```

The skill refuses, with exit code 2:

```text
Error: seasonal-skill scores cross-validated hindcasts only; this file is not one (cross_validated=False). Make one with seasonal-calibrate --cv loyo or seasonal-outlook.
```

Scoring a model on the years it was trained on would overstate its skill. The flag travels in the file, so the rule holds no matter which skill, or which provider's skill, touches the file next.

## 7. Add a second model

Repeat steps 2, 4, and 6 for GEOS-S2S. The hindcast download is the slow part again:

```bash
accord-weather-skills accord-fetch --product nmme/geoss2s -v precip --init 2026-09 --target OND \
  --hindcast 1993 2016 --bbox $BBOX --grid-res 1 -o geoss2s_hindcast.zarr
accord-weather-skills accord-fetch --product nmme/geoss2s -v precip --init 2026-09 --target OND \
  --bbox $BBOX --grid-res 1 -o geoss2s_forecast.zarr
accord-weather-skills seasonal-calibrate --hindcast geoss2s_hindcast.zarr --obs chirps_ond.zarr \
  --cv loyo --cv-window 5 -o geoss2s_cv.zarr
accord-weather-skills seasonal-calibrate --hindcast geoss2s_hindcast.zarr --obs chirps_ond.zarr \
  --forecast geoss2s_forecast.zarr -o geoss2s_ond2026.zarr
```

## 8. Combine the two models

`seasonal-ensemble` averages tercile probability files. Combine the two cross-validated hindcasts first. A uniform ensemble of cross-validated files stays cross-validated, and when you pass `--obs`, the skill scores the combination itself:

```bash
accord-weather-skills seasonal-ensemble -i ccsm4_cv.zarr -i geoss2s_cv.zarr --obs chirps_ond.zarr \
  --strategy uniform -o mme_cv.zarr
accord-weather-skills seasonal-skill --forecast mme_cv.zarr --obs chirps_ond.zarr \
  --metrics rpss --metrics roc -o mme_skill.zarr
```

Then combine the two forecasts the same way:

```bash
accord-weather-skills seasonal-ensemble -i ccsm4_ond2026.zarr -i geoss2s_ond2026.zarr -o mme_ond2026.zarr
```

In this run, the combination scored better than either model alone:

| Hindcast | Domain-mean RPSS |
| --- | --- |
| CCSM4, ensemble regression | 0.057 |
| GEOS-S2S, ensemble regression | 0.044 |
| Uniform ensemble of the two | 0.087 |

`skill_weighted` and `drop_worst` are also available. They fit their weights on the same years that `seasonal-skill` would score, so their output is labeled `cross_validated: false`.

## 9. Draw the map

`plot-terciles` draws the dominant tercile per cell, shaded by its probability, in one of the packaged regional color schemes:

```bash
accord-weather-skills plot-terciles -i mme_ond2026.zarr \
  --title "OND 2026 rainfall outlook, CCSM4 + GEOS-S2S" --style icpac -o mme_ond2026.png
```

Open `mme_ond2026.png`. In this run most of Kenya was shaded for above-normal rainfall. The provenance of the whole chain is embedded in the image.

## 10. Read the forecast at a point

Rhiza's `point-value` skill samples any gridded file at a location and writes a station file. Read the ensemble forecast at Nairobi:

```bash
weather-skills point-value -i mme_ond2026.zarr --point -1.29,36.82,nairobi -o nairobi.zarr
weather-skills inspect-zarr -i nairobi.zarr
```

In this run the three probabilities at Nairobi were:

| Category | Probability |
| --- | --- |
| Above normal | 0.75 |
| Near normal | 0.13 |
| Below normal | 0.12 |

## 11. Audit the provenance

Every file records which skills produced it and with which flags. Rhiza's `provenance` skill prints that history for a Zarr store or a PNG:

```bash
weather-skills provenance -i mme_ond2026.png
```

The lineage starts with the plot and the ensemble, then branches into each model's calibration and the three fetches behind it:

```text
1. seasonal-ensemble (v0.1.0)
   input: [ccsm4_ond2026.zarr, geoss2s_ond2026.zarr]
   args: optimize_ensemble=False, primary_metric='rpss', strategy='uniform'
   input branch a (ccsm4_ond2026.zarr):
     1. seasonal-calibrate (v0.1.0)
        input: [ccsm4_hindcast.zarr, chirps_ond.zarr, ccsm4_forecast.zarr]
        args: cv_window=1, method='ereg', output_type='tercile'
        ...
2. plot-terciles (v0.1.0)
   input: mme_ond2026.zarr
   args: smooth=False, style='icpac', title='OND 2026 rainfall outlook, CCSM4 + GEOS-S2S', variable_kind='precip'
```

To check that a file's history is well formed, add `--check`:

```bash
weather-skills provenance -i mme_ond2026.zarr --check
```

## 12. Clip to the country outline

The forecast covers the whole box. Rhiza's `clip-region` skill masks it to Kenya's border. With `--keep-outside`, cells outside the country become missing values rather than being dropped, so the grid stays rectangular:

```bash
weather-skills clip-region -i mme_ond2026.zarr --region Kenya --keep-outside -o mme_kenya.zarr
```

You can pass `mme_kenya.zarr` to `plot-terciles` or `point-value` like any other probability file.

## 13. Downscale onto a finer grid

`seasonal-downscale` fits a downscaling method on the hindcast and predicts one forecast on the observation grid, so the observations set the output resolution. Fetch CHIRPS at 0.25° and downscale the CCSM4 forecast with bias correction and spatial disaggregation (BCSD):

```bash
accord-weather-skills accord-fetch --product obs/chirps-v3-monthly -v precip --target OND \
  --hindcast 1993 2016 --bbox $BBOX --grid-res 0.25 -o chirps_ond_025.zarr
accord-weather-skills seasonal-downscale --hindcast ccsm4_hindcast.zarr --obs chirps_ond_025.zarr \
  --forecast ccsm4_forecast.zarr --method bcsd -o ccsm4_ond2026_bcsd.zarr
accord-weather-skills plot-terciles -i ccsm4_ond2026_bcsd.zarr \
  --title "OND 2026, CCSM4 downscaled with BCSD" --style icpac -o ccsm4_ond2026_bcsd.png
```

The output is on the 41 by 33 observation grid. It is a forecast, not a cross-validated hindcast, so `seasonal-skill` refuses it. Other methods are `cca`, `qm`, `dqm`, `delta`, `climatology`, and `rank-analog`.

## 14. Run the whole workflow in one call

`seasonal-outlook` runs the standard ACMAD recipe: it fetches the models and CHIRPS at native resolution, runs the multi-model pipeline with leave-year-out cross-validation, and writes the forecast, the cross-validated hindcast, and the map. Pass exactly three `-o` flags, in that order.

Its default roster is six NMME models. At the time of writing, one of them, SPEAR, had no September 2026 issuance at the data source, and the skill said so:

```text
Error: no data for 2026-09 from nmme/spear (ValueError: single_year_fetch: no data for 2026-2026). Rerun with the models that have data: --models nmme/ccsm4 --models nmme/cfsv2 --models nmme/geoss2s --models nmme/cansipsic4 --models nmme/cesm1
```

Run it with the models that have data:

```bash
accord-weather-skills seasonal-outlook --init 2026-09 --target OND --bbox $BBOX \
  --models nmme/ccsm4 --models nmme/cfsv2 --models nmme/geoss2s --models nmme/cansipsic4 --models nmme/cesm1 \
  -o kenya_ond_2026.zarr -o kenya_ond_cv.zarr -o kenya_ond_2026.png
```

For a new region this step downloads every model and CHIRPS and runs the cross-validation, which takes 15 to 25 minutes. With everything cached it took 16 seconds. The forecast is on the CHIRPS 0.05° grid, 200 by 160 cells, and its attributes carry the domain-mean scores of the cross-validated hindcast. In this run `score_rpss` was 0.14 with the default canonical correlation analysis method, the best of the hindcasts in this tutorial.

`kenya_ond_cv.zarr` is a cross-validated hindcast, so you can pass it to `seasonal-skill` for maps, or to `seasonal-ensemble` together with other hindcasts.

## Clean up

To remove the files this tutorial wrote, delete the working directory:

```bash
cd .. && rm -r kenya-ond
```

To remove the commands and their environments:

```bash
uv tool uninstall weather-skills accord-weather-skills
uv cache prune
```

Downloaded data stays in the acmadDL cache under `~/.nuthatch/caches`. Delete that directory to reclaim the space.

## What's next

- Install the skills into an agent. Rhiza's [skillkit](https://github.com/rohitg00/skillkit) copies `SKILL.md` files into a project so that an agent such as Claude Code can read them and run the same commands: `npx skillkit install weather-skills/weather-skills-catalog --list`.
- Read each skill's `SKILL.md` for every flag, output attribute, and known limit.
- For the same capabilities from a chat, ACCORD's hosted [s2s-mcp](https://github.com/accord-research/s2s-mcp) server exposes acmadDL, africas2s, and Rhiza's fetchers over MCP.
