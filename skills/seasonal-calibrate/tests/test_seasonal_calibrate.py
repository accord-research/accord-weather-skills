"""seasonal-calibrate: africas2s.calibrate (ereg/logit/smoothed_regression), with and without leave-year-out CV."""

import numpy as np
import pytest
import xarray as xr
from helpers import load_skill, run_expecting_usage_error, run_skill
from weather_skills_core.provenance import load_history

import accord_contract as C


@pytest.fixture(scope="module")
def skill():
    return load_skill("seasonal-calibrate", "seasonal_calibrate").seasonal_calibrate


def _sums_to_one(ds):
    total = sum(ds[v] for v in C.PROB_VARS).values
    np.testing.assert_allclose(total[np.isfinite(total)], 1.0, atol=1e-6)


def test_calibrate_cv_writes_a_cross_validated_hindcast(tmp_path, skill, inputs):
    out = tmp_path / "c.zarr"
    run_skill(skill, "--hindcast", inputs["hind"], "--obs", inputs["obs"], "--cv", "loyo", "-o", str(out))
    ds = xr.open_zarr(out, consolidated=True)
    assert set(ds.data_vars) == set(C.PROB_VARS)
    assert ds.attrs["cross_validated"] is True and ds.attrs["cv_window"] == 1 and ds.attrs["method"] == "ereg"
    assert ds.sizes["init_time"] == 12 and list(ds.attrs["hindcast_years"]) == [2001, 2012]
    _sums_to_one(ds)
    assert load_history(out)[-1]["skill"] == "seasonal-calibrate"


def test_calibrate_forecast_writes_one_issuance(tmp_path, skill, inputs):
    out = tmp_path / "c.zarr"
    run_skill(skill, "--hindcast", inputs["hind"], "--obs", inputs["obs"], "--forecast", inputs["fc"],
              "--forecast-year", "2025", "-o", str(out))
    ds = xr.open_zarr(out, consolidated=True)
    assert "init_time" not in ds.dims and str(ds["time"].values)[:10] == "2025-02-01"
    assert ds.attrs["cross_validated"] is False and ds.attrs["cv_window"] == 0
    _sums_to_one(ds)


def test_calibrate_two_models_averages(tmp_path, skill, inputs):
    out = tmp_path / "c.zarr"
    run_skill(skill, "--hindcast", inputs["hind"], "--hindcast", inputs["hind"], "--obs", inputs["obs"],
              "--forecast", inputs["fc"], "--forecast", inputs["fc"], "--forecast-year", "2025", "-o", str(out))
    ds = xr.open_zarr(out, consolidated=True)
    assert set(ds.data_vars) == set(C.PROB_VARS) and "init_time" not in ds.dims
    _sums_to_one(ds)


def test_calibrate_without_forecast_or_cv_is_a_usage_error(tmp_path, skill, inputs, capsys):
    run_expecting_usage_error(capsys, skill, "--hindcast", inputs["hind"], "--obs", inputs["obs"],
                              "-o", str(tmp_path / "x.zarr"), match="--forecast.*--cv|--cv.*--forecast")


def test_calibrate_mismatched_forecast_count_is_a_usage_error(tmp_path, skill, inputs, capsys):
    run_expecting_usage_error(capsys, skill, "--hindcast", inputs["hind"], "--hindcast", inputs["hind"],
                              "--obs", inputs["obs"], "--forecast", inputs["fc"], "-o", str(tmp_path / "x.zarr"),
                              match="one --forecast per --hindcast")
