"""Repo-level consistency: every skill carries an identical copy of the contract module."""

from helpers import SKILLS_ROOT, TOOLS_ROOT


def _skill_dirs():
    return sorted(p for p in SKILLS_ROOT.iterdir() if (p / "SKILL.md").is_file())


def test_every_skill_has_an_identical_contract_copy():
    src = (TOOLS_ROOT / "accord_contract.py").read_text()
    skill_dirs = _skill_dirs()
    assert skill_dirs, "no skills yet"
    for d in skill_dirs:
        assert (d / "scripts" / "accord_contract.py").read_text() == src, d.name


def test_one_script_per_skill():
    for d in _skill_dirs():
        scripts = [p for p in (d / "scripts").glob("*.py") if p.name != "accord_contract.py"]
        assert len(scripts) == 1, d.name
