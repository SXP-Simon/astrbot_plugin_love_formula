# Testing and generated artifact policy

This plugin currently has lightweight verification scripts under `tests/` rather than a full pytest suite. This document records how to run them and how to classify generated files so that runtime data is not accidentally committed.

## Verification scripts

From the repository root, run the scripts directly with Python:

```bash
python tests/mock_verification.py
python tests/verify_repeat_fix.py
```

These checks are intended to be safe local smoke tests. They should not require real group data, tokens, or production AstrBot state.

## Sample card rendering

`tests/render_sample_card.py` is used to render a representative diagnostic card for visual inspection.

```bash
python tests/render_sample_card.py
```

If the renderer writes temporary HTML/PNG files, prefer writing them to `tests/output/`, which is ignored by git. If an output image or HTML file is intentionally used as a baseline snapshot or README/documentation asset, place it in a clearly named path such as `tests/snapshots/` or `docs/assets/` and document how it was generated.

## Runtime database policy

`love_formula.db`-style SQLite files are runtime/local state by default. They may contain group or user-derived data and can create noisy diffs. New runtime database files and SQLite sidecar files are ignored via `.gitignore`:

- `*.db`
- `*.sqlite`
- `*.sqlite3`
- `*.db-journal`
- `*.db-wal`
- `*.db-shm`

If a database is deliberately committed as a fixture, it should be moved to a fixture path, scrubbed of real user data, and accompanied by documentation explaining its purpose and refresh procedure.

## Current tracked artifacts

At the time this policy was added, the repository already tracked `love_formula.db`, `tests/test_output.html`, and `tests/test_output.png`. This change does not remove those files. Maintainers should decide in a follow-up whether they are fixtures/snapshots to keep, documentation assets to move, or local artifacts to remove from version control.
