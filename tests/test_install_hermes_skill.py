import argparse
from pathlib import Path

import pytest

from scripts.install_hermes_skill import InstallError, build_plan, copy_skill, parse_frontmatter


def make_skill(root: Path) -> Path:
    skill = root / ".hermes" / "skills" / "hermes-autoresearch"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\n"
        "name: hermes-autoresearch\n"
        "description: Use when installing Hermes Autoresearch.\n"
        "---\n\n"
        "# Hermes Autoresearch\n",
        encoding="utf-8",
    )
    (skill / "templates").mkdir()
    (skill / "templates" / "run_config.yaml").write_text("name: test\n", encoding="utf-8")
    return skill


def test_parse_frontmatter_requires_name_and_description(tmp_path):
    skill = make_skill(tmp_path)
    data = parse_frontmatter(skill / "SKILL.md")
    assert data["name"] == "hermes-autoresearch"


def test_build_plan_targets_profile_category(tmp_path):
    make_skill(tmp_path)
    profiles_root = tmp_path / "profiles"
    plan = build_plan(
        source_repo=tmp_path,
        profile="coder",
        category="software-development",
        skill_path=".hermes/skills/hermes-autoresearch",
        name=None,
        overwrite=False,
        dry_run=True,
        profiles_root=profiles_root,
    )
    assert plan.destination == profiles_root / "coder" / "skills" / "software-development" / "hermes-autoresearch"


def test_copy_skill_installs_templates(tmp_path):
    make_skill(tmp_path)
    profiles_root = tmp_path / "profiles"
    plan = build_plan(
        source_repo=tmp_path,
        profile="coder",
        category="software-development",
        skill_path=".hermes/skills/hermes-autoresearch",
        name=None,
        overwrite=False,
        dry_run=False,
        profiles_root=profiles_root,
    )
    copy_skill(plan)
    assert (plan.destination / "SKILL.md").exists()
    assert (plan.destination / "templates" / "run_config.yaml").exists()


def test_existing_destination_requires_overwrite(tmp_path):
    make_skill(tmp_path)
    profiles_root = tmp_path / "profiles"
    destination = profiles_root / "coder" / "skills" / "software-development" / "hermes-autoresearch"
    destination.mkdir(parents=True)
    with pytest.raises(InstallError):
        build_plan(
            source_repo=tmp_path,
            profile="coder",
            category="software-development",
            skill_path=".hermes/skills/hermes-autoresearch",
            name=None,
            overwrite=False,
            dry_run=False,
            profiles_root=profiles_root,
        )


def test_invalid_category_rejected(tmp_path):
    make_skill(tmp_path)
    with pytest.raises(InstallError):
        build_plan(
            source_repo=tmp_path,
            profile="coder",
            category="../bad",
            skill_path=".hermes/skills/hermes-autoresearch",
            name=None,
            overwrite=False,
            dry_run=True,
            profiles_root=tmp_path / "profiles",
        )
