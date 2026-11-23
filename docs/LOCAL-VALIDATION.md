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

## b1r5 evidence from actual Windows b1r4 run
- `logs_122336351531.zip`: OnTheSpot v2.0.5 Python runtime and React successfully built, static ZIP SHA-256 `bee1a517fd909039c0de0d8a8d26117cc5b3f257129be240b941cd13d9eb6460`, Windows launcher smoke test passed (HTTP 200).
- Failure selected `official` engine in shared source-based 3.9.24 pipeline. NSIS reported `File: failed opening file ..\..\App\OnTheSpot\runtime\Lib\site-packages\cryptography-50.0.2.dist-info\sboms\cryptography-rust.cyclonedx.json` under deep checkout build output.
- Shared action `action.yml` permits absolute `output-dir`; `scripts/build.ps1` places `/_upb_work/official` under it; `scripts/build-official.ps1` copies staging to `/isolated-source/<app>` and calls the authentic NSIS compiler. Root of runner temporary drive used as shallow build directory in b1r5.
- Confirm b1r5 local unit tests, YAML parsing, source file checksum list and ZIP archive integrity before uploading; official Windows execution and installer installation are *not yet tested* for b1r5.

### b1r5 local regression (23 November 2026)
- `python -m unittest discover -s tests -v`: **37 tests passed** (32 earlier tests plus five new installer-path/output safety tests).
- `python -m compileall -q scripts tests`: passed.
- Parsed all three GitHub Actions workflows as YAML, confirmed shared compiler calls receive the short absolute directory emitted by `shortpath`, and verified verified-output copying occurs after installer validation.
- Generated and verified `SOURCE-MANIFEST.sha256` and the source ZIP CRC checks.
- No new Windows Actions run was performed for **b1r5**. Success of `official` NSIS compilation, actual installer launch, reinstallation, upgrade and rollback remain unverified.
