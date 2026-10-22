"""Translation between ACCORD's shapes and the weather-skills standard dataset.

This module is the single source of truth, kept in ``tools/``; ``tools/sync_contract.py``
copies it verbatim beside every skill script as ``skills/<name>/scripts/accord_contract.py``
(uv puts a script's own directory on ``sys.path``, so ``import accord_contract`` resolves
there). Edit this file only; a test fails when a copy drifts.
"""

from __future__ import annotations

import datetime as _dt
import json

import numpy as np
import xarray as xr
from weather_skills_core import UsageError

CONTRACT_VERSION = "1"




PROB_VARS = ("prob_below", "prob_normal", "prob_above")
HONEST_SOURCES = "seasonal-calibrate --cv loyo or seasonal-outlook"
_REFERENCE_YEAR = 2001          # non-leap: lead days are nominal, target_season is authoritative
_UNIT_SPELLINGS = {"mm/day": "mm day-1", "mm/month": "mm month-1", "mm/hour": "mm hour-1",
                   "mm/pentad": "mm pentad-1", "mm/dekad": "mm dekad-1"}


# --- bbox and seasons -------------------------------------------------------

def bbox_to_region(bbox):
    """Rhiza's ``(N, W, S, E)`` → acmadDL's ``[lat_s, lat_n, lon_w, lon_e]``."""
    n, w, s, e = (float(x) for x in bbox)
    return [s, n, w, e]


def season_months(target):
    """``"MAM"`` → ``[3, 4, 5]``; wraps through December (``"DJF"`` → ``[12, 1, 2]``)."""
    from acmaddl import season_to_months

    start, end = season_to_months(target)
    months = [int(start)]
    while months[-1] != int(end):
        months.append(months[-1] % 12 + 1)
    return months


def season_lead_days(init_month, target):
    """Days from the first of ``init_month`` to the first day of ``target``'s first month.

    Computed in a non-leap reference year. An issuance in the season's first month
    is this season (lead 0; acmadDL counts the issuance month as lead 1); a season
    starting before the issuance month is next year's.
    """
    first = season_months(target)[0]
    init_month = int(init_month)
    start = _dt.date(_REFERENCE_YEAR, init_month, 1)
    year = _REFERENCE_YEAR if first >= init_month else _REFERENCE_YEAR + 1
    return (_dt.date(year, first, 1) - start).days


def _pint_spelling(units):
    if units is None:
        return None
    text = str(units).strip()
    if text in _UNIT_SPELLINGS:
        return _UNIT_SPELLINGS[text]
    if text.count("/") == 1:
        num, den = (p.strip() for p in text.split("/"))
        return f"{num} {den}-1"
    return text


def _season_attrs(target, init_month=None):
    attrs = {"target_season": str(target),
             "aggregation_period": f"{len(season_months(target))} month",
             "cell_methods": "time: mean"}
    if init_month is not None:
        attrs["init_month"] = int(init_month)
    return attrs


# --- predictors: year axis <-> init_time axis --------------------------------

def predictor_to_standard(da, *, product, variable, init_month, target, forecast_year=None):
    """ACCORD ``(year, [member,] lat, lon)`` → a standard forecast dataset.

    Each year becomes an ``init_time`` at the first of ``init_month``; one
    ``lead_time`` carries the nominal offset to the target season. A field with
    no ``year`` axis is one forecast and needs ``forecast_year``.
    """
    from acmaddl.weather_skills import to_standard_dataset

    if da.name != variable:
        da = da.rename(variable)
    if "year" not in da.dims:
        if forecast_year is None:
            raise UsageError("a field without a year axis is one forecast: pass forecast_year= "
                             "(the year it is for)")
        da = da.expand_dims(year=[int(forecast_year)])
    source = product if ":" in product else f"acmaddl:{product}"   # "africas2s:ereg" names a derived product
    ds = to_standard_dataset(da, name=variable, source=source, init_month=int(init_month),
                             lead=f"{season_lead_days(init_month, target)} days", record=False)
    ds.attrs.setdefault("weather_skills_source", source)
    ds.attrs.pop("weather_skills_history", None)       # the decorator owns the chain; never ship an empty one
    v = ds[variable]
    if v.attrs.get("units") is not None:
        v.attrs["units"] = _pint_spelling(v.attrs["units"])
    v.attrs.update(_season_attrs(target, init_month))
    return ds


