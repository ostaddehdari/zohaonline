#!/usr/bin/env python3
"""Force ZohaOnline Aurora routing into all plausible active HTTP/HTTPS IP servers.

This utility is deliberately defensive for VPS installations that contain several
legacy Nginx files, duplicate server_name declarations, or old direct locations.
It removes prior ZohaOnline includes/locations only inside target server blocks,
then adds exactly one Aurora snippet include to each target block.
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import re
import shutil
import sys


def matching_brace(text: str, opening: int) -> int:
    depth = 0
    quote: str | None = None
    escaped = False
    comment = False
    for pos in range(opening, len(text)):
        ch = text[pos]
        if comment:
            if ch == "\n":
                comment = False
            continue
        if quote:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
            continue
        if ch == "#":
            comment = True
            continue
        if ch in {"'", '"'}:
            quote = ch
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return pos + 1
    raise RuntimeError(f"Unbalanced Nginx braces near character {opening}")


def server_ranges(text: str) -> list[tuple[int, int]]:
    found: list[tuple[int, int]] = []
    pattern = re.compile(r"(?m)^[ \t]*server[ \t]*\{")
    for match in pattern.finditer(text):
        opening = text.find("{", match.start(), match.end())
        end = matching_brace(text, opening)
        found.append((match.start(), end))
    return found


def listens(block: str, port: int) -> bool:
    return bool(re.search(rf"(?m)^[ \t]*listen[ \t]+(?:\[::\]:)?{port}(?:[ \t]+[^;]*)?;", block))


def is_target(block: str, ip: str) -> bool:
    is_public_port = listens(block, 80) or listens(block, 443)
    if not is_public_port:
        return False
    names = " ".join(re.findall(r"(?m)^[ \t]*server_name[ \t]+([^;]+);", block))
    exactish = ip in names or re.search(r"(^|\s)_($|\s)", names) is not None
    default_server = re.search(r"(?m)^[ \t]*listen[ \t]+[^;]*\bdefault_server\b[^;]*;", block) is not None
    legacy = "zohaonline" in block.lower()
    return exactish or default_server or legacy


def remove_old_routes(block: str, include_line: str) -> str:
    # Remove this exact release include and any legacy ZohaOnline snippet include.
    exact_path = include_line.removeprefix("include ").removesuffix(";")
    block = re.sub(
        rf"(?mi)^[ \t]*include[ \t]+{re.escape(exact_path)}[ \t]*;[ \t]*\n?",
        "",
        block,
    )
    block = re.sub(
        r"(?mi)^[ \t]*include[ \t]+[^;\n]*zohaonline[^;\n]*;[ \t]*\n?",
        "",
        block,
    )
    # Remove direct old location blocks for this path.
    location_pattern = re.compile(
        r"(?mi)^[ \t]*location\b[^\n{]*(?:/zohaonline\b|zohaonline)[^\n{]*\{"
    )
    while True:
        match = location_pattern.search(block)
        if not match:
            break
        opening = block.find("{", match.start(), match.end())
        end = matching_brace(block, opening)
        while end < len(block) and block[end] in " \t":
            end += 1
        if end < len(block) and block[end] == "\n":
            end += 1
        block = block[: match.start()] + block[end:]
    return block


def inject(block: str, include_line: str) -> str:
    block = remove_old_routes(block, include_line).rstrip()
    closing = block.rfind("}")
    if closing < 0:
        raise RuntimeError("Invalid server block: closing brace not found")
    indent_match = re.match(r"(?m)^([ \t]*)\}[ \t]*$", block[closing:])
    indent = indent_match.group(1) if indent_match else ""
    return block[:closing].rstrip() + f"\n\n{indent}    {include_line}\n" + block[closing:]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sites-enabled", default="/etc/nginx/sites-enabled")
    parser.add_argument("--snippet", required=True)
    parser.add_argument("--ip", required=True)
    args = parser.parse_args()

    enabled = Path(args.sites_enabled)
    snippet = Path(args.snippet).resolve()
    if not enabled.exists():
        raise SystemExit(f"sites-enabled not found: {enabled}")
    if not snippet.exists():
        raise SystemExit(f"snippet not found: {snippet}")

    include_line = f"include {snippet};"
    paths: list[Path] = []
    seen: set[Path] = set()
    roots = [enabled]
    confd = enabled.parent / "conf.d"
    if confd.exists() and confd.resolve() != enabled.resolve():
        roots.append(confd)
    for root in roots:
        for entry in sorted(root.iterdir()):
            if entry.name.startswith(".") or entry.suffix in {".bak", ".backup"}:
                continue
            try:
                real = entry.resolve(strict=True)
            except (FileNotFoundError, RuntimeError):
                continue
            if real.is_file() and real not in seen:
                seen.add(real)
                paths.append(real)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    total = http_count = https_count = 0
    modified: list[Path] = []

    for path in paths:
        original = path.read_text()
        text = original
        ranges = server_ranges(text)
        file_targets = 0
        for start, end in reversed(ranges):
            block = text[start:end]
            if not is_target(block, args.ip):
                continue
            has80, has443 = listens(block, 80), listens(block, 443)
            text = text[:start] + inject(block, include_line) + text[end:]
            total += 1
            http_count += int(has80)
            https_count += int(has443)
            file_targets += 1
        if text != original:
            backup = path.with_name(f"{path.name}.aurora250-backup-{stamp}")
            shutil.copy2(path, backup)
            path.write_text(text)
            modified.append(path)
            print(f"patched: {path} | server blocks: {file_targets} | backup: {backup}")

    if total == 0 or http_count == 0:
        raise SystemExit("No active HTTP target server block was found for ZohaOnline.")
    if https_count == 0:
        raise SystemExit("No active HTTPS target server block was found; Aurora requires both HTTP and HTTPS.")

    print(f"Aurora routing summary: blocks={total}, http={http_count}, https={https_count}")
    print(f"Aurora snippet: {snippet}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Aurora Nginx patch failed: {exc}", file=sys.stderr)
        raise
