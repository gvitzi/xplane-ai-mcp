#!/usr/bin/env python3
"""Convert X-Plane ``DataRefs.txt`` (tab-separated) into ``.refs/datarefs.csv`` and index files."""

from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--input",
        type=Path,
        default=Path(".refs/source/DataRefs.txt"),
        help="Path to DataRefs.txt (default: .refs/source/DataRefs.txt)",
    )
    p.add_argument(
        "--csv-out",
        type=Path,
        default=Path(".refs/datarefs.csv"),
        help="Output CSV path",
    )
    p.add_argument(
        "--readme-out",
        type=Path,
        default=Path(".refs/README.md"),
        help="Output README path",
    )
    p.add_argument(
        "--prefix-index-out",
        type=Path,
        default=Path(".refs/prefix_index.md"),
        help="Output prefix index markdown path",
    )
    return p.parse_args()


def read_datarefs(path: Path) -> tuple[str, list[tuple[str, str, str, str, str]]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    if not lines:
        raise SystemExit(f"empty file: {path}")

    header = lines[0].strip()
    rows: list[tuple[str, str, str, str, str]] = []

    for line in lines[1:]:
        raw = line.strip("\n")
        if not raw.strip():
            continue
        if not raw.startswith("sim/"):
            raise SystemExit(f"unexpected non-data line after header: {raw[:80]!r}")

        parts = raw.split("\t")
        # name, type, writable, units, description[, empty…]
        while parts and parts[-1] == "":
            parts.pop()
        if len(parts) < 3:
            raise SystemExit(f"too few tab fields ({len(parts)}): {raw[:120]!r}")

        name, dtype, writable = parts[0], parts[1], parts[2]
        units = parts[3] if len(parts) > 3 else ""
        description = parts[4] if len(parts) > 4 else ""
        if len(parts) > 5:
            description = "\t".join(parts[4:])

        writable = writable.strip().lower()
        if writable not in ("y", "n"):
            raise SystemExit(f"expected y/n writable, got {writable!r} in {name!r}")

        rows.append(
            (
                name.strip(),
                dtype.strip(),
                writable,
                units.strip(),
                description.strip(),
            )
        )

    return header, rows


def prefix_for_name(name: str) -> str:
    segs = name.split("/")
    if len(segs) >= 2:
        return f"{segs[0]}/{segs[1]}/"
    return f"{segs[0]}/"


def build_prefix_index(rows: list[tuple[str, str, str, str, str]]) -> list[tuple[str, int, str, str]]:
    by_prefix: dict[str, list[str]] = defaultdict(list)
    for name, *_ in rows:
        by_prefix[prefix_for_name(name)].append(name)

    out: list[tuple[str, int, str, str]] = []
    for pref in sorted(by_prefix):
        names = sorted(by_prefix[pref])
        ex_a = names[0] if names else ""
        ex_b = names[1] if len(names) > 1 else ""
        out.append((pref, len(names), ex_a, ex_b))
    return out


def write_readme(
    path: Path,
    *,
    source_path: Path,
    header_line: str,
    row_count: int,
) -> None:
    meta = header_line.strip()
    # e.g. "2 1208 Wed Aug 16 20:19:08 2023"
    m = re.match(r"^(\d+)\s+(\d+)\s+(.+)$", meta)
    if m:
        fmt_ver, build, stamp = m.group(1), m.group(2), m.group(3).strip()
        build_summary = f"format version **{fmt_ver}**, build **{build}**, stamp `{stamp}`"
    else:
        build_summary = f"raw header: `{meta}`"

    body = f"""# X-Plane datarefs (local snapshot)

This folder holds a **static** export of stock X-Plane **dataref names** and metadata for local search (humans and agents). It does **not** include plugin- or aircraft-defined datarefs.

## Files

| File | Purpose |
|------|---------|
| `datarefs.csv` | Full catalog: `name`, `type`, `writable`, `units`, `description` |
| `prefix_index.md` | Row counts and example names grouped by `sim/<section>/` |
| `source/DataRefs.txt` | Pinned tab-separated source used to generate the CSV |

## Provenance

- **Source format:** Laminar Research `DataRefs.txt` (ships with X-Plane under `Resources/plugins/DataRefs.txt`).
- **This snapshot:** {build_summary} (from `{source_path.as_posix()}`).
- **Rows:** {row_count} datarefs.
- **Source file:** If you did not copy from your game folder, this file may match a public mirror (for example [XPlane2Blender `DataRefs.txt`](https://github.com/X-Plane/XPlane2Blender/blob/master/io_xplane2blender/resources/DataRefs.txt)); prefer **`Resources/plugins/DataRefs.txt` from your X-Plane 12 install** for an exact match to your build.

Prefer replacing `source/DataRefs.txt` with the file from **your** X-Plane 12 install when you want the list to match your exact simulator build, then regenerate:

```bash
python scripts/datarefs_txt_to_csv.py --input \"path/to/DataRefs.txt\"
```

## Limitations

- **Web API IDs** for datarefs are **session-local**; resolve names at runtime via the API.
- **Writable** in this file is the simulator’s declaration; the HTTP API may still reject writes (`dataref_is_readonly`, etc.).
- Third-party mirrors (e.g. XPlane2Blender) can lag the latest X-Plane patch; the install copy is authoritative.

## License / attribution

Dataref names and descriptions are part of X-Plane’s published developer materials. Use in accordance with Laminar Research’s terms for the simulator and SDK documentation.
"""
    path.write_text(body, encoding="utf-8")


def write_prefix_index(path: Path, index: list[tuple[str, int, str, str]]) -> None:
    lines = [
        "# Datarefs by prefix",
        "",
        "Grouped by `sim/<section>/`. See `datarefs.csv` for the full list.",
        "",
        "| Prefix | Count | Example | Example 2 |",
        "|--------|------:|---------|-----------|",
    ]
    for pref, count, a, b in index:
        lines.append(f"| `{pref}` | {count} | `{a}` | `{b or ''}` |")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    input_path = args.input
    if not input_path.is_file():
        raise SystemExit(f"input not found: {input_path}")

    header, rows = read_datarefs(input_path)

    args.csv_out.parent.mkdir(parents=True, exist_ok=True)
    with args.csv_out.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        w.writerow(["name", "type", "writable", "units", "description"])
        w.writerows(rows)

    try:
        src_display = input_path.relative_to(Path.cwd())
    except ValueError:
        src_display = input_path
    write_readme(
        args.readme_out,
        source_path=src_display,
        header_line=header,
        row_count=len(rows),
    )

    write_prefix_index(args.prefix_index_out, build_prefix_index(rows))

    print(f"wrote {len(rows)} rows -> {args.csv_out}")
    print(f"wrote {args.readme_out}")
    print(f"wrote {args.prefix_index_out}")


if __name__ == "__main__":
    main()
