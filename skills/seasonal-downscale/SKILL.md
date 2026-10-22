---
name: seasonal-downscale
description: "Downscale a seasonal model hindcast onto an observation grid with an africas2s method (BCSD, CCA, quantile mapping, and others) and issue one forecast as tercile probabilities or a continuous field. Use after accord-fetch when a task needs a downscaled seasonal forecast for one issuance. Not cross-validated: for a scoreable hindcast, use seasonal-calibrate --cv loyo or seasonal-outlook."
license: MIT
compatibility: Requires Python 3.12 and uv. Works offline once the inputs exist. The first run on a machine installs the ACCORD libraries (about a minute).
allowed-tools: Bash(uv run ${CLAUDE_SKILL_DIR}/scripts/seasonal_downscale.py *)
metadata:
  catalog-group: transforms
  version: "0.1.0"
---

# seasonal-downscale

Fits an africas2s downscaling method on a model hindcast against seasonal observations, then predicts one forecast on the observation grid.

## Usage

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/seasonal_downscale.py --hindcast HIND.zarr --obs OBS.zarr [--forecast FC.zarr] [--method bcsd] [--output-type tercile|continuous] [--options JSON] -o OUT.zarr
```

### Arguments

- `--hindcast`: model hindcast Zarr store from `accord-fetch` (one `init_time` per year, members kept). Required.
- `--obs`: seasonal observations Zarr store from `accord-fetch` on the target grid. Required.
- `--forecast`: the model's real-time forecast for one issuance. Without it, the skill predicts the last hindcast year as a quick check.
- `--method`: africas2s method name: `bcsd` (default), `cca`, `qm`, `dqm`, `delta`, `climatology`, or `rank-analog`.
- `--output-type`: `tercile` (default) for below, normal, and above probabilities, or `continuous` for the downscaled field.
- `--options`: JSON object of extra keyword arguments for the method, for example `{"n_modes": 3}` for CCA.
- `--init-month`, `--target`: needed only when the hindcast wasn't written by `accord-fetch` and lacks the `init_month` and `target_season` attributes.
- `--output`, `-o`: output Zarr store.

### Output

- Tercile: variables `prob_below`, `prob_normal`, and `prob_above` (`units = "1"`, summing to 1 per valid cell) on the observation grid, for one issuance (scalar `time` plus `step`). Attributes: `cross_validated: false`, `method`, `tercile_method: counting`, and `hindcast_years`.
- Continuous: one variable named after the observations, with dimensions `(step, member, lat, lon)`, in the observations' units.

### Notes

- The result is a forecast, not a cross-validated hindcast, so `seasonal-skill` rejects it. Scoreable hindcasts come from `seasonal-calibrate --cv loyo` and `seasonal-outlook`.
- `--forecast` must hold one issuance. A file with an `init_time` axis is rejected.

### Example

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/seasonal_downscale.py --hindcast ccsm4_mam_hindcast.zarr --obs chirps_mam.zarr --forecast ccsm4_2025-02.zarr --method bcsd -o ccsm4_mam_2025_bcsd.zarr
```
