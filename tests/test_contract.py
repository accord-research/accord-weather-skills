"""Round-trip tests for tools/accord_contract.py (the source copy)."""

import numpy as np
import pytest
import xarray as xr
from helpers import tercile_cv  # noqa: F401  (used by later tests)
from weather_skills_core import UsageError

import accord_contract as C


def test_bbox_to_region_reorders_to_acmaddl():
    assert C.bbox_to_region((5.0, 34.0, -5.0, 42.0)) == [-5.0, 5.0, 34.0, 42.0]


@pytest.mark.parametrize("target,months", [("MAM", [3, 4, 5]), ("JJAS", [6, 7, 8, 9]), ("DJF", [12, 1, 2])])
def test_season_months(target, months):
    assert C.season_months(target) == months


@pytest.mark.parametrize("init_month,target,days",
                         [(2, "MAM", 28), (9, "OND", 30), (11, "DJF", 30), (12, "JFM", 31),
                          (3, "MAM", 0), (12, "DJF", 0)])      # an issuance in the season's first month is this season
def test_season_lead_days_wraps_forward(init_month, target, days):
    assert C.season_lead_days(init_month, target) == days


def test_predictor_to_standard_hindcast(year_hindcast):
    ds = C.predictor_to_standard(year_hindcast, product="nmme/ccsm4", variable="precip", init_month=2, target="MAM")
    assert dict(ds.sizes) == {"init_time": 12, "lead_time": 1, "member": 4, "lat": 3, "lon": 3}
    assert str(ds["init_time"].values[0])[:10] == "2001-02-01"
    assert ds["lead_time"].values[0] == np.timedelta64(28, "D")
    v = ds["precip"]
    assert v.attrs["units"] == "mm day-1"
    assert v.attrs["target_season"] == "MAM" and v.attrs["init_month"] == 2
    assert v.attrs["aggregation_period"] == "3 month" and v.attrs["cell_methods"] == "time: mean"
    assert ds.attrs["weather_skills_source"] == "acmaddl:nmme/ccsm4"
    assert "weather_skills_history" not in ds.attrs            # record=False: the decorator owns history


def test_predictor_to_standard_forecast_and_member_free_field(year_forecast):
    ds = C.predictor_to_standard(year_forecast, product="nmme/ccsm4", variable="precip", init_month=2, target="MAM")
    # One issuance is written the way Rhiza's own fetchers write it: scalar init ``time`` + a lead axis.
    assert "init_time" not in ds.dims and str(ds["time"].values)[:10] == "2025-02-01"
    assert dict(ds.sizes) == {"step": 1, "member": 4, "lat": 3, "lon": 3}     # "step" is their lead-axis spelling
    field = year_forecast.isel(year=0, drop=True).mean("member")          # (lat, lon), no year dim
    ds2 = C.predictor_to_standard(field, product="downscale:bcsd", variable="precip", init_month=2, target="MAM",
                                  forecast_year=2025)
    assert "init_time" not in ds2.dims and "member" not in ds2.dims and str(ds2["time"].values)[:10] == "2025-02-01"
    with pytest.raises(UsageError, match="forecast_year"):
        C.predictor_to_standard(field, product="x", variable="precip", init_month=2, target="MAM")


def test_to_year_axis_round_trips_hindcast_and_forecast(year_hindcast, year_forecast):
    hind = C.to_year_axis(C.predictor_to_standard(year_hindcast, product="p", variable="precip", init_month=2, target="MAM"))
    assert hind.dims == ("year", "member", "lat", "lon") and list(hind["year"].values) == list(range(2001, 2013))
    np.testing.assert_allclose(hind.values, year_hindcast.transpose("year", "member", "lat", "lon").values)
    assert hind.attrs["target_season"] == "MAM" and "forecast_year" not in hind.attrs
    fc = C.to_year_axis(C.predictor_to_standard(year_forecast, product="p", variable="precip", init_month=2, target="MAM"))
    assert fc.dims == ("member", "lat", "lon") and fc.attrs["forecast_year"] == 2025


def test_to_year_axis_accepts_a_rhiza_style_forecast():
    """Files from Rhiza's own fetchers: latitude/longitude, number, scalar time + step."""
    steps = np.array([np.timedelta64(28, "D")])
    da = xr.DataArray(np.ones((4, 1, 3, 3)), dims=("number", "step", "latitude", "longitude"),
                      coords={"number": range(4), "step": steps, "latitude": [-1.0, 0.0, 1.0],
                              "longitude": [36.0, 37.0, 38.0], "time": np.datetime64("2025-02-01", "ns")},
                      name="precip", attrs={"units": "mm day-1"})
    out = C.to_year_axis(da.to_dataset())
    assert set(out.dims) == {"member", "lat", "lon"} and out.attrs["forecast_year"] == 2025


