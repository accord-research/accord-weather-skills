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
"""One-call ACCORD seasonal outlook: fetch the models and observations, run africas2s's multi-model pipeline with leave-year-out cross-validation, write the tercile forecast, the cross-validated hindcast and the map."""

from __future__ import annotations

import re
from pathlib import Path

from weather_skills_core import UsageError, weather_skill

import accord_contract as C

# Kept in lockstep with SKILL.md metadata.version.
_SKILL_VERSION = "0.1.0"

NMME_PRECIP_MODELS = ["nmme/ccsm4", "nmme/cfsv2", "nmme/geoss2s", "nmme/cansipsic4", "nmme/spear", "nmme/cesm1"]
METHODS = ["cca", "bcsd", "qm", "dqm", "delta", "climatology", "rank-analog"]
_INIT_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _models_failure(acmaddl, roster, variable, init, target, region, exc):
    """Name the models acmadDL cannot fetch for this issuance and suggest --models for the rest.

    ``acmaddl.assemble`` is all-or-nothing and its error ("no data for 2026-2026") does not
    say which model, so probe the roster one model at a time (cheap: the others are cached).
    """
    failed, ok = [], []
    for row in roster:
        try:
            acmaddl.assemble([row], variable, init=init, target=target, region=region, verbose=False)
            ok.append(row[1])
        except Exception as e:  # noqa: BLE001
            failed.append(f"{row[1]} ({type(e).__name__}: {e})")
    if not failed:
        return f"fetching the forecast models failed: {type(exc).__name__}: {exc}"
    msg = f"no data for {init} from {', '.join(failed)}."
    if ok:
        msg += " Rerun with the models that have data: " + " ".join(f"--models {p}" for p in ok)
    return msg


@weather_skill(name="seasonal-outlook", version=_SKILL_VERSION)
@weather_skill.argument("--init", required=True, help="Issuance month YYYY-MM, e.g. 2025-02.")
@weather_skill.argument("--target", required=True, help="Target season as month initials: MAM, JJAS, OND, ...")
@weather_skill.argument("--bbox", required=True, help="N/W/S/E in decimal degrees.")
@weather_skill.argument("--models", action="append",
                        help="acmadDL forecast product id; repeat for several. Default: the six NMME precipitation models.")
@weather_skill.argument("--predictand", default="obs/chirps-v3-monthly",
                        help="Observation product (default obs/chirps-v3-monthly rainfall; obs/era5 for temperature).")
@weather_skill.argument("-v", "--variable", choices=["precip", "temp"], default="precip", help="Variable to forecast.")
@weather_skill.argument("--hindcast", nargs=2, type=int, default=[1993, 2016], metavar=("FIRST", "LAST"),
                        help="Hindcast years, inclusive (default 1993 2016).")
@weather_skill.argument("--method", choices=METHODS, default="cca",
                        help="Downscaling method; cca is the PyCPT-style default, climatology the no-skill baseline.")
@weather_skill.argument("--cv-window", type=int, default=5, help="Years left out per cross-validation fold (5 matches PyCPT).")
@weather_skill.argument("--title", help="Map title; default built from the request.")
def seasonal_outlook(output, init, target, bbox, models=None, predictand="obs/chirps-v3-monthly", variable="precip",
                     hindcast=(1993, 2016), method="cca", cv_window=5, title=None, **kwargs):
    """ACMAD's standard seasonal workflow in one call. Three outputs, in this order:
    -o FORECAST.zarr (tercile probabilities for the issuance, with skill scores in attrs)
    -o HINDCAST.zarr (the leave-year-out cross-validated tercile hindcast seasonal-skill scores)
    -o MAP.png (the dominant-tercile map).
    """
    outputs = list(output) if isinstance(output, (list, tuple)) else [output]
    if len(outputs) != 3:
        raise UsageError("seasonal-outlook writes 3 outputs: pass -o FORECAST.zarr -o HINDCAST.zarr -o MAP.png "
                         f"(got {len(outputs)})")
    if not _INIT_RE.match(str(init)):
        raise UsageError(f"--init must be YYYY-MM, got {init!r}")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    import acmaddl
    import africas2s

    models = list(models) if models else list(NMME_PRECIP_MODELS)
    window = (int(hindcast[0]), int(hindcast[1]))
    region = C.bbox_to_region(bbox)
    roster = [(p.split("/")[-1], p, window) for p in models]
    try:
        tracks = acmaddl.assemble(roster, variable, init=init, target=target, region=region, verbose=False)
    except Exception as exc:  # noqa: BLE001
        raise UsageError(_models_failure(acmaddl, roster, variable, init, target, region, exc)) from exc
    try:
        obs_raw = acmaddl.fetch(predictand, variable, region=region, hindcast=window, target=target,
                                seasonal="mean", verbose=False, progress=False)
    except Exception as exc:  # noqa: BLE001
        raise UsageError(f"fetching the predictand failed: {type(exc).__name__}: {exc}") from exc
    obs = obs_raw[variable] if hasattr(obs_raw, "data_vars") else obs_raw

    # Forecast-year probabilities: pooled aggregation measures spread across models; under CCA
    # the library derives them from the regression error instead (CPT's Student-t path).
    aggregation = "cpt_per_model" if method == "cca" else "pooled"
    try:
        result = africas2s.seasonal_mme({variable: tracks}, obs, method=method, cv="loyo",
                                        cpt_args={"crossvalidation_window": int(cv_window)},
                                        probability_aggregation=aggregation, verbose=False)
    except Exception as exc:  # noqa: BLE001
        raise UsageError(f"seasonal_mme failed: {type(exc).__name__}: {exc}") from exc

    month = int(str(init)[5:7])
    year = int(result.metadata.get("forecast_year") or str(init)[:4])
    tercile_method = result.metadata.get("tercile_method")
    request = dict(models=list(models), predictand=str(predictand), variable=str(variable), init=str(init),
                   target=str(target), bbox=[float(x) for x in bbox])
    forecast = C.terciles_to_variables(result.tercile_forecast, init_month=month, target=target, cross_validated=False,
                                       method=method, tercile_method=tercile_method, hindcast_years=window,
                                       forecast_year=year)
    forecast.attrs.update(request)
    for key, value in result.skill_report.scores.items():
        try:
            forecast.attrs[f"score_{key}"] = float(value)
        except (TypeError, ValueError):
            continue
    cv = C.terciles_to_variables(result.tercile_cv, init_month=month, target=target, cross_validated=True,
                                 method=method, tercile_method=tercile_method, cv_window=int(cv_window),
                                 hindcast_years=window)
    cv.attrs.update(request)

    map_title = title or f"{target} {year} {variable} outlook ({method}, {len(models)} model{'s' if len(models) != 1 else ''})"
    africas2s.plot_terciles(result.tercile_forecast, title=map_title,
                            variable_kind="temp" if variable == "temp" else "precip")
    png = Path(outputs[2])
    plt.gcf().savefig(png, dpi=150, bbox_inches="tight")
    plt.close("all")
    return [C.stamp_versions(forecast), C.stamp_versions(cv), png]


if __name__ == "__main__":
    seasonal_outlook()
