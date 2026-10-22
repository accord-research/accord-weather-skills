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
"""Fetch one ACCORD seasonal product (hindcast, real-time forecast, or seasonal observations) as a weather-skills Zarr."""

from __future__ import annotations

import re
import sys

from weather_skills_core import UsageError, weather_skill

import accord_contract as C

# Kept in lockstep with SKILL.md metadata.version.
_SKILL_VERSION = "0.1.0"

_INIT_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _array(ds, variable):
    """acmadDL returns a Dataset; take the requested variable (or the only one)."""
    if not hasattr(ds, "data_vars"):
        return ds
    if variable in ds.data_vars:
        return ds[variable]
    names = list(ds.data_vars)
    if len(names) == 1:
        return ds[names[0]]
    raise UsageError(f"acmadDL returned {names}; none is {variable!r}")


@weather_skill(name="accord-fetch", version=_SKILL_VERSION)
@weather_skill.argument("--product", required=True,
                        help="acmadDL product id: nmme/* or c3s/* (forecast models), obs/* (observations).")
@weather_skill.argument("-v", "--variable", required=True, help="Catalog field: precip, temp or sst.")
@weather_skill.argument("--init", help="Issuance month YYYY-MM. Required for forecast models.")
@weather_skill.argument("--target", required=True, help="Target season as month initials: MAM, JJAS, OND, ...")
@weather_skill.argument("--bbox", help="N/W/S/E in decimal degrees. Default: the product's full domain.")
@weather_skill.argument("--hindcast", nargs=2, type=int, metavar=("FIRST", "LAST"),
                        help="Hindcast years, inclusive. Omit for a real-time forecast; required for obs/*.")
@weather_skill.argument("--grid-res", type=float,
                        help="Interpolate onto a regular lat/lon grid of this spacing (degrees) over --bbox, so a model "
                             "and its observations land on one grid for seasonal-calibrate.")
@weather_skill.argument("--probe-latest", nargs="?", const="", metavar="PRODUCT", probe=True,
                        help="Print the latest available issuance (YYYY-MM-DD or none) and exit; no -o.")
def accord_fetch(output, product, variable, init, target, bbox, hindcast, probe_latest, grid_res=None, **kwargs):
    """Fetch one ACCORD seasonal product as a weather-skills Zarr.

    A forecast model with --hindcast gives the multi-year hindcast (one init_time per
    year); without it the real-time forecast for --init; an obs/* product gives the
    seasonal mean per year as observations on a time axis.
    """
    if probe_latest is not None:
        print("none")
        print("accord-fetch: acmadDL has no issuance probe yet. Seasonal models are issued monthly; "
              "pass --init YYYY-MM and the fetch reports what is missing.", file=sys.stderr)
        return None

    import acmaddl

    region = C.bbox_to_region(bbox) if bbox else None
    window = (int(hindcast[0]), int(hindcast[1])) if hindcast else None
    common = dict(region=region, verbose=False, progress=False)
    if grid_res is not None:
        if region is None:
            raise UsageError("--grid-res needs --bbox (the grid spans the box)")
        common["grid_res"] = float(grid_res)
    try:
        if product.startswith("obs/"):
            if window is None:
                raise UsageError("observations need --hindcast FIRST LAST (the years to fetch)")
            raw = acmaddl.fetch(product, variable, hindcast=window, target=target, seasonal="mean", **common)
            out = C.obs_to_standard(_array(raw, variable), product=product, variable=variable, target=target)
        else:
            if not init:
                raise UsageError("forecast models need --init YYYY-MM (the issuance month)")
            if not _INIT_RE.match(str(init)):
                raise UsageError(f"--init must be YYYY-MM, got {init!r}")
            fetch_kwargs = dict(init=init, target=target, year_index=True, **common)
            if window is not None:
                fetch_kwargs["hindcast"] = window
            raw = acmaddl.fetch(product, variable, **fetch_kwargs)
            out = C.predictor_to_standard(_array(raw, variable), product=product, variable=variable,
                                          init_month=int(str(init)[5:7]), target=target)
    except UsageError:
        raise
    except (ValueError, KeyError, NotImplementedError, RuntimeError, OSError, ImportError) as exc:
        # acmadDL reports missing years, unreachable sources and absent credentials this way.
        raise UsageError(f"{type(exc).__name__}: {exc}") from exc
    return C.stamp_versions(out)


if __name__ == "__main__":
    accord_fetch()
