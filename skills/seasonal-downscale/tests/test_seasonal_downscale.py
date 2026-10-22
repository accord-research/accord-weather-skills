"""seasonal-downscale: africas2s.downscale over standard-dataset inputs (not cross-validated)."""

import pytest
import xarray as xr
from helpers import load_skill, run_expecting_usage_error, run_skill
from weather_skills_core.provenance import load_history

import accord_contract as C


@pytest.fixture(scope="module")
def skill():
    return load_skill("seasonal-downscale", "seasonal_downscale").seasonal_downscale


def test_downscale_tercile_output_is_not_cross_validated(tmp_path, skill, inputs):
    out = tmp_path / "d.zarr"
    run_skill(skill, "--hindcast", inputs["hind"], "--obs", inputs["obs"], "--method", "bcsd", "-o", str(out))
    ds = xr.open_zarr(out, consolidated=True)
    assert set(ds.data_vars) == set(C.PROB_VARS) and ds.attrs["cross_validated"] is False
    assert ds.attrs["method"] == "bcsd" and ds.attrs["tercile_method"] == "counting"
    assert "init_time" not in ds.dims and str(ds["time"].values)[:4] == "2012"     # last hindcast year, no --forecast
    history = load_history(out)
    assert history[-1]["skill"] == "seasonal-downscale" and len(history[-1]["input"]) == 2   # a two-input join


def test_downscale_with_forecast_file_predicts_that_year(tmp_path, skill, inputs):
    out = tmp_path / "d.zarr"
    run_skill(skill, "--hindcast", inputs["hind"], "--obs", inputs["obs"], "--forecast", inputs["fc"],
              "--method", "bcsd", "-o", str(out))
    ds = xr.open_zarr(out, consolidated=True)
    assert str(ds["time"].values)[:10] == "2025-02-01"
    assert len(load_history(out)[-1]["input"]) == 3


def test_downscale_continuous_output(tmp_path, skill, inputs):
    out = tmp_path / "d.zarr"
    run_skill(skill, "--hindcast", inputs["hind"], "--obs", inputs["obs"], "--forecast", inputs["fc"],
              "--method", "bcsd", "--output-type", "continuous", "-o", str(out))
    ds = xr.open_zarr(out, consolidated=True)
    assert list(ds.data_vars) == ["precip"] and dict(ds.sizes) == {"step": 1, "member": 4, "lat": 3, "lon": 3}
    assert ds["precip"].attrs["target_season"] == "MAM"


def test_downscale_refuses_a_forecast_with_several_issuances(tmp_path, skill, inputs, capsys):
    run_expecting_usage_error(capsys, skill, "--hindcast", inputs["hind"], "--obs", inputs["obs"],
                              "--forecast", inputs["hind"], "-o", str(tmp_path / "x.zarr"),
                              match="--forecast.*init_time")


def test_downscale_bad_options_is_a_usage_error(tmp_path, skill, inputs, capsys):
    run_expecting_usage_error(capsys, skill, "--hindcast", inputs["hind"], "--obs", inputs["obs"],
                              "--options", "[1]", "-o", str(tmp_path / "x.zarr"), match="--options")
