# Local validation evidence — 23 November 2026

**Executed in the authoring Linux container:**

- `python -m unittest discover -s tests -v`: **14 tests passed**.
- `python -m compileall -q scripts tests`: passed (Python syntax).
- Parsed all three GitHub Actions workflow YAML files using PyYAML: passed (syntax/parser only).
- Inspected verified upstream v2.0.5 Python, Docker and web application source, shared Package Builder v1.1.0 `action.yml` / shared scripts, and Publisher v1.1.1 `action.yml` / publisher scripts.
- Checked that publisher paths are relative, action pins are exact immutable commit IDs, builder requires genuine PE launcher, ZIP verification rejects path traversal, wrong checksums fail, and data-relocation unit regression passes.

**Not executed:** Windows C++ compilation, OnTheSpot locked Python dependency resolution on Windows, npm React build on Windows, actual FFmpeg/Deno acquisition, Python/Uvicorn server launch, real HTTPS service use, either installer engine, installation, upgrade, rollback or host-trace assessment. These are not represented as verified successes.

**Known-good production releases:** none have been demonstrated for this application-specific builder as of this audit. GitHub Actions is configured to withhold artifacts and publishing on failed validation.
