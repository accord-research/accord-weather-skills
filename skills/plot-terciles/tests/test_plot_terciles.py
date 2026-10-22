"""plot-terciles: africas2s's dominant-tercile map as a PNG with provenance."""

import pytest
from helpers import load_skill, run_expecting_usage_error, run_skill
from weather_skills_core.provenance import load_figure_history


@pytest.fixture(scope="module")
def skill():
    return load_skill("plot-terciles", "plot_terciles").plot_terciles


@pytest.fixture
def tercile_files(tmp_path, inputs):
    cal = load_skill("seasonal-calibrate", "seasonal_calibrate").seasonal_calibrate
    paths = {k: str(tmp_path / f"{k}.zarr") for k in ("cv", "fc")}
    run_skill(cal, "--hindcast", inputs["hind"], "--obs", inputs["obs"], "--cv", "loyo", "-o", paths["cv"])
    run_skill(cal, "--hindcast", inputs["hind"], "--obs", inputs["obs"], "--forecast", inputs["fc"],
              "--forecast-year", "2025", "-o", paths["fc"])
    return paths


def test_plot_writes_png_with_provenance(tmp_path, skill, tercile_files):
    out = tmp_path / "map.png"
    run_skill(skill, "-i", tercile_files["fc"], "--title", "MAM 2025 rainfall", "-o", str(out))
    assert out.read_bytes()[:4] == b"\x89PNG"
    assert load_figure_history(out)[-1]["skill"] == "plot-terciles"


def test_plot_named_style_and_temperature_convention(tmp_path, skill, tercile_files):
    out = tmp_path / "map.png"
    run_skill(skill, "-i", tercile_files["fc"], "--style", "icpac", "--variable-kind", "temp", "-o", str(out))
    assert out.read_bytes()[:4] == b"\x89PNG"


def test_plot_refuses_a_multi_year_file(tmp_path, skill, tercile_files, capsys):
    run_expecting_usage_error(capsys, skill, "-i", tercile_files["cv"], "-o", str(tmp_path / "x.png"),
                              match="one issuance.*init_time")


def test_plot_refuses_a_non_tercile_input(tmp_path, skill, inputs, capsys):
    run_expecting_usage_error(capsys, skill, "-i", inputs["hind"], "-o", str(tmp_path / "x.png"), match="tercile")
