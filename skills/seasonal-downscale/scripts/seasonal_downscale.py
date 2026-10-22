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
"""Downscale a seasonal hindcast onto the observation grid with an africas2s method and issue one forecast."""

from __future__ import annotations

from weather_skills_core import Dataset, UsageError, weather_skill

import accord_contract as C

# Kept in lockstep with SKILL.md metadata.version.
_SKILL_VERSION = "0.1.0"

PREDICTOR = Dataset([("lat", "lon", "init_time", "member"), ("lat", "lon", "member")])   # a hindcast, or one issuance


def season_of(da, init_month, target):
    """The issuance month and target season: from the file's attrs, else the flags."""
    month = da.attrs.get("init_month", init_month)
    season = da.attrs.get("target_season", target)
    if month is None or season is None:
        raise UsageError("the hindcast carries no init_month/target_season attrs (it was not written by "
                         "accord-fetch); pass --init-month and --target")
    return int(month), str(season)


@weather_skill(name="seasonal-downscale", version=_SKILL_VERSION)
@weather_skill.argument("--hindcast", type=PREDICTOR, required=True, dest="hindcast",
                        help="Model hindcast Zarr from accord-fetch: one init_time per year, members kept.")
@weather_skill.argument("--obs", type=Dataset("observations"), required=True, dest="obs",
                        help="Seasonal observations Zarr from accord-fetch (time, lat, lon): the target grid.")
@weather_skill.argument("--forecast", type=PREDICTOR, dest="forecast",
                        help="The model's real-time forecast (one issuance). Without it the last hindcast "
                             "year is predicted as a sanity check.")
@weather_skill.argument("--method", default="bcsd",
                        help="africas2s method: bcsd (default), cca, qm, dqm, delta, climatology, rank-analog, ...")
@weather_skill.argument("--output-type", choices=["continuous", "tercile"], default="tercile",
                        help="tercile probabilities (default) or the continuous downscaled field.")
@weather_skill.argument("--options", help='JSON object of extra keyword arguments for the method, e.g. {"n_modes": 3}.')
@weather_skill.argument("--init-month", type=int, help="Issuance month if the hindcast lacks an init_month attr.")
@weather_skill.argument("--target", help="Target season if the hindcast lacks a target_season attr.")
def seasonal_downscale(hindcast, obs, output, forecast=None, method="bcsd", output_type="tercile",
                       options=None, init_month=None, target=None, **kwargs):
    """Fit a downscaling method on the hindcast against the observations and issue one forecast.

    The output is not cross-validated: it is a forecast, labelled cross_validated=false, and
    seasonal-skill refuses it. For a scoreable hindcast use seasonal-calibrate --cv loyo or
    seasonal-outlook.
    """
    import africas2s

    opts = C.parse_options(options)
    hind = C.to_year_axis(hindcast)
    if "year" not in hind.dims:
        raise UsageError("--hindcast must hold several issuances (a hindcast on an init_time axis), not one forecast")
    o = C.to_year_axis(obs)
    month, season = season_of(hind, init_month, target)
    fc = None
    if forecast is not None:
        fc = C.to_year_axis(forecast)
        if "year" in fc.dims:
            raise UsageError("--forecast holds several issuances (an init_time axis); this skill issues one "
                             "forecast, so select one init_time first")
    year = int(fc.attrs["forecast_year"]) if fc is not None else int(hind["year"].max())
    call = dict(method=method, output_type=output_type, verbose=False, **opts)
    if fc is not None:
        call["forecast"] = fc
    try:
        result = africas2s.downscale(hind, o, **call)
    except (ValueError, KeyError, NotImplementedError, RuntimeError, TypeError) as exc:
        raise UsageError(f"{type(exc).__name__}: {exc}") from exc
    years = (int(hind["year"].min()), int(hind["year"].max()))
    if output_type == "tercile":
        out = C.terciles_to_variables(result, init_month=month, target=season, cross_validated=False,
                                      method=method, tercile_method="counting", hindcast_years=years,
                                      forecast_year=year)
    else:
        if result.attrs.get("units") is None and o.attrs.get("units") is not None:
            result = result.assign_attrs(units=o.attrs["units"])      # downscaled onto the predictand: its units
        out = C.predictor_to_standard(result, product=f"africas2s:downscale-{method}", variable=o.name,
                                      init_month=month, target=season, forecast_year=year)
    return C.stamp_versions(out)


if __name__ == "__main__":
    seasonal_downscale()
