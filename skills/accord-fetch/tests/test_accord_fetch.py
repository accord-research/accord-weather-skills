"""accord-fetch: acmadDL's seasonal products as weather-skills Zarrs (acmadDL stubbed)."""

import pytest
import xarray as xr
from helpers import load_skill, run_expecting_usage_error, run_skill
from weather_skills_core.provenance import load_history


@pytest.fixture(scope="module")
def skill():
    return load_skill("accord-fetch", "accord_fetch").accord_fetch


def test_hindcast_fetch_writes_a_standard_forecast_zarr(tmp_path, skill, fake_acmaddl):
    out = tmp_path / "h.zarr"
    run_skill(skill, "--product", "nmme/ccsm4", "-v", "precip", "--init", "2025-02", "--target", "MAM",
              "--bbox", "5/34/-5/42", "--hindcast", "2001", "2012", "-o", str(out))
    ds = xr.open_zarr(out, consolidated=True)
    assert dict(ds.sizes) == {"init_time": 12, "lead_time": 1, "member": 4, "lat": 3, "lon": 3}
    assert ds.attrs["weather_skills_source"] == "acmaddl:nmme/ccsm4" and ds.attrs["acmaddl_version"]
    assert ds["precip"].attrs["units"] == "mm day-1" and ds["precip"].attrs["init_month"] == 2
    history = load_history(out)
    assert len(history) == 1 and history[-1]["skill"] == "accord-fetch"
    call = fake_acmaddl["fetch"][-1]
    assert call["region"] == [-5.0, 5.0, 34.0, 42.0] and call["hindcast"] == (2001, 2012)
    assert call["init"] == "2025-02" and call["target"] == "MAM" and call["year_index"] is True


def test_forecast_fetch_is_one_issuance(tmp_path, skill, fake_acmaddl):
    out = tmp_path / "f.zarr"
    run_skill(skill, "--product", "nmme/ccsm4", "-v", "precip", "--init", "2025-02", "--target", "MAM", "-o", str(out))
    ds = xr.open_zarr(out, consolidated=True)
    assert "init_time" not in ds.dims and str(ds["time"].values)[:10] == "2025-02-01"
    assert dict(ds.sizes) == {"step": 1, "member": 4, "lat": 3, "lon": 3}
    assert "hindcast" not in fake_acmaddl["fetch"][-1]


def test_obs_fetch_writes_observations(tmp_path, skill, fake_acmaddl):
    out = tmp_path / "o.zarr"
    run_skill(skill, "--product", "obs/chirps-v3-monthly", "-v", "precip", "--target", "MAM",
              "--hindcast", "2001", "2012", "-o", str(out))
    ds = xr.open_zarr(out, consolidated=True)
    assert dict(ds.sizes) == {"time": 12, "lat": 3, "lon": 3} and str(ds["time"].values[0])[:10] == "2001-03-01"
    assert ds["precip"].attrs["units"] == "mm month-1"
    call = fake_acmaddl["fetch"][-1]
    assert call["seasonal"] == "mean" and call["hindcast"] == (2001, 2012) and "init" not in call


def test_obs_without_hindcast_is_a_usage_error(tmp_path, skill, fake_acmaddl, capsys):
    run_expecting_usage_error(capsys, skill, "--product", "obs/chirps-v3-monthly", "-v", "precip", "--target", "MAM",
                              "-o", str(tmp_path / "o.zarr"), match="--hindcast")


def test_forecast_without_init_is_a_usage_error(tmp_path, skill, fake_acmaddl, capsys):
    run_expecting_usage_error(capsys, skill, "--product", "nmme/ccsm4", "-v", "precip", "--target", "MAM",
                              "-o", str(tmp_path / "f.zarr"), match="--init")


def test_probe_latest_prints_none(skill, capsys):
    run_skill(skill, "--product", "nmme/ccsm4", "-v", "precip", "--target", "MAM", "--probe-latest")
    assert capsys.readouterr().out.strip() == "none"


def test_acmaddl_availability_errors_reach_the_user_as_a_message(tmp_path, skill, monkeypatch, capsys):
    import acmaddl

    def _fetch(product, variable, **kwargs):
        raise RuntimeError(f"no data in 2001-2012 for {product}")

    monkeypatch.setattr(acmaddl, "fetch", _fetch)
    run_expecting_usage_error(capsys, skill, "--product", "nmme/ccsm4", "-v", "precip", "--init", "2025-02",
                              "--target", "MAM", "--hindcast", "2001", "2012", "-o", str(tmp_path / "h.zarr"),
                              match="no data in 2001-2012")


def test_grid_res_is_passed_to_acmaddl_and_needs_a_bbox(tmp_path, skill, fake_acmaddl, capsys):
    run_skill(skill, "--product", "obs/chirps-v3-monthly", "-v", "precip", "--target", "MAM", "--hindcast", "2001", "2012",
              "--bbox", "5/34/-5/42", "--grid-res", "1", "-o", str(tmp_path / "o.zarr"))
    assert fake_acmaddl["fetch"][-1]["grid_res"] == 1.0
    run_expecting_usage_error(capsys, skill, "--product", "obs/chirps-v3-monthly", "-v", "precip", "--target", "MAM",
                              "--hindcast", "2001", "2012", "--grid-res", "1", "-o", str(tmp_path / "o2.zarr"),
                              match="--grid-res needs --bbox")
