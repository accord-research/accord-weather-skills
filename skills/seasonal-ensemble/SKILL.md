---
name: seasonal-ensemble
description: "Combine several seasonal tercile probability files (from seasonal-downscale, seasonal-calibrate or seasonal-outlook) into one multi-model ensemble with africas2s: uniform, skill-weighted or drop-worst weights. A uniform ensemble of cross-validated hindcasts stays cross-validated; skill-based weights are fit in sample and the result is labelled so. Use to merge models' outlooks for one season."
license: MIT
compatibility: Requires Python 3.12 and uv. Offline once the inputs exist. First run on a machine installs the ACCORD libraries (about a minute).
allowed-tools: Bash(uv run ${CLAUDE_SKILL_DIR}/scripts/seasonal_ensemble.py *)
metadata:
  catalog-group: transforms
  version: "0.1.0"
---

# seasonal-ensemble

Weighted combination of tercile probability maps into one outlook, renormalised onto the probability simplex per cell.

## Usage

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/seasonal_ensemble.py -i A.zarr -i B.zarr [-i C.zarr ...] [--obs OBS.zarr] [--strategy uniform] [--optimize-ensemble] -o OUT.zarr
```

### Arguments
- `--input`, `-i` — tercile probability Zarr (`prob_below`, `prob_normal`, `prob_above`); repeat for each member. All on one grid with the same time layout. Required.
- `--obs` — seasonal observations Zarr from `accord-fetch`; needed for `skill_weighted` and `drop_worst`, which score each member with africas2s.skill. Every member must then be a cross-validated hindcast.
- `--strategy` — `uniform` (default), `skill_weighted`, `drop_worst`. `bma` is refused in this version (it fits on continuous hindcasts).
- `--optimize-ensemble` — refused in this version (the library optimises on continuous hindcasts only).
- `--primary-metric` — metric used when optimizing (default `rpss`).
- `--options` — JSON object of extra keyword arguments for `africas2s.ensemble`, e.g. `{"n_drop": 1}`.
- `--output`, `-o` — output Zarr.

### Output
- `prob_below`, `prob_normal`, `prob_above` (`units = "1"`) in the inputs' time layout; attrs `method: ensemble:<strategy>`, `weights`, `weights_fit` (`none` for uniform, `in_sample` otherwise), `member_names`, `member_scores`, `primary_metric`, `effective_n`, `gate_passed`, `members_cross_validated`, `models` (the union of the members'), and `cross_validated`: true only for a uniform ensemble whose every input was a cross-validated hindcast. With `--obs` such an ensemble also carries its own `score_<metric>` (`score_source: ensemble`); a member's scores are never passed through.

### Notes
- Inputs must share the time layout and season: all cross-validated hindcasts over the same years, or all single issuances. A hindcast mixed with a forecast is refused.
- `skill_weighted` and `drop_worst` fit their weights on the same years `seasonal-skill` would score, so their output is labelled `cross_validated: false`; use `uniform` for a scoreable multi-model hindcast.
- Version 1 combines tercile files only; continuous fields are refused.

### Example
```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/seasonal_ensemble.py -i ccsm4_mam_cv.zarr -i cfsv2_mam_cv.zarr --obs chirps_mam.zarr --strategy skill_weighted -o mme_mam_cv.zarr
```
