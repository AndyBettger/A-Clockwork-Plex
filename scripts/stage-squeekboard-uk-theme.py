#!/usr/bin/env python3
"""Offline only: stage UK keyboard YAML and ACP GTK3 style samples. Never runs OSK."""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

BASE = Path("/usr/share/misc/squeekboard/keyboards")
REPO = Path(__file__).resolve().parents[1]
DEST = Path.home() / ".cache/a-clockwork-plex/squeekboard-c2-uk-theme-v1"
VENDOR_HASH = "2ad3ef3750c26b94427deb7423041293c1ae658027261a38623373af1a243338"
VENDOR_VERSION = "1.43.1-1+rpt1"
SOURCES = ("us.yaml", "us_wide.yaml", "email/us.yaml", "url/us.yaml",
           "number/us.yaml", "pin/us.yaml", "terminal/us.yaml")
THEMES = ("classic_dark", "midnight_blue", "amber_terminal",
          "green_phosphor", "aubergine", "steel_cyan", "crimson_glow")


class StagingError(Exception):
    pass


def replace_once(source: str, before: str, after: str, label: str) -> str:
    if source.count(before) != 1:
        raise StagingError("Unexpected vendor keymap structure in " + label)
    return source.replace(before, after, 1)


def _validate_punctuation_row(source: str, filename: str) -> None:
    """Validate the actual vendor YAML symbols row, not guessed key aliases.

    Raspberry Pi Squeekboard 1.43.1-1+rpt1 writes the colon key as literal
    ':' in YAML, while some upstream revisions use the alias 'colon'.
    The double quote is YAML-escaped as \" (or can be a quotedbl alias).
    """
    rows = [line for line in source.splitlines()
            if "show_symbols" in line and "BackSpace" in line]
    if len(rows) != 1:
        raise StagingError("Expected exactly one symbols row in " + filename)
    row_match = re.fullmatch(r'\s*-\s*"(.+)"\s*', rows[0])
    if row_match is None:
        raise StagingError("Symbols row is not a double-quoted YAML list in " + filename)
    keys = row_match.group(1).split()
    if ":" not in keys and "colon" not in keys:
        raise StagingError("Colon (:) key missing from symbols row in " + filename)
    if "'" not in keys and "apostrophe" not in keys:
        raise StagingError("Apostrophe key missing from symbols row in " + filename)
    if r'\"' not in keys and "quotedbl" not in keys:
        raise StagingError("Double-quote key missing from symbols row in " + filename)


def layout(source: str, filename: str) -> str:
    if "views:" not in source or "buttons:" not in source:
        raise StagingError("Invalid source keyboard: " + filename)
    if filename.startswith("pin/"):
        return source
    if filename.startswith("number/"):
        # The commissioned Pi's 1.43.1-1+rpt1 layout uses literal
        # ( 1 2 3 ), not the older "1 2 3 parenleft parenright" syntax.
        # Literal '.' and ':' also appear in the Pi's other stock keymaps.
        if source.count("( 1 2 3 )") == 1:
            source = replace_once(source, "( 1 2 3 )", ". 1 2 3 :", filename)
            if " 7 8 9 -" not in source or " 4 5 6 +" not in source:
                raise StagingError("Pi numeric signed-key rows changed in " + filename)
            return source
        if source.count("1 2 3 parenleft parenright") == 1:
            source = replace_once(source, "1 2 3 parenleft parenright",
                                  "1 2 3 period colon", filename)
            if re.search(r"(?m)^    (?:period|colon):", source):
                raise StagingError("Numeric key definitions changed")
            return source.rstrip() + '\n    period:\n        text: "."\n    colon:\n        text: ":"\n'
        raise StagingError("Unrecognised numeric key row in " + filename)

    if filename.startswith("terminal/"):
        # Pi terminal: "\\ * # $ / & - + ( ) _";
        # upstream terminal: "* # $ / & - _ + ( )".
        source = replace_once(source, " # $ ", " # £ ", filename)
    else:
        source = replace_once(source, "@ # $ % & - _ + ( )",
                              "@ # £ % & - _ + ( )", filename)
    # Preserve access to dollars on the symbols view in every text purpose.
    source = replace_once(source, "© ® £ €", "© ® $ €", filename)
    _validate_punctuation_row(source, filename)
    return source