def obs_to_standard(da, *, product, variable, target):
    """ACCORD ``(year, lat, lon)`` seasonal observations → a standard observations dataset.

    Each year becomes one ``time`` step at the first day of the target season's
    first month; the value stays the seasonal mean rate acmadDL returns, labelled
    ``cell_methods: time: mean`` with the season's ``aggregation_period``.
    """
    from acmaddl.weather_skills import to_standard_dataset

    if da.name != variable:
        da = da.rename(variable)
    if "year" not in da.dims:
        raise UsageError("observations need a year axis: (year, lat, lon) seasonal values")
    first = season_months(target)[0]
    times = np.array([np.datetime64(f"{int(y)}-{first:02d}-01", "ns") for y in da["year"].values])
    da = da.assign_coords(year=times).rename({"year": "time"})
    ds = to_standard_dataset(da, name=variable, source=f"acmaddl:{product}", record=False)
    ds.attrs.setdefault("weather_skills_source", f"acmaddl:{product}")
    ds.attrs.pop("weather_skills_history", None)
    v = ds[variable]
    if v.attrs.get("units") is not None:
        v.attrs["units"] = _pint_spelling(v.attrs["units"])
    v.attrs.update(_season_attrs(target))
    return ds


def _pick_variable(ds, variable):
    names = [v for v in ds.data_vars if v not in PROB_VARS]
    if variable is not None:
        if variable not in ds.data_vars:
            raise UsageError(f"no variable {variable!r} in the input; it has {list(ds.data_vars)}")
        return variable
    if len(names) != 1:
        raise UsageError(f"the input holds {len(names)} data variables {names}; this skill needs one data variable "
                         "(a file written by accord-fetch or another accord skill)")
    return names[0]


def to_year_axis(ds, variable=None):
    """A standard dataset → the ACCORD DataArray the verbs take.

    ``init_time`` (or ``time`` for observations) becomes ``year``; a single lead is
    squeezed; a single issuance is squeezed into ``attrs["forecast_year"]``. Rhiza's
    spellings (``latitude``, ``number``, scalar ``time`` + ``step``) are accepted.
    """
    from acmaddl.weather_skills import from_standard_dataset
    from weather_skills_core.units import dequantify_dataset

    if isinstance(ds, xr.DataArray):
        ds = ds.to_dataset(name=ds.name or variable or "data")
    # The decorator opens inputs pint-quantified and lazily chunked; the verbs want
    # plain in-memory arrays with units as strings.
    ds = dequantify_dataset(ds).load()
    ds = from_standard_dataset(ds)
    name = _pick_variable(ds, variable)
    da = ds[name]
    attrs = dict(da.attrs)
    for lead in ("lead_time", "step", "prediction_timedelta"):
        if lead in da.dims:
            if da.sizes[lead] != 1:
                raise UsageError(f"the forecast has several lead steps ({da.sizes[lead]}); this skill takes one "
                                 "seasonal value per issuance: reduce the lead axis to the season first "
                                 "(Rhiza's aggregate-temporal), or fetch the season with accord-fetch")
            da = da.squeeze(lead, drop=True)
    time_dim = "init_time" if "init_time" in da.dims else ("time" if "time" in da.dims else None)
    if time_dim is not None:
        years = da[time_dim].dt.year.values
        if len(set(years.tolist())) != len(years):
            raise UsageError(f"the input is not one value per year ({len(years)} steps over "
                             f"{len(set(years.tolist()))} distinct years); this skill takes seasonal values, one per "
                             "year: fetch them with accord-fetch, or aggregate the season first")
        da = da.assign_coords({time_dim: years}).rename({time_dim: "year"})
    for coord in list(da.coords):
        if coord not in da.dims:
            da = da.drop_vars(coord)
    if "year" in da.dims:
        da = da.assign_coords(year=da["year"].values.astype(int))
        if da.sizes["year"] == 1:
            attrs["forecast_year"] = int(da["year"].values[0])
            da = da.squeeze("year", drop=True)
    front = [d for d in ("year", "member", "lat", "lon") if d in da.dims]
    da = da.transpose(*front, *[d for d in da.dims if d not in front])
    da.attrs = attrs
    da.name = name
    return da


# --- tercile probabilities: a tercile dim <-> three variables ---------------

_LONG_NAMES = {"prob_below": "probability of below-normal", "prob_normal": "probability of near-normal",
               "prob_above": "probability of above-normal"}


def is_tercile_file(ds):
    return all(v in ds.data_vars for v in PROB_VARS)


