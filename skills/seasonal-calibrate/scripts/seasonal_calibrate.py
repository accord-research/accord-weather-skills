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
"""Calibrate seasonal model output into tercile probabilities on the observation grid (ereg, logit, smoothed regression), optionally as a leave-year-out cross-validated hindcast."""

from __future__ import annotations

from weather_skills_core import Dataset, UsageError, weather_skill

import accord_contract as C

# Kept in lockstep with SKILL.md metadata.version.
_SKILL_VERSION = "0.1.0"

PREDICTOR = Dataset([("lat", "lon", "init_time", "member"), ("lat", "lon", "member")])   # a hindcast, or one issuance
_TERCILE_METHOD = {"ereg": "gaussian", "logit": "logistic", "smoothed_regression": "parametric"}


def _season_of(da, init_month, target):
    month = da.attrs.get("init_month", init_month)
    season = da.attrs.get("target_season", target)
    if month is None or season is None:
        raise UsageError("the hindcast carries no init_month/target_season attrs (it was not written by "
                         "accord-fetch); pass --init-month and --target")
    return int(month), str(season)


def _labels(hinds):
    """Model names for several hindcasts: the fetch's product, made unique."""
    out = []
    for i, h in enumerate(hinds):
        src = str(h.attrs.get("weather_skills_source", "")).split(":")[-1].split("/")[-1] or f"model{i + 1}"
        out.append(src if src not in out else f"{src}_{i + 1}")
    return out


@weather_skill(name="seasonal-calibrate", version=_SKILL_VERSION)
@weather_skill.argument("--hindcast", type=PREDICTOR, action="append", required=True, dest="hindcast",
                        help="Model hindcast Zarr from accord-fetch, already on the obs grid. Repeat for several models.")
@weather_skill.argument("--obs", type=Dataset("observations"), required=True, dest="obs",
                        help="Seasonal observations Zarr from accord-fetch (time, lat, lon).")
@weather_skill.argument("--forecast", type=PREDICTOR, action="append", dest="forecast",
                        help="The model's real-time forecast (one issuance); one per --hindcast, same order.")
@weather_skill.argument("--method", choices=["ereg", "logit", "smoothed_regression"], default="ereg",
                        help="ereg (default; ensemble regression), logit, or smoothed_regression.")
@weather_skill.argument("--cv", choices=["loyo"],
                        help="loyo: return the leave-year-out cross-validated hindcast instead of a forecast.")
@weather_skill.argument("--cv-window", type=int, default=1, help="Years left out per fold (5 matches PyCPT).")
@weather_skill.argument("--output-type", choices=["tercile", "deterministic"], default="tercile",
                        help="tercile probabilities (default) or the deterministic calibrated field.")
@weather_skill.argument("--forecast-year", type=int, help="The year the forecast is for (default: the forecast file's).")
@weather_skill.argument("--options", help='JSON object of extra keyword arguments for the method, e.g. {"clip_negative": true}.')
@weather_skill.argument("--init-month", type=int, help="Issuance month if the hindcast lacks an init_month attr.")
@weather_skill.argument("--target", help="Target season if the hindcast lacks a target_season attr.")
def seasonal_calibrate(hindcast, obs, output, forecast=None, method="ereg", cv=None, cv_window=1,
                       output_type="tercile", forecast_year=None, options=None, init_month=None, target=None,
                       **kwargs):
    """Calibrate one or several models' seasonal output against observations, without regridding.

    With --forecast the result is one issuance (cross_validated=false). With --cv loyo it is the
    leave-year-out hindcast (cross_validated=true), the input seasonal-skill scores.
    """
    import africas2s

    opts = C.parse_options(options)
    hinds = [C.to_year_axis(h) for h in hindcast]
    for h in hinds:
        if "year" not in h.dims:
            raise UsageError("--hindcast must hold several issuances (an init_time axis), not one forecast")
    o = C.to_year_axis(obs)
    month, season = _season_of(hinds[0], init_month, target)
    fcs = [C.to_year_axis(f) for f in (forecast or [])]
    for f in fcs:
        if "year" in f.dims:
            raise UsageError("--forecast holds several issuances (an init_time axis); select one init_time first")
    if fcs and len(fcs) != len(hinds):
        raise UsageError("pass one --forecast per --hindcast, in the same order")
    if not fcs and not cv:
        raise UsageError("pass --forecast (to issue a forecast) or --cv loyo (to make a cross-validated hindcast)")
    pairs = [(h, fcs[i] if fcs else h.isel(year=-1, drop=True)) for i, h in enumerate(hinds)]
    predictor = pairs[0] if len(pairs) == 1 else dict(zip(_labels(hinds), pairs))
    year = int(forecast_year) if forecast_year is not None else (
        int(fcs[0].attrs["forecast_year"]) if fcs and "forecast_year" in fcs[0].attrs else int(hinds[0]["year"].max()))
    try:
        result = africas2s.calibrate(predictor, o, method=method, output_type=output_type, forecast_year=year,
                                     cv=cv, cv_window=cv_window, **opts)
    except (ValueError, KeyError, NotImplementedError, RuntimeError, TypeError) as exc:
        raise UsageError(f"{type(exc).__name__}: {exc}") from exc
    years = (int(min(int(h["year"].min()) for h in hinds)), int(max(int(h["year"].max()) for h in hinds)))
    if output_type == "tercile":
        out = C.terciles_to_variables(result, init_month=month, target=season, cross_validated=bool(cv),
                                      method=method, tercile_method=_TERCILE_METHOD.get(method),
                                      cv_window=cv_window if cv else None, hindcast_years=years, forecast_year=year)
    else:
        out = C.predictor_to_standard(result, product=f"africas2s:calibrate-{method}", variable=o.name,
                                      init_month=month, target=season, forecast_year=year)
        out.attrs["cross_validated"] = bool(cv)
    return C.stamp_versions(out)


if __name__ == "__main__":
    seasonal_calibrate()
