# Local validation evidence — 23 November 2026

**Executed in the authoring Linux container for b1r2:**

- Inspected `logs_122236620256.zip`: source builder tests and upstream resolver succeeded; GitHub Actions step **Skip existing identical production release** exited 1 before compilation. The step hid `gh release view` output, so its precise return condition could not be established from the log alone. The workflow improperly treated any exit code 1 as a missing release and inherited it as failure.
- Fixed build and installer-only release checks to use HTTP status-aware authenticated GitHub REST calls with strict errors and source-original revision tags. Added mocked 200 / release-404 / repository-404 / HTTP 403 / mismatched-release response cases.


- `python -m unittest discover -s tests -v`: **22 tests passed**.
- `python -m compileall -q scripts tests`: passed (Python syntax).
- Parsed all three GitHub Actions workflow YAML files using PyYAML: passed (syntax/parser only).
- Inspected verified upstream v2.0.5 Python, Docker and web application source, shared Package Builder v1.1.0 `action.yml` / shared scripts, and Publisher v1.1.1 `action.yml` / publisher scripts.
- Checked that publisher paths are relative, action pins are exact immutable commit IDs, builder requires genuine PE launcher, ZIP verification rejects path traversal, wrong checksums fail, and data-relocation unit regression passes.

**Not executed:** Windows C++ compilation, OnTheSpot locked Python dependency resolution on Windows, npm React build on Windows, actual FFmpeg/Deno acquisition, Python/Uvicorn server launch, real HTTPS service use, either installer engine, installation, upgrade, rollback or host-trace assessment. These are not represented as verified successes.

**Known-good production releases:** none have been demonstrated for this application-specific builder as of this audit. GitHub Actions is configured to withhold artifacts and publishing on failed validation.
