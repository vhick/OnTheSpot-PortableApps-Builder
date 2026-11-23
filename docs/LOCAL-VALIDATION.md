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

## b1r3 local regression (23 November 2026)
- Inspected `logs_122241030336.zip`: b1r2 release probe succeeded, upstream checkout v2.0.5 succeeded, source preflight succeeded, Node / uv / Pillow setup succeeded; `scripts/stage.py init` stopped at the old icon discovery rule.
- Source of existing README repository-logo reference confirmed at https://raw.githubusercontent.com/ots-downloader/onthespot/v2.0.5/README.md. That reference does not prove a usable logo file exists in every release checkout.
- New image-source tests cover explicitly labeled fallback artwork, multiple logos, nonexistent README target, alternate app asset, safe README hints, traversal rejection, service exclusion, corrupt images and absence of matching artwork.
- Windows compiler, actual v2.0.5 stage with checked-out full source, selected installer and runtime still not exercised locally; GitHub Actions must confirm.

- b1r3 moves the pre-existing pinned Pillow setup to **before** regression tests (not installed twice). The eight added image-validation tests would otherwise fail at the first workflow stage on clean Windows runners.

## b1r4 regression — Windows Actions log uploaded 23 November 2026

- Observed `logs_122256383085.zip`: 30 tests ran; 4 failed on Windows with `WindowsPath('C:/Users/runneradmin/...') != WindowsPath('C:/Users/RUNNER~1/...')`, all from icon asset tests. The failures were in regression tests, before the resolver fetched upstream source or application binaries compiled.
- Root cause: temporary paths use Windows 8.3 short names while `Path.resolve()` canonicalizes to long path names. This is a documented Python/Windows path issue.
- Changed four tests to `chosen.samefile(expected)` for actual file identity; added one explicit aliased path regression; application icon selection code was not changed.
- Run all 32 tests locally, compile Python sources, parse workflows, validate final archive and source checksums. Windows tests still pending.

- Additional workflow consistency fix: published build releases now include the ZIP checksum manifest required by the existing installer-only source recovery; verified with regression coverage. No shared publisher logic was duplicated.
