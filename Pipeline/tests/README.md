# Tests

A small pytest suite covering the parts of the pipeline where a silent
bug has real consequences — a message getting dropped, duplicated, or
mis-dated in someone's only copy of their chat history.

## Running

```
cd Pipeline
pip install -r requirements.txt --break-system-packages   # installs pytest too
python3 -m pytest tests/ -v
```

Fast inner loop, skipping the slower end-to-end test:

```
python3 -m pytest tests/ -v -m "not smoke"
```

## What's covered

- **`test_common.py`** — unit tests for `scripts/common.py`'s date/time
  parsing (the trickiest part: disambiguating day-vs-month order from
  ambiguous input), the three real WhatsApp export line formats, and
  the small helpers (`clean_line`, `resolve_mentions`,
  `extract_slot_key`, etc).
- **`test_merge.py`** — unit tests for `scripts/3_merge_export.py`'s
  chronological merge/dedup logic directly: new messages get added,
  exact duplicates get skipped, a re-synced "waiting for this
  message" placeholder is correctly recognized as already covered,
  and re-running the same merge twice adds nothing the second time
  (the "safe to re-run" guarantee in that script's own docstring).
- **`test_pipeline_smoke.py`** — an end-to-end test that actually
  shells out to `python3 control.py merge` / `reports` / `doctor`
  against the real `sample_data/`, in a throwaway copy of the whole
  repo, and checks every promised output file gets written. Marked
  `smoke` since it's slower (real subprocesses, real charts/PDFs).

## What's not covered yet

The `Tools/` analyzers (`chat_analyzer`, `arc_analyzer`) are only
exercised indirectly, through the smoke test actually running them
end-to-end and checking their outputs exist and aren't empty — their
internal stats/scoring logic doesn't have unit tests yet. That, and a
wider set of format-edge-case fixtures for `common.py`, are the most
useful next contributions here (see `CONTRIBUTING.md`).