def terciles_to_variables(probs, *, init_month, target, cross_validated, method, tercile_method=None,
                          cv_window=None, hindcast_years=None, forecast_year=None):
    """``(year, tercile, lat, lon)`` or ``(tercile, lat, lon)`` → ``prob_below``/``prob_normal``/``prob_above``.

    Each variable is ``units="1"``; the dataset says how the probabilities were made and
    whether they are cross-validated, which is what ``seasonal-skill`` checks.
    """
    if "tercile" not in probs.dims:
        raise UsageError("expected a tercile dimension (below/normal/above)")
    if probs.sizes["tercile"] != 3:
        raise UsageError(f"expected 3 terciles, got {probs.sizes['tercile']}")
    kept = {k: v for k, v in probs.attrs.items() if k not in ("units", "long_name", "standard_name")}
    parts = []
    for k, name in enumerate(PROB_VARS):
        slab = probs.isel(tercile=k, drop=True).rename(name)
        slab.attrs = {**kept, "units": "1"}      # their classifier reads "prob_*" as a precip kind and wants units
        part = predictor_to_standard(slab, product=f"africas2s:{method}", variable=name, init_month=init_month,
                                     target=target, forecast_year=forecast_year)
        part[name].attrs["units"] = "1"
        part[name].attrs["long_name"] = _LONG_NAMES[name]
        parts.append(part)
    ds = xr.merge(parts, combine_attrs="override")
    ds.attrs = {
        "weather_skills_source": f"africas2s:{method}",
        "cross_validated": bool(cross_validated),
        "method": str(method),
        "tercile_method": str(tercile_method) if tercile_method else "none",
        "cv_window": int(cv_window) if cv_window else 0,
        "hindcast_years": [int(hindcast_years[0]), int(hindcast_years[1])] if hindcast_years else [],
    }
    return ds


def variables_to_terciles(ds):
    """The inverse of :func:`terciles_to_variables`: back to a ``tercile`` dimension.

    ``(year, tercile, lat, lon)`` for a cross-validated hindcast; ``(tercile, lat, lon)``
    with ``attrs["forecast_year"]`` for one issuance.
    """
    if not is_tercile_file(ds):
        raise UsageError(f"not a tercile probability file: it needs the variables {list(PROB_VARS)}; "
                         f"it has {list(ds.data_vars)}")
    slabs = [to_year_axis(ds, variable=name) for name in PROB_VARS]
    first = slabs[0]
    out = xr.concat([s.drop_attrs() if hasattr(s, "drop_attrs") else s for s in slabs], dim="tercile")
    out = out.assign_coords(tercile=[0, 1, 2])
    front = [d for d in ("year", "tercile", "lat", "lon") if d in out.dims]
    out = out.transpose(*front, *[d for d in out.dims if d not in front])
    attrs = {"units": "1", "long_name": "tercile probability",
             "method": ds.attrs.get("method"), "tercile_method": ds.attrs.get("tercile_method"),
             "cross_validated": bool(ds.attrs.get("cross_validated", False))}
    for key in ("target_season", "init_month", "forecast_year"):
        if key in first.attrs:
            attrs[key] = first.attrs[key]
    out.attrs = attrs
    out.name = "probability"
    return out


def require_cross_validated(ds, *, skill_name):
    """Refuse a probability file that is not a cross-validated hindcast."""
    flag = ds.attrs.get("cross_validated")
    if flag is not True:
        raise UsageError(f"{skill_name} scores cross-validated hindcasts only; this file is not one "
                         f"(cross_validated={flag!r}). Make one with {HONEST_SOURCES}.")


# --- skill scores and version stamps ----------------------------------------

def skill_to_standard(report, *, metrics):
    """A SkillReport → one ``(lat, lon)`` variable per metric that has a map, scores as attrs."""
    data = {}
    for name, field in report.spatial.items():          # a metric may expand (roc -> roc_an/roc_bn/roc_nn)
        da = field if isinstance(field, xr.DataArray) else xr.DataArray(field)
        if {"lat", "lon"} <= set(da.dims):
            da = da.transpose("lat", "lon", ...)
        da = da.copy()
        da.attrs = {"units": "1", "long_name": f"{name} skill"}
        data[str(name)] = da
    ds = xr.Dataset(data)
    attrs = {"metrics": [str(m) for m in metrics]}
    for key, value in report.scores.items():
        try:
            attrs[f"score_{key}"] = float(value)
        except (TypeError, ValueError):
            attrs[f"score_{key}"] = str(value)
    ds.attrs = attrs
    return ds


def stamp_versions(ds):
    """Record which library versions produced the file."""
    import importlib.metadata as _meta

    ds.attrs["acmaddl_version"] = _meta.version("acmadDL")
    ds.attrs["africas2s_version"] = _meta.version("africas2s")
    ds.attrs["accord_contract_version"] = CONTRACT_VERSION
    return ds


# --- options ----------------------------------------------------------------

def parse_options(text):
    """``--options`` JSON object → kwargs for the verb; anything else is a UsageError."""
    if text is None or str(text).strip() == "":
        return {}
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise UsageError(f"--options must be a JSON object: {exc}") from exc
    if not isinstance(value, dict):
        raise UsageError('--options must be a JSON object, e.g. \'{"n_modes": 3}\'')
    return value
