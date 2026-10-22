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
"""Combine several tercile probability files into one multi-model ensemble with africas2s.ensemble."""

from __future__ import annotations

from weather_skills_core import Dataset, UsageError, weather_skill

import accord_contract as C

# Kept in lockstep with SKILL.md metadata.version.
_SKILL_VERSION = "0.1.0"


def _label(ds, i):
    src = str(ds.attrs.get("weather_skills_source", "")).split(":")[-1].split("/")[-1]
    return src or f"member{i + 1}"


@weather_skill(name="seasonal-ensemble", version=_SKILL_VERSION)
@weather_skill.argument("-i", "--input", type=Dataset("any"), action="append", required=True, dest="ds",
                        help="Tercile probability Zarrs to combine (seasonal-downscale/-calibrate/-outlook output). Repeat -i.")
@weather_skill.argument("--obs", type=Dataset("observations"), dest="obs",
                        help="Seasonal observations; needed for skill-based weighting and the error-variance diagnostic.")
@weather_skill.argument("--strategy", choices=["uniform", "skill_weighted", "bma", "drop_worst"], default="uniform",
                        help="How members are weighted (default uniform).")
@weather_skill.argument("--optimize-ensemble", action="store_true",
                        help="Fit the weights by cross-validated skill (needs --obs); falls back to uniform if the gate fails.")
@weather_skill.argument("--primary-metric", default="rpss", help="Metric used to weight members when optimizing.")
@weather_skill.argument("--options", help="JSON object of extra keyword arguments for africas2s.ensemble.")
def seasonal_ensemble(ds, output, obs=None, strategy="uniform", optimize_ensemble=False, primary_metric="rpss",
                      options=None, **kwargs):
    """Combine tercile probability files into one ensemble; the result is cross-validated only if every input is.

    skill_weighted and drop_worst score each member with africas2s.skill against --obs
    (cross-validated hindcasts only); uniform needs no observations.
    """
    import africas2s

    opts = C.parse_options(options)
    inputs = list(ds) if isinstance(ds, (list, tuple)) else [ds]
    for d in inputs:
        if not C.is_tercile_file(d):
            raise UsageError("version 1 combines tercile probability files (prob_below/prob_normal/prob_above); "
                             f"an input has {list(d.data_vars)}")
    forecasts = []
    names = []
    for i, d in enumerate(inputs):
        probs = C.variables_to_terciles(d)
        name = _label(d, i)
        name = name if name not in names else f"{name}_{i + 1}"
        probs.name = name
        names.append(name)
        forecasts.append(probs)
    _require_same_layout(forecasts)
    all_cv = all(d.attrs.get("cross_validated") is True for d in inputs)
    # Uniform weights fit nothing, so an ensemble of honest hindcasts is still honest. Skill-based
    # weights are fit on the same years the result would be scored on: label that in-sample.
    cross_validated = all_cv and strategy == "uniform"
    o = C.to_year_axis(obs) if obs is not None else None
    if strategy == "bma" or optimize_ensemble:
        raise UsageError("bma and --optimize-ensemble fit on continuous hindcasts, which africas2s.ensemble "
                         "cannot do from tercile files; version 1 offers uniform, skill_weighted and drop_worst")
    scores = None
    if strategy in ("skill_weighted", "drop_worst"):
        if obs is None:
            raise UsageError(f"--strategy {strategy} needs --obs to score the members")
        if not all_cv:
            raise UsageError(f"--strategy {strategy} scores the members, so every input must be a cross-validated "
                             f"hindcast (cross_validated=true); make them with {C.HONEST_SOURCES}")
        try:
            scores = [float(africas2s.skill(f, o, metrics=[primary_metric]).scores[primary_metric]) for f in forecasts]
        except (ValueError, KeyError, RuntimeError, TypeError) as exc:
            raise UsageError(f"scoring the members failed: {type(exc).__name__}: {exc}") from exc
        opts.setdefault("scores", scores)
    try:
        # obs is never handed to africas2s.ensemble: its diagnostics assume continuous forecasts.
        res = africas2s.ensemble(forecasts, None, strategy=strategy, **opts)
    except (ValueError, KeyError, NotImplementedError, RuntimeError, TypeError) as exc:
        raise UsageError(f"{type(exc).__name__}: {exc}") from exc
    first = forecasts[0]
    years = inputs[0].attrs.get("hindcast_years") or None
    out = C.terciles_to_variables(res.forecast, init_month=int(first.attrs["init_month"]), target=first.attrs["target_season"],
                                  cross_validated=cross_validated, method=f"ensemble:{strategy}",
                                  tercile_method="combined", hindcast_years=tuple(years) if years else None,
                                  forecast_year=first.attrs.get("forecast_year"))
    out.attrs.update(weights=[float(w) for w in res.weights], member_names=[str(n) for n in res.member_names],
                     effective_n=float(res.effective_n), gate_passed=bool(res.gate_passed),
                     members_cross_validated=[bool(d.attrs.get("cross_validated") is True) for d in inputs],
                     primary_metric=str(primary_metric), member_scores=scores if scores is not None else [],
                     weights_fit="none" if strategy == "uniform" else "in_sample")
    _shadow_inherited_attrs(out, inputs)
    if cross_validated and o is not None:
        try:
            own = float(africas2s.skill(res.forecast, o, metrics=[primary_metric]).scores[primary_metric])
        except (ValueError, KeyError, RuntimeError, TypeError):
            own = None
        if own is not None:
            out.attrs[f"score_{primary_metric}"] = own
            out.attrs["score_source"] = "ensemble"
    return C.stamp_versions(out)


def _require_same_layout(forecasts):
    """Members must share the time layout (all hindcasts over the same years, or all one issuance) and season."""
    first = forecasts[0]
    for f in forecasts[1:]:
        same_years = ("year" in first.dims) == ("year" in f.dims) and (
            "year" not in first.dims or list(first["year"].values) == list(f["year"].values))
        same_season = (first.attrs.get("target_season"), first.attrs.get("init_month")) == (
            f.attrs.get("target_season"), f.attrs.get("init_month"))
        if not (same_years and same_season):
            raise UsageError("all inputs must share the same time layout (all cross-validated hindcasts over the "
                             "same years, or all single issuances) and the same season; a hindcast cannot be "
                             "averaged with a forecast")


_REQUEST_KEYS = ("predictand", "variable", "init", "target", "bbox")


def _shadow_inherited_attrs(out, inputs):
    """The decorator copies the first input's attrs under ours; say what the ensemble is, not what member 1 was."""
    keys = []
    for d in inputs:
        keys.extend(k for k in d.attrs if k not in keys)
    for key in keys:
        if key in out.attrs:
            continue
        if key.startswith("score_"):
            out.attrs[key] = None                       # a member's score is not the ensemble's
        elif key == "models":
            union = []
            for d in inputs:
                union.extend(m for m in (d.attrs.get("models") or []) if m not in union)
            out.attrs["models"] = union
        elif key in _REQUEST_KEYS:
            values = [d.attrs.get(key) for d in inputs]
            out.attrs[key] = values[0] if all(v == values[0] for v in values) else None


if __name__ == "__main__":
    seasonal_ensemble()
