"""seasonal-outlook: the one-call recipe (fetch models + obs, seasonal_mme, map), acmadDL stubbed."""

import numpy as np
import pytest
import xarray as xr
from helpers import load_skill, run_expecting_usage_error, run_skill
from weather_skills_core.provenance import load_history

import accord_contract as C


@pytest.fixture(scope="module")
def skill():
    return load_skill("seasonal-outlook", "seasonal_outlook").seasonal_outlook


def test_outlook_writes_forecast_cv_hindcast_and_map(tmp_path, skill, fake_acmaddl):
    fc, cv, png = (str(tmp_path / n) for n in ("fc.zarr", "cv.zarr", "map.png"))
    run_skill(skill, "--init", "2025-02", "--target", "MAM", "--bbox", "5/34/-5/42", "--models", "nmme/ccsm4",
              "--models", "nmme/cfsv2", "--hindcast", "2001", "2012", "--method", "bcsd", "--cv-window", "1",
              "-o", fc, "-o", cv, "-o", png)
    f = xr.open_zarr(fc, consolidated=True)
    assert set(f.data_vars) == set(C.PROB_VARS) and f.attrs["cross_validated"] is False
    assert "init_time" not in f.dims and str(f["time"].values)[:10] == "2025-02-01"
    assert np.isfinite(f.attrs["score_rpss"]) and f.attrs["models"] == ["nmme/ccsm4", "nmme/cfsv2"]
    assert f.attrs["method"] == "bcsd" and list(f.attrs["hindcast_years"]) == [2001, 2012]
    c = xr.open_zarr(cv, consolidated=True)
    assert c.attrs["cross_validated"] is True and c.sizes["init_time"] == 12 and c.attrs["cv_window"] == 1
    assert open(png, "rb").read(4) == b"\x89PNG"
    assert load_history(fc)[-1]["skill"] == "seasonal-outlook"
    roster = fake_acmaddl["assemble"][-1]["roster"]
    assert [row[1] for row in roster] == ["nmme/ccsm4", "nmme/cfsv2"] and roster[0][2] == (2001, 2012)
    assert fake_acmaddl["assemble"][-1]["region"] == [-5.0, 5.0, 34.0, 42.0]
    obs_call = fake_acmaddl["fetch"][-1]
    assert obs_call["product"] == "obs/chirps-v3-monthly" and obs_call["seasonal"] == "mean"


def test_outlook_defaults_to_six_nmme_models(tmp_path, skill, fake_acmaddl):
    fc, cv, png = (str(tmp_path / n) for n in ("fc.zarr", "cv.zarr", "map.png"))
    run_skill(skill, "--init", "2025-02", "--target", "MAM", "--bbox", "5/34/-5/42", "--hindcast", "2001", "2012",
              "--method", "bcsd", "--cv-window", "1", "-o", fc, "-o", cv, "-o", png)
    assert len(fake_acmaddl["assemble"][-1]["roster"]) == 6


def test_outlook_needs_three_outputs(tmp_path, skill, fake_acmaddl, capsys):
    with pytest.raises(SystemExit):
        run_skill(skill, "--init", "2025-02", "--target", "MAM", "--bbox", "5/34/-5/42", "--hindcast", "2001", "2012",
                  "--method", "bcsd", "-o", str(tmp_path / "only.zarr"))
    assert "3" in capsys.readouterr().err


@pytest.mark.integration
def test_outlook_live_kenya_ond(tmp_path, skill):
    fc, cv, png = (str(tmp_path / n) for n in ("fc.zarr", "cv.zarr", "map.png"))
    run_skill(skill, "--init", "2025-09", "--target", "OND", "--bbox", "5/34/-5/42", "--models", "nmme/ccsm4",
              "--hindcast", "1993", "2016", "--method", "bcsd", "-o", fc, "-o", cv, "-o", png)
    assert open(png, "rb").read(4) == b"\x89PNG"
