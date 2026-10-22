---
name: seasonal-downscale
description: "Downscale a seasonal model hindcast onto an observation grid with an africas2s method (BCSD, CCA, quantile mapping, ...) and issue one forecast as tercile probabilities or a continuous field. Use after accord-fetch when a task needs a downscaled seasonal forecast for one issuance. Not cross-validated: for a scoreable hindcast use seasonal-calibrate --cv loyo or seasonal-outlook."
license: MIT
compatibility: Requires Python 3.12 and uv. Offline once the inputs exist. First run on a machine installs the ACCORD libraries (about a minute).
allowed-tools: Bash(uv run ${CLAUDE_SKILL_DIR}/scripts/seasonal_downscale.py *)
metadata:
  catalog-group: transforms
  version: "0.1.0"
---

# seasonal-downscale

Fits an africas2s downscaling method on a model hindcast against seasonal observations and predicts one forecast on the observation grid.

## Usage

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/seasonal_downscale.py --hindcast HIND.zarr --obs OBS.zarr [--forecast FC.zarr] [--method bcsd] [--output-type tercile|continuous] [--options JSON] -o OUT.zarr
```

### Arguments
- `--hindcast` — model hindcast Zarr from `accord-fetch` (`init_time` per year, members kept). Required.
- `--obs` — seasonal observations Zarr from `accord-fetch` on the target grid. Required.
- `--forecast` — the model's real-time forecast for one issuance. Without it the last hindcast year is predicted, as a sanity check.
- `--method` — africas2s method name: `bcsd` (default), `cca`, `qm`, `dqm`, `delta`, `climatology`, `rank-analog`.
- `--output-type` — `tercile` (default) for below/normal/above probabilities, or `continuous` for the downscaled field.
- `--options` — JSON object of extra keyword arguments for the method, e.g. `{"n_modes": 3}` for CCA.
- `--init-month`, `--target` — only needed when the hindcast was not written by `accord-fetch` and lacks `init_month`/`target_season` attrs.
- `--output`, `-o` — output Zarr.

### Output
- Tercile: variables `prob_below`, `prob_normal`, `prob_above` (`units = "1"`, sum to 1 per valid cell) on the observation grid, one issuance (scalar `time` + `step`); attrs `cross_validated: false`, `method`, `tercile_method: counting`, `hindcast_years`.
- Continuous: one variable named after the observations, dims `(step, member, lat, lon)`, in the observations' units.

### Notes
- The result is a forecast, not a cross-validated hindcast, so `seasonal-skill` refuses it. Scoreable hindcasts come from `seasonal-calibrate --cv loyo` and `seasonal-outlook`.
- `--forecast` must hold one issuance; a file with an `init_time` axis is refused.

### Example
```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/seasonal_downscale.py --hindcast ccsm4_mam_hindcast.zarr --obs chirps_mam.zarr --forecast ccsm4_2025-02.zarr --method bcsd -o ccsm4_mam_2025_bcsd.zarr
```
