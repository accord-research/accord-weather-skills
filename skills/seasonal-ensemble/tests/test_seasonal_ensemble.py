"""seasonal-ensemble: africas2s.ensemble over tercile probability files."""

import numpy as np
import pytest
import xarray as xr
from helpers import load_skill, run_expecting_usage_error, run_skill
from weather_skills_core.provenance import load_history

import accord_contract as C


@pytest.fixture(scope="module")
def skill():
    return load_skill("seasonal-ensemble", "seasonal_ensemble").seasonal_ensemble


@pytest.fixture
def tercile_files(tmp_path, inputs):
    """Two cross-validated hindcasts and one forecast, from seasonal-calibrate."""
    cal = load_skill("seasonal-calibrate", "seasonal_calibrate").seasonal_calibrate
    paths = {k: str(tmp_path / f"{k}.zarr") for k in ("cv1", "cv2", "fc")}
    run_skill(cal, "--hindcast", inputs["hind"], "--obs", inputs["obs"], "--cv", "loyo", "-o", paths["cv1"])
    run_skill(cal, "--hindcast", inputs["hind"], "--obs", inputs["obs"], "--cv", "loyo", "--cv-window", "3", "-o", paths["cv2"])
    run_skill(cal, "--hindcast", inputs["hind"], "--obs", inputs["obs"], "--forecast", inputs["fc"],
              "--forecast-year", "2025", "-o", paths["fc"])
    return paths


def test_uniform_ensemble_of_two_cv_hindcasts(tmp_path, skill, tercile_files, inputs):
    out = tmp_path / "e.zarr"
    run_skill(skill, "-i", tercile_files["cv1"], "-i", tercile_files["cv2"], "--obs", inputs["obs"], "-o", str(out))
    ds = xr.open_zarr(out, consolidated=True)
    assert set(ds.data_vars) == set(C.PROB_VARS) and ds.sizes["init_time"] == 12
    assert ds.attrs["cross_validated"] is True and ds.attrs["method"] == "ensemble:uniform"
    assert list(ds.attrs["weights"]) == [0.5, 0.5] and len(ds.attrs["member_names"]) == 2
    total = sum(ds[v] for v in C.PROB_VARS).values
    np.testing.assert_allclose(total[np.isfinite(total)], 1.0, atol=1e-6)
    assert load_history(out)[-1]["skill"] == "seasonal-ensemble"


def test_ensemble_of_forecasts_is_not_cross_validated(tmp_path, skill, tercile_files):
    out = tmp_path / "e.zarr"
    run_skill(skill, "-i", tercile_files["fc"], "-i", tercile_files["fc"], "-o", str(out))
    ds = xr.open_zarr(out, consolidated=True)
    assert ds.attrs["cross_validated"] is False and "init_time" not in ds.dims


def test_ensemble_refuses_a_non_tercile_input(tmp_path, skill, tercile_files, inputs, capsys):
    run_expecting_usage_error(capsys, skill, "-i", tercile_files["cv1"], "-i", inputs["hind"],
                              "-o", str(tmp_path / "x.zarr"), match="tercile")


def test_skill_weighted_scores_cross_validated_members(tmp_path, skill, tercile_files, inputs):
    out = tmp_path / "e.zarr"
    run_skill(skill, "-i", tercile_files["cv1"], "-i", tercile_files["cv2"], "--obs", inputs["obs"],
              "--strategy", "skill_weighted", "-o", str(out))
    ds = xr.open_zarr(out, consolidated=True)
    weights = list(ds.attrs["weights"])
    assert len(weights) == 2 and sum(weights) == pytest.approx(1.0) and len(ds.attrs["member_scores"]) == 2
    assert ds.attrs["primary_metric"] == "rpss" and ds.attrs["method"] == "ensemble:skill_weighted"
    # The weights were fit on the same years the result would be scored on: not an honest hindcast.
    assert ds.attrs["cross_validated"] is False and ds.attrs["weights_fit"] == "in_sample"


def test_skill_weighted_refuses_members_that_are_not_cross_validated(tmp_path, skill, tercile_files, inputs, capsys):
    run_expecting_usage_error(capsys, skill, "-i", tercile_files["fc"], "-i", tercile_files["fc"], "--obs", inputs["obs"],
                              "--strategy", "skill_weighted", "-o", str(tmp_path / "x.zarr"), match="cross-validated")


def test_bma_and_optimize_are_refused_in_v1(tmp_path, skill, tercile_files, inputs, capsys):
    run_expecting_usage_error(capsys, skill, "-i", tercile_files["cv1"], "-i", tercile_files["cv2"], "--obs", inputs["obs"],
                              "--strategy", "bma", "-o", str(tmp_path / "x.zarr"), match="bma")
    run_expecting_usage_error(capsys, skill, "-i", tercile_files["cv1"], "-i", tercile_files["cv2"], "--obs", inputs["obs"],
                              "--optimize-ensemble", "-o", str(tmp_path / "x.zarr"), match="optimize")


def test_ensemble_does_not_inherit_a_members_skill_score_or_request(tmp_path, skill, tercile_files, inputs):
    """The decorator copies the first input's attrs under ours; a member's score must not become the ensemble's."""
    for path, model in ((tercile_files["cv1"], "nmme/ccsm4"), (tercile_files["cv2"], "nmme/cfsv2")):
        ds = xr.open_zarr(path, consolidated=True).load()
        ds.attrs.update(score_rpss=0.99, models=[model], init="2025-02", predictand="obs/chirps-v3-monthly")
        ds.to_zarr(path, mode="w", consolidated=True)
    out = tmp_path / "e.zarr"
    run_skill(skill, "-i", tercile_files["cv1"], "-i", tercile_files["cv2"], "--obs", inputs["obs"], "-o", str(out))
    ds = xr.open_zarr(out, consolidated=True)
    assert ds.attrs["models"] == ["nmme/ccsm4", "nmme/cfsv2"] and ds.attrs["init"] == "2025-02"
    assert ds.attrs["score_rpss"] != 0.99 and np.isfinite(ds.attrs["score_rpss"])   # the ensemble's own score
    assert ds.attrs["score_source"] == "ensemble"
    out2 = tmp_path / "e2.zarr"
    run_skill(skill, "-i", tercile_files["cv1"], "-i", tercile_files["cv2"], "-o", str(out2))   # no obs: no score
    assert xr.open_zarr(out2, consolidated=True).attrs.get("score_rpss") is None


def test_ensemble_refuses_mixing_a_hindcast_with_a_forecast(tmp_path, skill, tercile_files, capsys):
    run_expecting_usage_error(capsys, skill, "-i", tercile_files["cv1"], "-i", tercile_files["fc"],
                              "-o", str(tmp_path / "x.zarr"), match="same time layout")
