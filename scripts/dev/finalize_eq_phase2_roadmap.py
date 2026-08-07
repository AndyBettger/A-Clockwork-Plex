#!/usr/bin/python3
from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ROADMAP = ROOT / 'docs' / 'eq-audio-installer-roadmap.md'


def section(text: str, heading: str, next_heading: str) -> tuple[str, str, str]:
    start = text.index(heading)
    end = text.index(next_heading, start)
    return text[:start], text[start:end], text[end:]


text = ROADMAP.read_text(encoding='utf-8')
text = re.sub(
    r'^\*\*Status:\*\* Active roadmap.*$',
    '**Status:** Active roadmap — Phase 3 in progress  ',
    text,
    count=1,
    flags=re.MULTILINE,
)

before, phase2, after = section(
    text,
    '### Phase 2 — standalone installer implementation',
    '### Phase 3 — non-production tests',
)
phase2 = phase2.replace('- [ ] ', '- [x] ')
checkpoint = '''
**Completion checkpoint — 7 August 2026:**

- the CamillaDSP-backed EQ helper preserves the dashboard command and JSON contract;
- the small route helper owns only fixed route, validation and failback actions;
- the supported install, verify, repair and uninstall commands are prepare-first;
- one exact pre-EQ backup supports rollback and later uninstall;
- repair and failed uninstall snapshot the current route, state files and CamillaDSP service state;
- a full live verifier is required before install or repair reports success;
- temporary-root tests cover install, repeated install, repair, uninstall, reinstall and injected rollback;
- the former approval, authority-borrowing and retained-transaction machinery is not used;
- the implementation has not changed the bedroom Pi.

'''
if '**Completion checkpoint — 7 August 2026:**' not in phase2:
    phase2 = phase2.replace('**Exit condition:**', checkpoint + '**Exit condition:**', 1)
text = before + phase2 + after

before, phase3, after = section(
    text,
    '### Phase 3 — non-production tests',
    '### Phase 4 — controlled bedroom-Pi installation',
)
for item in (
    'Validate shell syntax.',
    'Exercise install against a temporary filesystem root.',
    'Exercise repeated install for idempotence.',
    'Exercise explicit uninstall.',
    'Inject one or more simple failures and verify restoration.',
    'Confirm no test command writes to production paths.',
):
    phase3 = phase3.replace(f'- [ ] {item}', f'- [x] {item}')
if '**Current checkpoint:**' not in phase3:
    phase3 = phase3.replace(
        '**Exit condition:**',
        '**Current checkpoint:** filesystem lifecycle and rollback tests pass in isolated roots. '
        'Real Pi parser checks for ALSA, CamillaDSP and systemd remain before any installation.\n\n'
        '**Exit condition:**',
        1,
    )
text = before + phase3 + after

text = re.sub(
    r'^\| 2\. Standalone installer \|.*$',
    '| 2. Standalone installer | Complete | Supported prepare/install/verify/repair/uninstall path implemented and rollback-tested |',
    text,
    count=1,
    flags=re.MULTILINE,
)
text = re.sub(
    r'^\| 3\. Non-production tests \|.*$',
    '| 3. Non-production tests | In progress | Isolated filesystem lifecycle complete; Pi parser validation remains |',
    text,
    count=1,
    flags=re.MULTILINE,
)

next_heading = '## Next action'
if next_heading in text:
    prefix, _heading, tail = text.partition(next_heading)
    text = (
        prefix
        + next_heading
        + '\n\nBegin the remaining **Phase 3** host validation in read-only/prepare-only mode: '
        'parse both ALSA routes with the Pi\'s real ALSA stack, validate the rendered '
        'CamillaDSP configuration with the accepted 4.1.3 binary, and run systemd unit '
        'verification. No production audio route or service should be changed.\n'
    )

ROADMAP.write_text(text, encoding='utf-8')