def test_parse_options():
    assert C.parse_options(None) == {} and C.parse_options('{"n_modes": 3}') == {"n_modes": 3}
    with pytest.raises(UsageError, match="--options"):
        C.parse_options("[1, 2]")
    with pytest.raises(UsageError, match="--options"):
        C.parse_options("{not json")


# --- observations -----------------------------------------------------------

def test_obs_to_standard(year_obs):
    ds = C.obs_to_standard(year_obs, product="obs/chirps-v3-monthly", variable="precip", target="MAM")
    assert dict(ds.sizes) == {"time": 12, "lat": 3, "lon": 3}
    assert str(ds["time"].values[0])[:10] == "2001-03-01"
    assert ds["precip"].attrs["units"] == "mm month-1"
    assert ds["precip"].attrs["cell_methods"] == "time: mean" and ds["precip"].attrs["aggregation_period"] == "3 month"
    assert ds.attrs["weather_skills_source"] == "acmaddl:obs/chirps-v3-monthly"
    assert "weather_skills_history" not in ds.attrs


def test_obs_to_standard_wraparound_season_stamps_december(year_obs):
    ds = C.obs_to_standard(year_obs, product="p", variable="precip", target="DJF")
    assert str(ds["time"].values[0])[:10] == "2001-12-01"


def test_to_year_axis_round_trips_observations(year_obs):
    back = C.to_year_axis(C.obs_to_standard(year_obs, product="p", variable="precip", target="MAM"))
    assert back.dims == ("year", "lat", "lon") and list(back["year"].values) == list(range(2001, 2013))
    np.testing.assert_allclose(back.values, year_obs.values)


# --- tercile codec ----------------------------------------------------------

def test_terciles_round_trip_cv_hindcast(year_obs):
    probs = tercile_cv(year_obs)                                        # (year, tercile, lat, lon)
    ds = C.terciles_to_variables(probs, init_month=2, target="MAM", cross_validated=True, method="ereg",
                                 tercile_method="gaussian", cv_window=1, hindcast_years=(2001, 2012))
    assert set(ds.data_vars) == set(C.PROB_VARS) and C.is_tercile_file(ds)
    assert dict(ds["prob_above"].sizes) == {"init_time": 12, "lead_time": 1, "lat": 3, "lon": 3}
    assert ds["prob_above"].attrs["units"] == "1"
    total = sum(ds[v] for v in C.PROB_VARS)
    np.testing.assert_allclose(total.values[np.isfinite(total.values)], 1.0, atol=1e-9)
    assert ds.attrs["cross_validated"] is True and ds.attrs["method"] == "ereg" and ds.attrs["cv_window"] == 1
    assert list(ds.attrs["hindcast_years"]) == [2001, 2012]
    back = C.variables_to_terciles(ds)
    assert back.dims == ("year", "tercile", "lat", "lon") and list(back["tercile"].values) == [0, 1, 2]
    np.testing.assert_allclose(back.values, probs.transpose("year", "tercile", "lat", "lon").values)
    assert back.attrs["units"] == "1" and back.attrs["cross_validated"] is True and back.attrs["method"] == "ereg"


def test_terciles_round_trip_forecast_and_nan_cells(year_obs):
    probs = tercile_cv(year_obs).isel(year=-1, drop=True).copy()        # (tercile, lat, lon)
    probs[:, 0, 0] = np.nan                                             # a masked cell
    ds = C.terciles_to_variables(probs, init_month=2, target="MAM", cross_validated=False, method="bcsd",
                                 tercile_method="counting", forecast_year=2025)
    assert "init_time" not in ds.dims and str(ds["time"].values)[:10] == "2025-02-01"   # one issuance: scalar time + step
    assert ds.attrs["cross_validated"] is False and ds.attrs["cv_window"] == 0 and ds.attrs["tercile_method"] == "counting"
    assert np.isnan(ds["prob_below"].values[0, 0, 0])
    back = C.variables_to_terciles(ds)
    assert back.dims == ("tercile", "lat", "lon") and back.attrs["forecast_year"] == 2025
    assert np.isnan(back.values[:, 0, 0]).all()
    np.testing.assert_allclose(back.values[:, 1:, :], probs.values[:, 1:, :])


def test_require_cross_validated_names_the_honest_sources(year_obs):
    ds = C.terciles_to_variables(tercile_cv(year_obs).isel(year=-1, drop=True), init_month=2, target="MAM",
                                 cross_validated=False, method="bcsd", forecast_year=2025)
    with pytest.raises(UsageError, match="seasonal-skill.*seasonal-calibrate --cv loyo or seasonal-outlook"):
        C.require_cross_validated(ds, skill_name="seasonal-skill")
    assert not C.is_tercile_file(ds.drop_vars("prob_normal"))


# --- skill fields and version stamps ----------------------------------------

