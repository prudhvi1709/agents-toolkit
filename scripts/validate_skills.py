#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6"]
# ///
"""Validate agent skill folders against the Agent Skills spec.

Encodes the rules from Anthropic's skill best-practices page and the
skill-creator skill, plus a signal-density heuristic that flags skills made
only of advice the model already follows by default.

Exit codes: 0 clean, 1 findings at or above the fail threshold, 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path

import yaml

# Spec limits. Sources: platform.claude.com agent-skills/best-practices,
# skill-creator/scripts/quick_validate.py.
MAX_NAME_LEN = 64
MAX_DESCRIPTION_LEN = 1024
MAX_BODY_LINES = 500
WARN_BODY_LINES = 300

# Frontmatter keys the portable Agent Skills validator accepts.
PORTABLE_KEYS = frozenset({"name", "description", "license", "allowed-tools", "metadata"})
# Extra keys Claude Code understands but other hosts (e.g. Codex) reject.
HOST_SPECIFIC_KEYS = frozenset(
    {
        "disable-model-invocation",
        "user-invocable",
        "when_to_use",
        "argument-hint",
        "arguments",
        "context",
    }
)

# Files skill-creator explicitly says not to ship inside a skill folder.
EXTRANEOUS_NAMES = frozenset(
    {"readme.md", "changelog.md", "installation_guide.md", "quick_reference.md", "todo.md"}
)

NAME_RE = re.compile(r"^[a-z0-9-]+$")
TRIGGER_RE = re.compile(r"use (this )?(skill )?when|trigger|when the user|invoke when", re.I)
FIRST_PERSON_RE = re.compile(r"\b(I|I'm|my|you|your|we|our)\b")
VAGUE_NAMES = frozenset({"helper", "helpers", "utils", "tools", "documents", "data", "files"})

# Typography banned by the user's global rules (plain ASCII everywhere).
BANNED_CHARS = {
    "\u2014": "em dash",
    "\u2013": "en dash",
    "\u201c": "curly quote",
    "\u201d": "curly quote",
    "\u2018": "curly quote",
    "\u2019": "curly apostrophe",
    "\u2026": "ellipsis",
    "\u2192": "arrow",
    "\u2713": "check mark",
    "\u2717": "cross mark",
    "\u00a0": "non-breaking space",
}

# A line is "concrete" if it carries something the model cannot invent: a
# command, path, flag, identifier, env var, or number. Heuristic ceiling: it
# counts syntax, not usefulness, so a skill can game it with decorative
# backticks. Upgrade path is a rubric-scored LLM pass if that ever happens.
CONCRETE_RE = re.compile(r"`[^`]+`|^\s{0,3}(\$|#|>)\s|--[a-z][\w-]+|\b[A-Z][A-Z0-9_]{3,}\b|\d")
MIN_CONCRETE_RATIO = 0.15


class Level(StrEnum):
    ERROR = "error"
    WARN = "warn"
    INFO = "info"


@dataclass(frozen=True, slots=True)
class Finding:
    skill: str
    level: Level
    rule: str
    message: str


@dataclass(frozen=True, slots=True)
class Metrics:
    skill: str
    body_lines: int
    description_chars: int
    concrete_ratio: float
    bundled_files: int


@dataclass(frozen=True, slots=True)
class Criterion:
    name: str
    earned: int
    possible: int
    note: str


@dataclass(frozen=True, slots=True)
class Score:
    skill: str
    earned: int
    possible: int
    criteria: tuple[Criterion, ...]

    @property
    def percent(self) -> int:
        return round(100 * self.earned / self.possible) if self.possible else 0


class SkillError(Exception):
    """A skill folder cannot be parsed far enough to validate."""


def split_frontmatter(text: str) -> tuple[dict[str, object], str]:
    if not text.startswith("---"):
        raise SkillError("no YAML frontmatter (file must start with ---)")
    match = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.DOTALL)
    if not match:
        raise SkillError("frontmatter is not closed by a second --- line")
    try:
        loaded = yaml.safe_load(match.group(1))
    except yaml.YAMLError as err:
        raise SkillError(f"invalid YAML in frontmatter: {err}") from err
    if not isinstance(loaded, dict):
        raise SkillError("frontmatter must be a YAML mapping")
    return loaded, match.group(2)


def check_name(skill_dir: Path, front: dict[str, object]) -> Iterator[Finding]:
    name = front.get("name")
    if name is None:
        yield Finding(skill_dir.name, Level.INFO, "name", "no name field; host defaults to folder name")
        return
    if not isinstance(name, str):
        yield Finding(skill_dir.name, Level.ERROR, "name", f"name must be a string, got {type(name).__name__}")
        return
    name = name.strip()
    if not NAME_RE.match(name):
        yield Finding(skill_dir.name, Level.ERROR, "name", f"'{name}' must be hyphen-case [a-z0-9-]")
    if name.startswith("-") or name.endswith("-") or "--" in name:
        yield Finding(skill_dir.name, Level.ERROR, "name", f"'{name}' has a leading, trailing, or doubled hyphen")
    if len(name) > MAX_NAME_LEN:
        yield Finding(skill_dir.name, Level.ERROR, "name", f"name is {len(name)} chars, max {MAX_NAME_LEN}")
    if name != skill_dir.name:
        yield Finding(skill_dir.name, Level.WARN, "name", f"name '{name}' does not match folder '{skill_dir.name}'")
    if name in VAGUE_NAMES:
        yield Finding(skill_dir.name, Level.WARN, "name", f"'{name}' is on the spec's vague-name list")


def check_description(skill_dir: Path, front: dict[str, object]) -> Iterator[Finding]:
    # With model invocation disabled the description never enters context for
    # auto-triggering, so trigger-phrase advice does not apply.
    user_only = front.get("disable-model-invocation") in {True, "true", "yes", "on", 1, "1"}
    raw = front.get("description")
    if raw is None:
        yield Finding(skill_dir.name, Level.ERROR, "description", "missing description; it is the only trigger signal")
        return
    if not isinstance(raw, str):
        yield Finding(skill_dir.name, Level.ERROR, "description", f"must be a string, got {type(raw).__name__}")
        return
    desc = " ".join(raw.split())
    if len(desc) > MAX_DESCRIPTION_LEN:
        yield Finding(
            skill_dir.name, Level.ERROR, "description", f"{len(desc)} chars, max {MAX_DESCRIPTION_LEN}"
        )
    if "<" in desc or ">" in desc:
        yield Finding(skill_dir.name, Level.ERROR, "description", "angle brackets are rejected by the validator")
    if not TRIGGER_RE.search(desc) and not user_only:
        yield Finding(
            skill_dir.name, Level.WARN, "description", "no explicit trigger ('Use when ...'); may never fire"
        )
    if TRIGGER_RE.match(desc):
        yield Finding(
            skill_dir.name,
            Level.WARN,
            "description",
            "opens with the trigger, so it never says what the skill does or provides",
        )
    if found := FIRST_PERSON_RE.search(desc):
        yield Finding(
            skill_dir.name,
            Level.WARN,
            "description",
            f"'{found.group(0)}' is first/second person; the spec requires third person",
        )


def check_frontmatter_keys(skill_dir: Path, front: dict[str, object]) -> Iterator[Finding]:
    keys = {str(k) for k in front}
    if unknown := keys - PORTABLE_KEYS - HOST_SPECIFIC_KEYS:
        yield Finding(
            skill_dir.name, Level.ERROR, "frontmatter", f"unrecognized key(s): {', '.join(sorted(unknown))}"
        )
    if host_only := keys & HOST_SPECIFIC_KEYS:
        yield Finding(
            skill_dir.name,
            Level.WARN,
            "frontmatter",
            f"{', '.join(sorted(host_only))} is Claude Code only; portable validators reject it",
        )


def check_body(skill_dir: Path, body: str) -> Iterator[Finding]:
    lines = body.splitlines()
    if len(lines) > MAX_BODY_LINES:
        yield Finding(
            skill_dir.name, Level.ERROR, "body-length", f"{len(lines)} lines, spec max {MAX_BODY_LINES}"
        )
    elif len(lines) > WARN_BODY_LINES:
        yield Finding(
            skill_dir.name,
            Level.WARN,
            "body-length",
            f"{len(lines)} lines; consider moving detail into references/",
        )
    if re.search(r"^#+\s*when to use\b", body, re.I | re.M):
        yield Finding(
            skill_dir.name,
            Level.WARN,
            "when-to-use",
            "'When to use' belongs in the description; the body loads only after the skill triggers",
        )
    if re.search(r"^#+\s*(setup|installation|install|dependency|dependencies)\b", body, re.I | re.M):
        yield Finding(
            skill_dir.name,
            Level.WARN,
            "readme-shape",
            "setup/install section reads as user documentation, which the spec excludes from skills",
        )
    for char, label in BANNED_CHARS.items():
        if char in body:
            yield Finding(skill_dir.name, Level.WARN, "typography", f"contains {label} (ASCII-only rule)")
    if re.search(r"`[^`\n]*\\[a-zA-Z]", body):
        yield Finding(skill_dir.name, Level.WARN, "paths", "backslash path in code span; use forward slashes")


def check_bundle(skill_dir: Path, body: str) -> Iterator[Finding]:
    bundled = [p for p in skill_dir.rglob("*") if p.is_file() and p.name != "SKILL.md"]
    for path in bundled:
        if path.name.lower() in EXTRANEOUS_NAMES:
            yield Finding(
                skill_dir.name,
                Level.WARN,
                "extraneous",
                f"{path.relative_to(skill_dir)} is auxiliary documentation the spec says to omit",
            )
    root_code = [p for p in bundled if p.parent == skill_dir and p.suffix in {".py", ".js", ".sh", ".mjs"}]
    for path in root_code:
        yield Finding(
            skill_dir.name,
            Level.INFO,
            "layout",
            f"{path.name} sits at the skill root; the spec layout puts executables in scripts/",
        )
    for path in bundled:
        rel = path.relative_to(skill_dir).as_posix()
        if path.suffix in {".py", ".js", ".sh", ".mjs", ".md"} and rel not in body and path.name not in body:
            yield Finding(
                skill_dir.name,
                Level.WARN,
                "unreferenced",
                f"{rel} is never mentioned in SKILL.md, so it will not be discovered",
            )
    for ref in (skill_dir / "references").glob("*.md"):
        if re.search(r"\]\(\s*(?!https?:)[^)]+\.md", ref.read_text(encoding="utf-8")):
            yield Finding(
                skill_dir.name,
                Level.WARN,
                "nested-refs",
                f"references/{ref.name} links to another local file; keep references one level deep",
            )


def concrete_ratio(body: str) -> tuple[float, int]:
    """Fraction of prose lines carrying a concrete token, ignoring fenced code."""
    in_fence = False
    prose: list[str] = []
    for line in body.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not line.strip() or line.lstrip().startswith("#"):
            continue
        prose.append(line)
    if not prose:
        return 1.0, 0
    hits = sum(1 for line in prose if CONCRETE_RE.search(line))
    return hits / len(prose), len(prose)


def score_skill(
    skill_dir: Path, front: dict[str, object], body: str, findings: list[Finding], metrics: Metrics
) -> Score:
    """Score a skill against the published guidance.

    Each criterion is a binary or thresholded check drawn from the Agent Skills
    spec and Anthropic's authoring guidance. The criteria are theirs; the
    weights are a judgement call about what makes a skill actually fire and
    actually help, so compare skills against each other rather than treating a
    number as an absolute grade.
    """
    desc = " ".join(str(front.get("description", "")).split())
    # A user-invoked skill is never auto-triggered, so a trigger phrase is moot.
    user_only = front.get("disable-model-invocation") in {True, "true", "yes", "on", 1, "1"}
    errors = {f.rule for f in findings if f.level is Level.ERROR}
    warns = {f.rule for f in findings if f.level is Level.WARN}
    body_lines = metrics.body_lines
    has_fence = "```" in body
    scripts = [p for p in skill_dir.rglob("*") if p.is_file() and p.suffix in {".py", ".js", ".sh", ".mjs"}]

    def hit(name: str, ok: bool, possible: int, yes: str, no: str) -> Criterion:
        return Criterion(name, possible if ok else 0, possible, yes if ok else no)

    criteria = [
        hit(
            "frontmatter",
            "frontmatter" not in errors,
            10,
            "parses and uses recognized keys",
            "invalid or unrecognized frontmatter",
        ),
        hit("name", "name" not in errors, 5, "valid hyphen-case name", "invalid name"),
        hit(
            "description-limits",
            "description" not in errors,
            5,
            f"{len(desc)} chars, within the {MAX_DESCRIPTION_LEN} limit",
            "exceeds limits or contains angle brackets",
        ),
        hit(
            "description-what",
            bool(desc) and not TRIGGER_RE.match(desc),
            10,
            "says what the skill does before when to use it",
            "opens with the trigger, so it never says what it provides",
        ),
        hit(
            "description-when",
            bool(TRIGGER_RE.search(desc)) or user_only,
            10,
            "user-invoked, so no trigger needed" if user_only else "carries an explicit trigger",
            "no explicit trigger, so it may never fire",
        ),
        hit(
            "body-length",
            body_lines <= MAX_BODY_LINES,
            10,
            f"{body_lines} lines, within the {MAX_BODY_LINES} limit",
            f"{body_lines} lines exceeds the {MAX_BODY_LINES} limit",
        ),
        hit(
            "worked-example",
            has_fence or bool(scripts),
            20,
            "ships a runnable example or script",
            "no code block and no script; the model must invent the how",
        ),
        # A compact skill has nothing to disclose progressively, so it is not
        # penalized; only a long body with nothing split out, or a bundled file
        # the body never mentions, loses points here.
        hit(
            "context-economy",
            ("unreferenced" not in warns)
            and (metrics.bundled_files > 0 or body_lines <= WARN_BODY_LINES),
            10,
            f"{metrics.bundled_files} bundled file(s) referenced"
            if metrics.bundled_files
            else f"compact at {body_lines} lines, nothing to split",
            "long body with nothing split out, or a bundled file the body never mentions",
        ),
        Criterion(
            "signal-density",
            20 if metrics.concrete_ratio >= MIN_CONCRETE_RATIO else round(
                20 * metrics.concrete_ratio / MIN_CONCRETE_RATIO
            ),
            20,
            f"{metrics.concrete_ratio:.0%} of prose lines carry a concrete token",
        ),
        hit(
            "layout",
            not ({"extraneous", "typography", "readme-shape"} & warns),
            10,
            "spec layout, no extraneous docs, clean typography",
            "extraneous docs, README shape, or banned typography",
        ),
    ]
    return Score(
        skill=skill_dir.name,
        earned=sum(c.earned for c in criteria),
        possible=sum(c.possible for c in criteria),
        criteria=tuple(criteria),
    )


def validate(skill_dir: Path) -> tuple[list[Finding], Metrics | None, Score | None]:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return [Finding(skill_dir.name, Level.ERROR, "structure", "SKILL.md not found")], None, None
    text = skill_md.read_text(encoding="utf-8")
    try:
        front, body = split_frontmatter(text)
    except SkillError as err:
        return [Finding(skill_dir.name, Level.ERROR, "frontmatter", str(err))], None, None

    findings = [
        *check_name(skill_dir, front),
        *check_description(skill_dir, front),
        *check_frontmatter_keys(skill_dir, front),
        *check_body(skill_dir, body),
        *check_bundle(skill_dir, body),
    ]

    ratio, prose_lines = concrete_ratio(body)
    fenced = "```" in body
    bundled = sum(1 for p in skill_dir.rglob("*") if p.is_file() and p.name != "SKILL.md")
    if ratio < MIN_CONCRETE_RATIO and not fenced and bundled == 0:
        findings.append(
            Finding(
                skill_dir.name,
                Level.WARN,
                "signal-density",
                f"{ratio:.0%} of {prose_lines} prose lines are concrete, no code block, no bundled file; "
                "likely restates default model behavior",
            )
        )

    desc = front.get("description")
    metrics = Metrics(
        skill=skill_dir.name,
        body_lines=len(body.splitlines()),
        description_chars=len(" ".join(str(desc).split())) if desc else 0,
        concrete_ratio=round(ratio, 3),
        bundled_files=bundled,
    )
    return findings, metrics, score_skill(skill_dir, front, body, findings, metrics)


def discover(root: Path) -> list[Path]:
    if (root / "SKILL.md").exists():
        return [root]
    return sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith("."))


def render_text(findings: list[Finding], metrics: list[Metrics]) -> str:
    icon = {Level.ERROR: "ERROR", Level.WARN: " WARN", Level.INFO: " INFO"}
    out: list[str] = []
    by_skill: dict[str, list[Finding]] = {}
    for f in findings:
        by_skill.setdefault(f.skill, []).append(f)
    for m in metrics:
        flags = by_skill.get(m.skill, [])
        errors = sum(1 for f in flags if f.level is Level.ERROR)
        warns = sum(1 for f in flags if f.level is Level.WARN)
        head = "ok" if not errors and not warns else f"{errors} error(s), {warns} warning(s)"
        out.append(
            f"\n{m.skill}  [{head}]\n"
            f"  body {m.body_lines} lines | description {m.description_chars} chars | "
            f"concrete {m.concrete_ratio:.0%} | bundled {m.bundled_files}"
        )
        for f in sorted(flags, key=lambda f: list(Level).index(f.level)):
            out.append(f"  {icon[f.level]}  {f.rule}: {f.message}")
    for f in findings:
        if f.skill not in {m.skill for m in metrics}:
            out.append(f"\n{f.skill}\n  {icon[f.level]}  {f.rule}: {f.message}")
    return "\n".join(out).lstrip("\n")


def render_scores(scores: list[Score], *, detail: bool) -> str:
    out = [
        "Scored against the Agent Skills spec and Anthropic's authoring guidance.",
        "Criteria are theirs; weights are a judgement call, so read these as",
        "relative rankings rather than absolute grades.",
        "",
        f"{'skill':<26} {'score':>5}  weakest criteria",
        "-" * 78,
    ]
    for s in sorted(scores, key=lambda s: s.earned, reverse=True):
        lost = [c for c in s.criteria if c.earned < c.possible]
        worst = ", ".join(f"{c.name} ({c.earned}/{c.possible})" for c in sorted(lost, key=lambda c: c.earned - c.possible)[:3])
        out.append(f"{s.skill:<26} {s.percent:>4}%  {worst or 'none'}")
    if detail:
        for s in sorted(scores, key=lambda s: s.earned, reverse=True):
            out.append(f"\n{s.skill}  {s.earned}/{s.possible}")
            for c in s.criteria:
                out.append(f"  {c.earned:>3}/{c.possible:<3} {c.name:<22} {c.note}")
    if scores:
        mean = sum(s.percent for s in scores) / len(scores)
        out.append(f"\n{len(scores)} skill{'s' if len(scores) != 1 else ''}, mean {mean:.0f}%")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate agent skill folders against the Agent Skills spec.",
        epilog=(
            "examples:\n"
            "  validate_skills.py ~/.claude/skills\n"
            "  validate_skills.py ~/.claude/skills/foundry-client --output json\n"
            "  validate_skills.py ~/.claude/skills --score --detail\n"
            "  validate_skills.py ~/.claude/skills --fail-on warn\n\n"
            "exit codes: 0 clean, 1 findings at or above --fail-on, 2 usage error"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("path", type=Path, help="a skills directory, or a single skill folder")
    parser.add_argument("--output", choices=("text", "json"), default="text", help="output format")
    parser.add_argument(
        "--fail-on", choices=("error", "warn"), default="error", help="lowest level that exits non-zero"
    )
    parser.add_argument("--score", action="store_true", help="rank skills against the guidance")
    parser.add_argument("--detail", action="store_true", help="with --score, show every criterion")
    args = parser.parse_args()

    root = args.path.expanduser()
    if not root.is_dir():
        parser.error(f"not a directory: {root}")

    skills = discover(root)
    if not skills:
        parser.error(f"no skill folders found under {root}")

    findings: list[Finding] = []
    metrics: list[Metrics] = []
    scores: list[Score] = []
    for skill in skills:
        skill_findings, skill_metrics, skill_score = validate(skill)
        findings.extend(skill_findings)
        if skill_metrics:
            metrics.append(skill_metrics)
        if skill_score:
            scores.append(skill_score)

    if args.output == "json":
        payload: dict[str, object] = {
            "findings": [asdict(f) for f in findings],
            "metrics": [asdict(m) for m in metrics],
        }
        if args.score:
            payload["scores"] = [asdict(s) | {"percent": s.percent} for s in scores]
        print(json.dumps(payload, indent=2))
    elif args.score:
        print(render_scores(scores, detail=args.detail))
    else:
        print(render_text(findings, metrics))

    levels = {Level.ERROR} if args.fail_on == "error" else {Level.ERROR, Level.WARN}
    return 1 if any(f.level in levels for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
