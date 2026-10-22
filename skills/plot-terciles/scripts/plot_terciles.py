# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#   "weather-skills-core>=0.1.1",
#   "acmadDL @ git+https://github.com/ACMAD-Niamey/acmadDL@eda1fea8b262953fb1ce56098ce6432365be8e3b",
#   "africas2s @ git+https://github.com/ACMAD-Niamey/africas2s@86be4da2ac8ef71034cbf59d1f6ea64f19d2dd8f",
#   "matplotlib",
#   "cartopy",
# ]
# [tool.uv]
# override-dependencies = ["zarr>=3.1.0", "xarray>=2026.7"]
# ///
"""Draw a seasonal tercile probability forecast as a dominant-tercile map (PNG) with africas2s."""

from __future__ import annotations

from pathlib import Path

from weather_skills_core import Dataset, UsageError, weather_skill

import accord_contract as C

# Kept in lockstep with SKILL.md metadata.version.
_SKILL_VERSION = "0.1.0"

STYLES = ["acmad", "icpac", "icpac-onset", "icpac-temperature", "noaa-cpc"]


@weather_skill(name="plot-terciles", version=_SKILL_VERSION)
@weather_skill.argument("-i", "--input", type=Dataset("any"), required=True, dest="ds",
                        help="A tercile probability Zarr for one issuance (seasonal-downscale/-calibrate/-outlook output).")
@weather_skill.argument("--title", help="Map title.")
@weather_skill.argument("--variable-kind", choices=["precip", "temp"], default="precip",
                        help="Colour convention: precip (below=dry colours, above=wet) or temp (below=cool, above=warm).")
@weather_skill.argument("--style", choices=STYLES, help="A packaged RCC colour language, e.g. icpac or acmad.")
@weather_skill.argument("--smooth", action="store_true", help="Smooth the probability field before drawing.")
def plot_terciles(ds, output, title=None, variable_kind="precip", style=None, smooth=False, **kwargs):
    """Dominant-tercile map in the IRI/PyCPT convention: each cell coloured by its most likely category."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    import africas2s

    if not C.is_tercile_file(ds):
        raise UsageError("plot-terciles draws tercile probability files (prob_below/prob_normal/prob_above); "
                         f"the input has {list(ds.data_vars)}")
    probs = C.variables_to_terciles(ds)
    if "year" in probs.dims:
        raise UsageError("one issuance per map: this file has an init_time axis (a hindcast); select one init_time first")
    style_obj = africas2s.TercileStyle.named(style) if style else None
    try:
        africas2s.plot_terciles(probs, title=title, variable_kind=variable_kind, smooth=smooth, style=style_obj)
    except (ValueError, KeyError, RuntimeError, TypeError) as exc:
        raise UsageError(f"{type(exc).__name__}: {exc}") from exc
    out = Path(output)
    plt.gcf().savefig(out, dpi=150, bbox_inches="tight")
    plt.close("all")
    return out


if __name__ == "__main__":
    plot_terciles()