def test_skill_to_standard(year_obs):
    import africas2s

    report = africas2s.skill(tercile_cv(year_obs), year_obs, metrics=["rpss"], spatial=True)
    ds = C.skill_to_standard(report, metrics=["rpss"])
    assert ds["rpss"].dims == ("lat", "lon") and ds["rpss"].attrs["units"] == "1"
    assert isinstance(ds.attrs["score_rpss"], float) and ds.attrs["metrics"] == ["rpss"]


def test_stamp_versions(year_obs):
    ds = C.stamp_versions(year_obs.to_dataset())
    assert ds.attrs["acmaddl_version"] and ds.attrs["africas2s_version"] and ds.attrs["accord_contract_version"] == "1"


def test_to_year_axis_dequantifies_and_loads_decorator_style_inputs(year_hindcast):
    """The decorator hands skills pint-quantified, lazily chunked datasets; the verbs need plain arrays."""
    from weather_skills_core.units import quantify_dataset

    ds = C.predictor_to_standard(year_hindcast, product="p", variable="precip", init_month=2, target="MAM")
    ds = quantify_dataset(ds.chunk({"init_time": 4}))
    back = C.to_year_axis(ds)
    assert type(back.data).__module__.startswith("numpy"), type(back.data)
    assert back.attrs["units"] == "mm/day" and back.dims == ("year", "member", "lat", "lon")   # acmadDL's spelling, for the verbs
    assert float(back.isel(year=0, member=0, lat=0, lon=0)) == pytest.approx(float(year_hindcast[0, 0, 0, 0]))



# --- inputs the skills cannot represent must fail with a plain message (finding 9) ---

def test_to_year_axis_refuses_daily_observations():
    times = np.arange(np.datetime64("2001-03-01"), np.datetime64("2001-04-30")).astype("datetime64[ns]")
    ds = xr.DataArray(np.ones((len(times), 3, 3)), dims=("time", "lat", "lon"),
                      coords={"time": times, "lat": [-1.0, 0.0, 1.0], "lon": [36.0, 37.0, 38.0]},
                      name="precip", attrs={"units": "mm day-1"}).to_dataset()
    with pytest.raises(UsageError, match="one value per year"):
        C.to_year_axis(ds)


def test_to_year_axis_refuses_a_forecast_with_several_lead_steps():
    steps = np.array([np.timedelta64(d, "D") for d in (28, 59, 89)])
    da = xr.DataArray(np.ones((4, 3, 3, 3)), dims=("number", "step", "latitude", "longitude"),
                      coords={"number": range(4), "step": steps, "latitude": [-1.0, 0.0, 1.0],
                              "longitude": [36.0, 37.0, 38.0], "time": np.datetime64("2025-02-01", "ns")},
                      name="precip", attrs={"units": "mm day-1"})
    with pytest.raises(UsageError, match="several lead steps"):
        C.to_year_axis(da.to_dataset())


def test_to_year_axis_message_for_several_variables(year_obs):
    ds = C.obs_to_standard(year_obs, product="p", variable="precip", target="MAM")
    ds["temp"] = ds["precip"] * 0 + 20.0
    with pytest.raises(UsageError, match="one data variable") as exc:
        C.to_year_axis(ds)
    assert "--variable" not in str(exc.value)


def test_skill_to_standard_keeps_every_map_the_report_holds(year_obs):
    import africas2s

    report = africas2s.skill(tercile_cv(year_obs), year_obs, metrics=["rpss", "roc"], spatial=True)
    ds = C.skill_to_standard(report, metrics=["rpss", "roc"])
    assert {"rpss", "roc_an", "roc_bn", "roc_nn"} <= set(ds.data_vars)
    assert ds.attrs["metrics"] == ["rpss", "roc"] and "score_roc_an" in ds.attrs


def test_predictor_to_standard_labels_a_seasonal_total_as_a_sum(year_hindcast):
    # acmadDL returns NMME seasons as totals in mm ("Total precipitation"). Rhiza's
    # convert-to-totals tells an amount from a rate by units and cell_methods, so a
    # total labelled "time: mean" would be multiplied by the season again.
    total = year_hindcast.copy()
    total.attrs["units"] = "mm"
    ds = C.predictor_to_standard(total, product="nmme/ccsm4", variable="precip", init_month=9, target="OND")
    v = ds["precip"]
    assert v.attrs["units"] == "mm"
    assert v.attrs["cell_methods"] == "time: sum"
    assert v.attrs["aggregation_period"] == "3 month"


def test_tercile_variables_carry_no_cell_methods(year_obs):
    ds = C.terciles_to_variables(tercile_cv(year_obs), init_month=2, target="MAM", cross_validated=True, method="ereg")
    for name in C.PROB_VARS:
        assert "cell_methods" not in ds[name].attrs, name
        assert ds[name].attrs["aggregation_period"] == "3 month"
        assert ds[name].attrs["target_season"] == "MAM"
