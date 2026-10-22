"""Repo-level consistency: every skill carries an identical copy of the contract module.

The copy is a package directory, ``scripts/accord_contract/__init__.py``, because the
catalog runner (skills-runner) runs the single ``.py`` file directly inside ``scripts/``
and refuses a directory that holds two.
"""

from helpers import SKILLS_ROOT, TOOLS_ROOT

CONTRACT_COPY = ("scripts", "accord_contract", "__init__.py")


def _skill_dirs():
    return sorted(p for p in SKILLS_ROOT.iterdir() if (p / "SKILL.md").is_file())


def test_every_skill_has_an_identical_contract_copy():
    src = (TOOLS_ROOT / "accord_contract.py").read_text()
    skill_dirs = _skill_dirs()
    assert skill_dirs, "no skills yet"
    for d in skill_dirs:
        assert d.joinpath(*CONTRACT_COPY).read_text() == src, d.name


def test_exactly_one_python_file_directly_inside_scripts():
    for d in _skill_dirs():
        py_files = sorted(p.name for p in (d / "scripts").iterdir() if p.suffix == ".py")
        assert len(py_files) == 1, (d.name, py_files)
