#!/usr/bin/env python3
"""Install the bundled Hermes Autoresearch skill into a Hermes profile."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit("PyYAML is required: python -m pip install pyyaml") from exc


DEFAULT_SKILL_PATH = ".hermes/skills/hermes-autoresearch"
DEFAULT_SOURCE_URL = "https://github.com/scottiesan/hermes-autoresearch"
PROFILE_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


class InstallError(RuntimeError):
    pass


@dataclass(frozen=True)
class InstallPlan:
    source_repo: Path
    source_skill: Path
    destination: Path
    backup: Path | None
    dry_run: bool


def is_git_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https", "ssh", "git"} or value.startswith("git@")


def clone_source(source: str, tmp_root: Path) -> Path:
    target = tmp_root / "repo"
    subprocess.run(["git", "clone", "--depth", "1", source, str(target)], check=True)
    return target


def resolve_source(source: str | None, tmp_root: Path | None = None) -> Path:
    if source is None:
        cwd = Path.cwd().resolve()
        if (cwd / DEFAULT_SKILL_PATH / "SKILL.md").exists():
            return cwd
        if tmp_root is None:
            raise InstallError("internal error: tmp_root is required for default URL source")
        return clone_source(DEFAULT_SOURCE_URL, tmp_root).resolve()
    if is_git_url(source):
        if tmp_root is None:
            raise InstallError("internal error: tmp_root is required for URL sources")
        return clone_source(source, tmp_root).resolve()
    return Path(source).expanduser().resolve()


def parse_frontmatter(skill_md: Path) -> dict:
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise InstallError(f"{skill_md} must start with YAML frontmatter")
    end = text.find("\n---\n", 4)
    if end == -1:
        raise InstallError(f"{skill_md} frontmatter is not closed")
    data = yaml.safe_load(text[4:end])
    if not isinstance(data, dict):
        raise InstallError(f"{skill_md} frontmatter must be a mapping")
    for field in ("name", "description"):
        if not data.get(field):
            raise InstallError(f"{skill_md} frontmatter missing {field}")
    if len(str(data["description"])) > 1024:
        raise InstallError(f"{skill_md} description is longer than 1024 characters")
    return data


def validate_profile_category(profile: str, category: str) -> None:
    if not PROFILE_RE.match(profile):
        raise InstallError(f"invalid Hermes profile name: {profile}")
    if category.startswith("/") or ".." in Path(category).parts:
        raise InstallError(f"invalid Hermes skill category: {category}")


def build_plan(
    source_repo: Path,
    profile: str,
    category: str,
    skill_path: str,
    name: str | None,
    overwrite: bool,
    dry_run: bool,
    profiles_root: Path | None = None,
) -> InstallPlan:
    validate_profile_category(profile, category)
    source_skill = (source_repo / skill_path).resolve()
    skill_md = source_skill / "SKILL.md"
    if not skill_md.exists():
        raise InstallError(f"source skill not found: {skill_md}")
    frontmatter = parse_frontmatter(skill_md)
    skill_name = name or str(frontmatter["name"])
    if not PROFILE_RE.match(skill_name):
        raise InstallError(f"invalid skill folder name: {skill_name}")
    root = profiles_root or Path.home() / ".hermes" / "profiles"
    destination = root / profile / "skills" / category / skill_name
    backup = None
    if destination.exists():
        if not overwrite:
            raise InstallError(f"destination exists, rerun with --overwrite: {destination}")
        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        backup = destination.with_name(f"{destination.name}.bak-{stamp}")
    return InstallPlan(source_repo, source_skill, destination, backup, dry_run)


def copy_skill(plan: InstallPlan) -> None:
    if plan.dry_run:
        return
    plan.destination.parent.mkdir(parents=True, exist_ok=True)
    if plan.backup:
        shutil.move(str(plan.destination), str(plan.backup))
    shutil.copytree(plan.source_skill, plan.destination)


def install(args: argparse.Namespace) -> InstallPlan:
    with tempfile.TemporaryDirectory(prefix="hermes-autoresearch-install-") as tmp:
        source_repo = resolve_source(args.source, Path(tmp))
        plan = build_plan(
            source_repo=source_repo,
            profile=args.profile,
            category=args.category,
            skill_path=args.skill_path,
            name=args.name,
            overwrite=args.overwrite,
            dry_run=args.dry_run,
        )
        copy_skill(plan)
        return plan


def print_plan(plan: InstallPlan) -> None:
    prefix = "DRY RUN" if plan.dry_run else "INSTALLED"
    print(f"{prefix}: {plan.destination}")
    print(f"SOURCE_REPO: {plan.source_repo}")
    print(f"SOURCE_SKILL: {plan.source_skill}")
    if plan.backup:
        print(f"BACKUP: {plan.backup}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install Hermes Autoresearch skill into a Hermes profile")
    parser.add_argument(
        "--source",
        help="Local repo path or git URL. Defaults to the current working directory.",
    )
    parser.add_argument("--profile", default="coder", help="Hermes profile name, default: coder")
    parser.add_argument("--category", default="software-development", help="Hermes skills category")
    parser.add_argument("--skill-path", default=DEFAULT_SKILL_PATH, help="Path to skill folder inside the repo")
    parser.add_argument("--name", help="Destination skill folder name; defaults to SKILL.md frontmatter name")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing skill after creating a backup")
    parser.add_argument("--dry-run", action="store_true", help="Validate and show destination without copying")
    args = parser.parse_args(argv)

    try:
        print_plan(install(args))
        return 0
    except (InstallError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