def stock() -> dict[str, str]:
    if os.geteuid() == 0:
        raise StagingError("Never run as root")
    try:
        result = subprocess.run(
            ["dpkg-query", "-W", "-f=" + "$" + "{Version}", "squeekboard"],
            capture_output=True, text=True, timeout=10, check=True)
        with Path("/usr/bin/squeekboard").open("rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
    except (OSError, subprocess.SubprocessError) as exc:
        raise StagingError("Unable to verify stock keyboard") from exc
    if result.stdout.strip() != VENDOR_VERSION or digest != VENDOR_HASH:
        raise StagingError("Stock package/version/hash changed; refusing trial files")
    out = {}
    for name in SOURCES:
        original = BASE / name
        if not original.is_file() or original.is_symlink():
            if name in ("us.yaml", "us_wide.yaml", "number/us.yaml"):
                raise StagingError("Required vendor YAML unavailable: " + name)
            continue
        output_name = name.replace("us_wide.yaml", "gb_wide.yaml").replace("us.yaml", "gb.yaml")
        out[output_name] = layout(original.read_text(encoding="utf-8"), name)
    return out


def palette_tokens() -> dict[str, dict[str, str]]:
    classic = (REPO / "app/static/css/style.css").read_text(encoding="utf-8")
    daytime = (REPO / "app/static/css/daytime-themes.css").read_text(encoding="utf-8")
    parse = lambda text: {a: b.strip() for a, b in
                          re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", text)}
    result = {"classic_dark": parse(classic.split("}", 1)[0])}
    for name, body in re.findall(
        r'html\[data-daytime-theme="([a-z_]+)"\]\s+body[^{]+\{([^}]*)\}',
        daytime, re.DOTALL,
    ):
        if name in THEMES:
            result[name] = parse(body)
    if set(result) != set(THEMES):
        raise StagingError("ACP palette set changed; review manually")
    for name, props in result.items():
        for token in ("--bg", "--text", "--accent"):
            if not re.fullmatch(r"#[0-9a-fA-F]{6}", props.get(token, "")):
                raise StagingError("Invalid colour token: " + name + " " + token)
    return result


def scaled(colour: str, factor: float) -> str:
    return "#" + "".join(format(round(int(colour[i:i + 2], 16) * factor), "02x")
                         for i in (1, 3, 5))


def gtk_style(bg: str, control: str, text: str, accent: str) -> str:
    # Only staged privately; loading priority and live reload need Pi testing.
    return (
        "/* ACP isolated GTK3 sample - do not install globally */\n"
        "sq_view { background-color: " + bg + "; color: " + text + "; }\n"
        "sq_view sq_button { background: " + control + "; color: " + text +
        "; border: 1px solid " + accent + "; border-radius: 6px; }\n"
        "sq_view sq_button:active, sq_view sq_button.locked, "
        "sq_view sq_button.latched { background: " + accent +
        "; color: " + bg + "; }\n"
        "sq_view sq_button.special, sq_view sq_button.altline, "
        "sq_view sq_button.wide { background: " + bg +
        "; color: " + text + "; }\n"
        "sq_view #Return { background: " + accent +
        "; color: " + bg + "; }\n"
    )


def styles() -> dict[str, str]:
    result = {}
    for name, t in palette_tokens().items():
        bg, fg, accent = t["--bg"], t["--text"], t["--accent"]
        result[name] = gtk_style(bg, t.get("--acp-theme-control", "#172c44"), fg, accent)
        for mode, level in (("idle", 0.32), ("active", 0.55)):
            result[name + "_night_classic_" + mode] = gtk_style(
                scaled(bg, 0.28), scaled(accent, 0.11),
                scaled(fg, level), scaled(accent, level))
    for mode, text, accent in (("idle", "#652323", "#722222"),
                               ("active", "#b33d3d", "#b84343")):
        result["astronomy_night_" + mode] = gtk_style(
            "#050000", "#180202", text, accent)
    return result


def stage(layouts: dict[str, str], themes: dict[str, str]) -> None:
    if DEST.exists() or DEST.is_symlink():
        raise StagingError("Refusing to overwrite existing stage: " + str(DEST))
    DEST.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = Path(tempfile.mkdtemp(prefix=".c2-staging-", dir=DEST.parent))
    try:
        tmp.chmod(0o700)
        for name, content in layouts.items():
            target = tmp / "keyboards" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        for name, content in themes.items():
            target = tmp / "themes" / name / "gtk-3.0" / "gtk.css"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        (tmp / "README.txt").write_text(
            "ACP Stage C2 OFFLINE candidate; no keyboard/theme service activated.\n"
            "UK YAML is intended for a future SQUEEKBOARD_KEYBOARDSDIR trial.\n"
            "GTK3 CSS is isolated for possible XDG_CONFIG_HOME candidate trial.\n"
            "Live theme synchronization and compositor checks are still OPEN.\n",
            encoding="utf-8")
        tmp.rename(DEST)
    finally:
        if tmp.exists():
            shutil.rmtree(tmp)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--plan", action="store_true")
    action.add_argument("--stage", action="store_true")
    args = parser.parse_args()
    try:
        keyboard, theme = stock(), styles()
        print("UK test YAML: " + ", ".join(sorted(keyboard)))
        print("ACP GTK3 theme samples: " + ", ".join(sorted(theme)))
        if args.stage:
            stage(keyboard, theme)
            print("STAGED only at " + str(DEST))
            print("No keyboard, GTK configuration or service was modified.")
        else:
            print("PLAN PASS: read-only checks; no files or processes modified.")
        return 0
    except (StagingError, OSError, ValueError) as exc:
        print("UK Squeekboard stage: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
