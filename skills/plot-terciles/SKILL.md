---
name: plot-terciles
description: "Draw a seasonal tercile probability forecast (one issuance) as a dominant-tercile map PNG in the IRI/PyCPT convention, with africas2s's packaged RCC colour languages (icpac, acmad, noaa-cpc, ...). Use after seasonal-downscale, seasonal-calibrate or seasonal-outlook to show an outlook."
license: MIT
compatibility: Requires Python 3.12 and uv. Needs matplotlib and cartopy (installed by the script); the first map on a machine may download Natural Earth borders. First run installs the ACCORD libraries (about a minute).
allowed-tools: Bash(uv run ${CLAUDE_SKILL_DIR}/scripts/plot_terciles.py *)
metadata:
  catalog-group: figure
  version: "0.1.0"
---

# plot-terciles

Each grid cell is coloured by its most likely tercile (below / near / above normal), shaded by that probability.

## Usage

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/plot_terciles.py -i FORECAST.zarr [--title TEXT] [--variable-kind precip|temp] [--style icpac] [--smooth] -o MAP.png
```

### Arguments
- `--input`, `-i` — tercile probability Zarr for one issuance. Required.
- `--title` — map title.
- `--variable-kind` — `precip` (default) or `temp` colour convention.
- `--style` — a packaged colour language: `acmad`, `icpac`, `icpac-onset`, `icpac-temperature`, `noaa-cpc`. Default: the library's default scheme.
- `--smooth` — smooth the field before drawing.
- `--output`, `-o` — output PNG; provenance is stamped in the file.

### Output
- A PNG with the map and legend; the weather-skills history is embedded in the image metadata.

### Notes
- A cross-validated hindcast (several issuances) is refused: select one `init_time` first.
- The map shows probabilities as they are; whether they are skilful is `seasonal-skill`'s job.

### Example
```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/plot_terciles.py -i mme_mam_2025.zarr --title "MAM 2025 rainfall outlook" --style icpac -o mam_2025.png
```
