"""Shared helpers and fixtures for the accord-weather-skills tests (re-exported by the root conftest.py).

Rhiza's pattern: import a skill script in-process and call its decorated
function with an argv list, so tests need no per-script environment.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = REPO_ROOT / "skills"
TOOLS_ROOT = REPO_ROOT / "tools"

YEARS = np.arange(2001, 2013)
MEMBERS = np.arange(4)
LAT = [-1.0, 0.0, 1.0]
LON = [36.0, 37.0, 38.0]


def load_skill(skill_dir_name: str, script_stem: str):
    """Import ``skills/<dir>/scripts/<stem>.py`` with its own directory on sys.path."""
    scripts_dir = SKILLS_ROOT / skill_dir_name / "scripts"
    path = scripts_dir / f"{script_stem}.py"
    if not path.is_file():
        raise FileNotFoundError(path)
    mod_name = f"skill_{skill_dir_name}_{script_stem}".replace("-", "_")
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load skill script: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(scripts_dir))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(scripts_dir))
    return module


def run_skill(fn, *argv: str):
    """Invoke a decorated skill with an argv list, in-process."""
    return fn(list(argv))


def write_zarr(ds, path) -> Path:
    ds.to_zarr(path, mode="w", consolidated=True)
    return Path(path)


def _signal(n_years: int) -> np.ndarray:
    pattern = np.outer(np.cos(np.array(LAT) * 0.8), np.sin(np.array(LON) * 0.3))
    return np.sin(np.arange(n_years) * 0.7)[:, None, None] * pattern[None]


@pytest.fixture
def year_hindcast() -> xr.DataArray:
    """(year, member, lat, lon) rainfall rate in mm/day, acmadDL's canonical hindcast."""
    rng = np.random.default_rng(0)
    data = _signal(len(YEARS))[:, None] + 0.3 * rng.normal(size=(len(YEARS), len(MEMBERS), 3, 3)) + 5.0
    return xr.DataArray(data, dims=("year", "member", "lat", "lon"),
                        coords={"year": YEARS, "member": MEMBERS, "lat": LAT, "lon": LON},
                        name="precip", attrs={"units": "mm/day"})


@pytest.fixture
def year_obs(year_hindcast) -> xr.DataArray:
    """(year, lat, lon) seasonal mean rainfall in mm/month, correlated with the hindcast."""
    rng = np.random.default_rng(1)
    data = 30.0 * 0.7 * year_hindcast.mean("member").values + 50.0 + 10.0 * rng.normal(size=(len(YEARS), 3, 3))
    return xr.DataArray(data, dims=("year", "lat", "lon"),
                        coords={"year": YEARS, "lat": LAT, "lon": LON},
                        name="precip", attrs={"units": "mm/month"})


@pytest.fixture
def year_forecast() -> xr.DataArray:
    """(year=[2025], member, lat, lon): acmadDL's canonical real-time forecast shape."""
    rng = np.random.default_rng(2)
    data = 5.0 + 0.3 * rng.normal(size=(1, len(MEMBERS), 3, 3))
    return xr.DataArray(data, dims=("year", "member", "lat", "lon"),
                        coords={"year": [2025], "member": MEMBERS, "lat": LAT, "lon": LON},
                        name="precip", attrs={"units": "mm/day"})


def tercile_cv(obs: xr.DataArray, seed: int = 3) -> xr.DataArray:
    """A cross-validated tercile hindcast (year, tercile, lat, lon) from noisy knowledge of obs."""
    from africas2s.tercile import to_tercile_cv

    rng = np.random.default_rng(seed)
    pred = (obs + rng.normal(0.0, 5.0, obs.shape)).assign_attrs(obs.attrs)
    return to_tercile_cv(pred, obs, method="bootstrap")


@pytest.fixture
def fake_acmaddl(monkeypatch, year_hindcast, year_obs, year_forecast) -> dict:
    """Stand in for acmaddl.fetch / acmaddl.assemble with the synthetic data; records calls."""
    import acmaddl

    calls = {"fetch": [], "assemble": []}

    def _fetch(product, variable, **kwargs):
        calls["fetch"].append({"product": product, "variable": variable, **kwargs})
        if product.startswith("obs/"):
            da = year_obs
        elif kwargs.get("hindcast") is not None:
            da = year_hindcast
        else:
            da = year_forecast
        return da.rename(variable).to_dataset()

    def _assemble(roster, variable, **kwargs):
        roster = list(roster)
        calls["assemble"].append({"roster": roster, "variable": variable, **kwargs})
        return {row[0]: (year_hindcast.rename(variable), year_forecast.rename(variable)) for row in roster}

    monkeypatch.setattr(acmaddl, "fetch", _fetch)
    monkeypatch.setattr(acmaddl, "assemble", _assemble)
    return calls


def run_expecting_usage_error(capsys, fn, *argv: str, match: str):
    """The decorator turns a UsageError into exit code 2 with ``Error: <message>`` on stderr."""
    import re

    with pytest.raises(SystemExit) as exc:
        fn(list(argv))
    assert exc.value.code == 2, exc.value.code
    err = capsys.readouterr().err
    assert re.search(match, err), err


@pytest.fixture
def inputs(tmp_path, fake_acmaddl) -> dict:
    """Hindcast, observations and a forecast Zarr written by accord-fetch over the stubbed acmadDL."""
    fetch = load_skill("accord-fetch", "accord_fetch").accord_fetch
    paths = {k: str(tmp_path / f"{k}.zarr") for k in ("hind", "obs", "fc")}
    run_skill(fetch, "--product", "nmme/ccsm4", "-v", "precip", "--init", "2025-02", "--target", "MAM",
              "--hindcast", "2001", "2012", "-o", paths["hind"])
    run_skill(fetch, "--product", "obs/chirps-v3-monthly", "-v", "precip", "--target", "MAM",
              "--hindcast", "2001", "2012", "-o", paths["obs"])
    run_skill(fetch, "--product", "nmme/ccsm4", "-v", "precip", "--init", "2025-02", "--target", "MAM", "-o", paths["fc"])
    return paths
