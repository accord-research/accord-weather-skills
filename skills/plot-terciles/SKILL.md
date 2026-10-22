---
name: plot-terciles
description: "Draw a seasonal tercile probability forecast (one issuance) as a dominant-tercile map PNG in the IRI/PyCPT convention, with africas2s's packaged RCC color schemes (icpac, acmad, noaa-cpc, and others). Use after seasonal-downscale, seasonal-calibrate, or seasonal-outlook to show an outlook."
license: MIT
compatibility: Requires Python 3.12 and uv. Needs matplotlib and cartopy, which the script installs. The first map on a machine might download Natural Earth borders. The first run installs the ACCORD libraries (about a minute).
allowed-tools: Bash(uv run ${CLAUDE_SKILL_DIR}/scripts/plot_terciles.py *)
metadata:
  catalog-group: figure
  version: "0.1.0"
---

# plot-terciles

Colors each grid cell by its most likely tercile (below, near, or above normal), shaded by that probability.

## Usage

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/plot_terciles.py -i FORECAST.zarr [--title TEXT] [--variable-kind precip|temp] [--style icpac] [--smooth] -o MAP.png
```

### Arguments

- `--input`, `-i`: tercile probability Zarr store for one issuance. Required.
- `--title`: map title.
- `--variable-kind`: color convention, `precip` (default) or `temp`.
- `--style`: a packaged color scheme: `acmad`, `icpac`, `icpac-onset`, `icpac-temperature`, or `noaa-cpc`. Default: the library's default scheme.
- `--smooth`: smooths the field before drawing.
- `--output`, `-o`: output PNG. Provenance is stamped in the file.

### Output

- A PNG with the map and legend. The weather-skills history is embedded in the image metadata.

### Notes

- A cross-validated hindcast (several issuances) is rejected. Select one `init_time` first.
- The map shows the probabilities as they are. To learn whether they are skillful, run `seasonal-skill`.

### Example

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/plot_terciles.py -i mme_mam_2025.zarr --title "MAM 2025 rainfall outlook" --style icpac -o mam_2025.png
```
