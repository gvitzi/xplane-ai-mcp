# X-Plane datarefs (local snapshot)

This folder holds a **static** export of stock X-Plane **dataref names** and metadata for local search (humans and agents). It does **not** include plugin- or aircraft-defined datarefs.

## Files

| File | Purpose |
|------|---------|
| `datarefs.csv` | Full catalog: `name`, `type`, `writable`, `units`, `description` |
| `prefix_index.md` | Row counts and example names grouped by `sim/<section>/` |
| `source/DataRefs.txt` | Pinned tab-separated source used to generate the CSV |

## Provenance

- **Source format:** Laminar Research `DataRefs.txt` (ships with X-Plane under `Resources/plugins/DataRefs.txt`).
- **This snapshot:** format version **2**, build **1208**, stamp `Wed Aug 16 20:19:08 2023` (from `refs/source/DataRefs.txt`).
- **Rows:** 5357 datarefs.
- **Checked-in source:** If you did not copy from your game folder, this file may match a public mirror (for example [XPlane2Blender `DataRefs.txt`](https://github.com/X-Plane/XPlane2Blender/blob/master/io_xplane2blender/resources/DataRefs.txt)); prefer **`Resources/plugins/DataRefs.txt` from your X-Plane 12 install** for an exact match to your build.

Prefer replacing `source/DataRefs.txt` with the file from **your** X-Plane 12 install when you want the list to match your exact simulator build, then regenerate:

```bash
python scripts/datarefs_txt_to_csv.py --input "path/to/DataRefs.txt"
```

## Limitations

- **Web API IDs** for datarefs are **session-local**; resolve names at runtime via the API.
- **Writable** in this file is the simulator’s declaration; the HTTP API may still reject writes (`dataref_is_readonly`, etc.).
- Third-party mirrors (e.g. XPlane2Blender) can lag the latest X-Plane patch; the install copy is authoritative.

## License / attribution

Dataref names and descriptions are part of X-Plane’s published developer materials. Use in accordance with Laminar Research’s terms for the simulator and SDK documentation.
