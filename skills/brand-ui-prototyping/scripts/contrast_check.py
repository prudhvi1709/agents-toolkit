#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Compute WCAG 2.2 contrast ratios for theme token pairings.

Models frequently misjudge contrast by eye or miscompute the relative-
luminance formula mentally. This does the arithmetic instead, so an approved
theme pairing is checked rather than assumed.

Two modes:
  one pairing   contrast_check.py "#1A1A1A" "#FFFFFF" --level text
  a theme file  contrast_check.py --tokens theme.json

theme.json is a list of pairings:
  [{"name": "primary-on-light", "fg": "#1A1A1A", "bg": "#FFFFFF", "level": "text"}]

Levels: text (4.5:1), large-text (3:1), non-text (3:1) - see
https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html and
https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html

Deliberate ceiling: checks the two flat colors given, not rendered overlap
with images, gradients, or translucency. Confirm those visually.

Exit codes:
  0   every pairing meets its threshold
  1   at least one pairing fails
  2   usage error (bad hex, bad JSON, bad level)
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

THRESHOLDS = {"text": 4.5, "large-text": 3.0, "non-text": 3.0}


class Level(StrEnum):
    TEXT = "text"
    LARGE_TEXT = "large-text"
    NON_TEXT = "non-text"


@dataclass(frozen=True, slots=True)
class Pairing:
    name: str
    fg: str
    bg: str
    level: Level


@dataclass(frozen=True, slots=True)
class Result:
    pairing: Pairing
    ratio: float

    @property
    def threshold(self) -> float:
        return THRESHOLDS[self.pairing.level]

    @property
    def passed(self) -> bool:
        return self.ratio >= self.threshold


def parse_hex(value: str) -> tuple[int, int, int]:
    raw = value.strip().lstrip("#")
    if len(raw) == 3:
        raw = "".join(ch * 2 for ch in raw)
    if len(raw) != 6:
        raise ValueError(f"expected a #RGB or #RRGGBB hex color, got {value!r}")
    try:
        return tuple(int(raw[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError as err:
        raise ValueError(f"expected a hex color, got {value!r}") from err


def _linearize(channel: int) -> float:
    c = channel / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = (_linearize(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg: str, bg: str) -> float:
    l1 = relative_luminance(parse_hex(fg))
    l2 = relative_luminance(parse_hex(bg))
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def load_tokens(path: Path) -> list[Pairing]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        raise ValueError(f"could not read {path} as JSON: {err}") from err
    if not isinstance(raw, list):
        raise ValueError(f"{path} must contain a JSON array of pairings")

    pairings = []
    for i, entry in enumerate(raw):
        try:
            pairings.append(
                Pairing(
                    name=entry["name"],
                    fg=entry["fg"],
                    bg=entry["bg"],
                    level=Level(entry.get("level", "text")),
                )
            )
        except (KeyError, ValueError) as err:
            raise ValueError(f"pairing #{i} in {path} is malformed: {err}") from err
    return pairings


def render_text(results: list[Result]) -> str:
    lines = []
    for r in results:
        mark = "PASS" if r.passed else "FAIL"
        lines.append(
            f"  [{mark}] {r.pairing.name}: {r.ratio:.2f}:1 "
            f"(needs {r.threshold}:1 for {r.pairing.level}) {r.pairing.fg} on {r.pairing.bg}"
        )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="contrast_check.py",
        description="Compute WCAG 2.2 contrast ratios for theme token pairings.",
        epilog=(
            "examples:\n"
            '  contrast_check.py "#1A1A1A" "#FFFFFF"\n'
            '  contrast_check.py "#6B6B6B" "#FFFFFF" --level large-text\n'
            "  contrast_check.py --tokens theme.json --output json\n\n"
            "exit codes: 0 all pass, 1 at least one fails, 2 usage error"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("fg", nargs="?", help="foreground hex color, e.g. #1A1A1A")
    parser.add_argument("bg", nargs="?", help="background hex color, e.g. #FFFFFF")
    parser.add_argument(
        "--level", choices=[level.value for level in Level], default=Level.TEXT.value,
        help="threshold to apply to a single pairing (default text, 4.5:1)",
    )
    parser.add_argument("--tokens", type=Path, metavar="FILE", help="JSON file of pairings to check")
    parser.add_argument("--output", choices=("text", "json"), default="text", help="report format")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.tokens and (args.fg or args.bg):
        parser.error("pass either --tokens FILE or a single fg/bg pair, not both")
    if args.tokens:
        try:
            pairings = load_tokens(args.tokens)
        except ValueError as err:
            parser.error(str(err))
    elif args.fg and args.bg:
        pairings = [Pairing(name="pairing", fg=args.fg, bg=args.bg, level=Level(args.level))]
    else:
        parser.error("pass fg and bg hex colors, or --tokens FILE")

    try:
        results = [Result(pairing=p, ratio=contrast_ratio(p.fg, p.bg)) for p in pairings]
    except ValueError as err:
        parser.error(str(err))

    if args.output == "json":
        print(
            json.dumps(
                [
                    {
                        "name": r.pairing.name,
                        "fg": r.pairing.fg,
                        "bg": r.pairing.bg,
                        "level": r.pairing.level.value,
                        "ratio": round(r.ratio, 2),
                        "threshold": r.threshold,
                        "passed": r.passed,
                    }
                    for r in results
                ],
                indent=2,
            )
        )
    else:
        print(render_text(results))

    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
