# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#   "weather-skills-core>=0.1.1",
#   "acmadDL @ git+https://github.com/ACMAD-Niamey/acmadDL@eda1fea8b262953fb1ce56098ce6432365be8e3b",
#   "africas2s @ git+https://github.com/ACMAD-Niamey/africas2s@86be4da2ac8ef71034cbf59d1f6ea64f19d2dd8f",
# ]
# [tool.uv]
# override-dependencies = ["zarr>=3.1.0", "xarray>=2026.7"]
# ///
"""Score a cross-validated seasonal tercile hindcast against observations with africas2s.skill."""

from __future__ import annotations

from weather_skills_core import Dataset, UsageError, weather_skill

import accord_contract as C

# Kept in lockstep with SKILL.md metadata.version.
_SKILL_VERSION = "0.1.0"


@weather_skill(name="seasonal-skill", version=_SKILL_VERSION)
@weather_skill.argument("--forecast", type=Dataset("any"), required=True, dest="forecast",
                        help="A cross-validated tercile hindcast Zarr (seasonal-calibrate --cv loyo or seasonal-outlook).")
@weather_skill.argument("--obs", type=Dataset("observations"), required=True, dest="obs",
                        help="Seasonal observations Zarr from accord-fetch, same grid and years.")
@weather_skill.argument("--metrics", action="append",
                        help="Metric name, repeatable: rpss (default), roc, reliability, ... or a preset such as svslrf.")
@weather_skill.argument("--options", help='JSON object forwarded to every metric, e.g. {"bounded": true}.')
def seasonal_skill(forecast, obs, output, metrics=None, options=None, **kwargs):
    """Per-cell skill maps and domain-mean scores for a cross-validated tercile hindcast.

    Refuses a file that is not cross-validated: scoring a fit on its own training years
    overstates skill.
    """
    import africas2s

    if not C.is_tercile_file(forecast):
        raise UsageError("version 1 scores tercile hindcasts (prob_below/prob_normal/prob_above); "
                         f"the input has {list(forecast.data_vars)}")
    C.require_cross_validated(forecast, skill_name="seasonal-skill")
    from africas2s.skill import PRESETS

    expanded = []
    for m in (list(metrics) if metrics else ["rpss"]):
        names = PRESETS.get(m)
        expanded.extend(names if isinstance(names, (list, tuple)) else [m])
    metrics = expanded
    probs = C.variables_to_terciles(forecast)
    if "year" not in probs.dims:
        raise UsageError("the hindcast has a single issuance; a cross-validated hindcast spans several years")
    o = C.to_year_axis(obs)
    try:
        report = africas2s.skill(probs, o, metrics=metrics, spatial=True, **C.parse_options(options))
    except (ValueError, KeyError, NotImplementedError, RuntimeError, TypeError) as exc:
        raise UsageError(f"{type(exc).__name__}: {exc}") from exc
    out = C.skill_to_standard(report, metrics=metrics)
    out.attrs.update(cross_validated=True, forecast_method=str(forecast.attrs.get("method")),
                     tercile_method=str(forecast.attrs.get("tercile_method")),
                     cv_window=int(forecast.attrs.get("cv_window", 0)),
                     hindcast_years=list(forecast.attrs.get("hindcast_years", [])),
                     weather_skills_source=f"africas2s:skill")
    return C.stamp_versions(out)


if __name__ == "__main__":
    seasonal_skill()
