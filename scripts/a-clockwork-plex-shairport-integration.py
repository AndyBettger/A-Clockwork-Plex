#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Mapping


BLOCK_RE_TEMPLATE = r"(?P<prefix>\b{block}\s*=\s*\{{)(?P<body>.*?)(?P<suffix>\}}\s*;)"
ASSIGNMENT_RE_TEMPLATE = r"(?m)^(?P<indent>[ \t]*){key}[ \t]*=[ \t]*(?P<value>[^;]*);[ \t]*$"


def quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def block_regex(block: str) -> re.Pattern[str]:
    return re.compile(BLOCK_RE_TEMPLATE.format(block=re.escape(block)), re.DOTALL)


def assignment_regex(key: str) -> re.Pattern[str]:
    return re.compile(ASSIGNMENT_RE_TEMPLATE.format(key=re.escape(key)))


def update_block(text: str, block: str, assignments: Mapping[str, str], remove: tuple[str, ...] = ()) -> str:
    pattern = block_regex(block)
    match = pattern.search(text)
    if match:
        body = match.group("body")
    else:
        separator = "" if not text or text.endswith("\n") else "\n"
        text = f"{text}{separator}\n{block} =\n{{\n}};\n"
        match = pattern.search(text)
        if match is None:  # pragma: no cover - defensive
            raise ValueError(f"Could not create {block} block")
        body = match.group("body")

    for key in remove:
        body = assignment_regex(key).sub("", body)

    for key, rendered_value in assignments.items():
        statement = f"    {key} = {rendered_value};"
        key_pattern = assignment_regex(key)
        if key_pattern.search(body):
            body = key_pattern.sub(statement, body, count=1)
        else:
            if body and not body.startswith("\n"):
                body = "\n" + body
            body = f"{body.rstrip()}\n{statement}\n"

    # Remove empty whitespace-only lines introduced by retired statements while
    # keeping comments and unrelated settings exactly where they were.
    body = re.sub(r"(?m)^[ \t]+$\n?", "", body)
    return text[: match.start("body")] + body + text[match.end("body") :]


def render_integration(
    text: str,
    *,
    start_wrapper: str = "/usr/local/bin/a-clockwork-plex-airplay-start",
    end_wrapper: str = "/usr/local/bin/a-clockwork-plex-airplay-end",
    metadata_pipe: str = "/tmp/shairport-sync-metadata",
) -> str:
    updated = update_block(
        text,
        "alsa",
        {"output_device": quote("acp_airplay")},
    )
    updated = update_block(
        updated,
        "sessioncontrol",
        {
            "run_this_before_entering_active_state": quote(start_wrapper),
            "run_this_after_exiting_active_state": quote(end_wrapper),
            "active_state_timeout": "10",
            "wait_for_completion": quote("yes"),
        },
        remove=("run_this_after_play_ends", "session_timeout"),
    )
    return update_block(
        updated,
        "metadata",
        {
            "enabled": quote("yes"),
            "include_cover_art": quote("yes"),
            "pipe_name": quote(metadata_pipe),
            "pipe_timeout": "5000",
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Render A Clockwork Plex Shairport integration into a config file.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--start-wrapper", default="/usr/local/bin/a-clockwork-plex-airplay-start")
    parser.add_argument("--end-wrapper", default="/usr/local/bin/a-clockwork-plex-airplay-end")
    parser.add_argument("--metadata-pipe", default="/tmp/shairport-sync-metadata")
    arguments = parser.parse_args()

    source = arguments.input.read_text(encoding="utf-8")
    rendered = render_integration(
        source,
        start_wrapper=arguments.start_wrapper,
        end_wrapper=arguments.end_wrapper,
        metadata_pipe=arguments.metadata_pipe,
    )
    arguments.output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
