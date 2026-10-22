"""seasonal-skill: africas2s.skill on a cross-validated tercile hindcast; refuses anything else."""

import numpy as np
import pytest
import xarray as xr
from helpers import load_skill, run_expecting_usage_error, run_skill
from weather_skills_core.provenance import load_history


@pytest.fixture(scope="module")
def skill():
    return load_skill("seasonal-skill", "seasonal_skill").seasonal_skill


@pytest.fixture
def tercile_files(tmp_path, inputs):
    cal = load_skill("seasonal-calibrate", "seasonal_calibrate").seasonal_calibrate
    paths = {k: str(tmp_path / f"{k}.zarr") for k in ("cv", "fc")}
    run_skill(cal, "--hindcast", inputs["hind"], "--obs", inputs["obs"], "--cv", "loyo", "-o", paths["cv"])
    run_skill(cal, "--hindcast", inputs["hind"], "--obs", inputs["obs"], "--forecast", inputs["fc"],
              "--forecast-year", "2025", "-o", paths["fc"])
    return paths


def test_skill_scores_a_cv_hindcast(tmp_path, skill, tercile_files, inputs):
    out = tmp_path / "s.zarr"
    run_skill(skill, "--forecast", tercile_files["cv"], "--obs", inputs["obs"], "-o", str(out))
    ds = xr.open_zarr(out, consolidated=True)
    assert ds["rpss"].dims == ("lat", "lon") and ds["rpss"].attrs["units"] == "1"
    assert np.isfinite(ds.attrs["score_rpss"]) and ds.attrs["metrics"] == ["rpss"]
    assert ds.attrs["cross_validated"] is True and ds.attrs["forecast_method"] == "ereg"
    assert load_history(out)[-1]["skill"] == "seasonal-skill"


def test_skill_two_metrics(tmp_path, skill, tercile_files, inputs):
    out = tmp_path / "s.zarr"
    run_skill(skill, "--forecast", tercile_files["cv"], "--obs", inputs["obs"], "--metrics", "rpss",
              "--metrics", "roc", "-o", str(out))
    ds = xr.open_zarr(out, consolidated=True)
    assert ds.attrs["metrics"] == ["rpss", "roc"] and "score_rpss" in ds.attrs
    assert {"rpss", "roc_an", "roc_bn", "roc_nn"} <= set(ds.data_vars)


def test_skill_expands_a_preset(tmp_path, skill, tercile_files, inputs):
    out = tmp_path / "s.zarr"
    run_skill(skill, "--forecast", tercile_files["cv"], "--obs", inputs["obs"], "--metrics", "svslrf", "-o", str(out))
    ds = xr.open_zarr(out, consolidated=True)
    assert {"rpss", "roc_an"} <= set(ds.data_vars) and ds.attrs["metrics"][0] == "rpss"


def test_skill_refuses_a_forecast_that_is_not_cross_validated(tmp_path, skill, tercile_files, inputs, capsys):
    run_expecting_usage_error(capsys, skill, "--forecast", tercile_files["fc"], "--obs", inputs["obs"],
                              "-o", str(tmp_path / "x.zarr"),
                              match="seasonal-skill.*seasonal-calibrate --cv loyo or seasonal-outlook")


def test_skill_refuses_a_non_tercile_input(tmp_path, skill, inputs, capsys):
    run_expecting_usage_error(capsys, skill, "--forecast", inputs["hind"], "--obs", inputs["obs"],
                              "-o", str(tmp_path / "x.zarr"), match="tercile")
