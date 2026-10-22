---
name: seasonal-ensemble
description: "Combine several seasonal tercile probability files (from seasonal-downscale, seasonal-calibrate, or seasonal-outlook) into one multi-model ensemble with africas2s, using uniform, skill-weighted, or drop-worst weights. A uniform ensemble of cross-validated hindcasts stays cross-validated; skill-based weights are fit in sample, and the result is labeled accordingly. Use to merge the models' outlooks for one season."
license: MIT
compatibility: Requires Python 3.12 and uv. Works offline once the inputs exist. The first run on a machine installs the ACCORD libraries (about a minute).
allowed-tools: Bash(uv run ${CLAUDE_SKILL_DIR}/scripts/seasonal_ensemble.py *)
metadata:
  catalog-group: transforms
  version: "0.1.0"
---

# seasonal-ensemble

Combines tercile probability maps into one weighted outlook, renormalized onto the probability simplex per cell.

## Usage

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/seasonal_ensemble.py -i A.zarr -i B.zarr [-i C.zarr ...] [--obs OBS.zarr] [--strategy uniform] [--optimize-ensemble] -o OUT.zarr
```

### Arguments

- `--input`, `-i`: tercile probability Zarr store (`prob_below`, `prob_normal`, `prob_above`). Repeat for each member. All members must share one grid and one time layout. Required.
- `--obs`: seasonal observations Zarr store from `accord-fetch`. Needed for `skill_weighted` and `drop_worst`, which score each member with `africas2s.skill`. Every member must then be a cross-validated hindcast.
- `--strategy`: `uniform` (default), `skill_weighted`, or `drop_worst`. `bma` is rejected in this version because it fits on continuous hindcasts.
- `--optimize-ensemble`: rejected in this version, because the library optimizes on continuous hindcasts only.
- `--primary-metric`: metric used when optimizing. Default `rpss`.
- `--options`: JSON object of extra keyword arguments for `africas2s.ensemble`, for example `{"n_drop": 1}`.
- `--output`, `-o`: output Zarr store.

### Output

- `prob_below`, `prob_normal`, and `prob_above` (`units = "1"`) in the inputs' time layout. Attributes: `method: ensemble:<strategy>`, `weights`, `weights_fit` (`none` for uniform, `in_sample` otherwise), `member_names`, `member_scores`, `primary_metric`, `effective_n`, `gate_passed`, `members_cross_validated`, `models` (the union of the members'), and `cross_validated`, which is true only for a uniform ensemble whose every input was a cross-validated hindcast. With `--obs`, such an ensemble also carries its own `score_<metric>` with `score_source: ensemble`. A member's scores are never passed through.

### Notes

- Inputs must share the time layout and season: either all cross-validated hindcasts over the same years, or all single issuances. A hindcast mixed with a forecast is rejected.
- `skill_weighted` and `drop_worst` fit their weights on the same years that `seasonal-skill` would score, so their output is labeled `cross_validated: false`. For a scoreable multi-model hindcast, use `uniform`.
- This version combines tercile files only. Continuous fields are rejected.

### Example

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/seasonal_ensemble.py -i ccsm4_mam_cv.zarr -i cfsv2_mam_cv.zarr --obs chirps_mam.zarr --strategy skill_weighted -o mme_mam_cv.zarr
```
