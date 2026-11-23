# OnTheSpot v2 PortableApps Builder Kit — b1r2

An **independent**, application-specific, source-based Windows PortableApps builder. It does not fork the upstream OnTheSpot project. GitHub Actions resolves a compatible stable v2+ release, builds its React frontend and Python backend with upstream locks, bundles a genuine Windows x64 Python runtime and necessary tools, compiles a native Win32 launcher, validates an independently generated PortableApps ZIP, and builds **one** installer via the shared Package Builder. Publishing is OFF unless explicitly selected.

> **Validation status:** Repository audit and 22 isolated unit tests completed in the authoring environment. The full Windows GitHub Actions build, actual runtime smoke, selected-engine installer compilation, real installation and upgrade testing **have not been executed by the authoring environment**. Run a test workflow before enabling publishing. The kit is a testable implementation, **not a verified successful Windows release**.

## Important upstream change

Starting in OnTheSpot v2, the application uses **FastAPI + React**: it is a locally hosted web application, not the old PyQt desktop GUI. The native launcher starts a local server on `127.0.0.1:6767`, opens your normal browser, and provides a visible **Stop OnTheSpot** window. Closing that window requests graceful server shutdown, with a 15-second bounded fallback if it hangs. This kit **intentionally skips v1.x legacy releases**; it cannot automatically transform a v1 desktop GUI to the incompatible v2 architecture. Docker is NOT needed to run the portable build.

Upstream documentation: https://github.com/ots-downloader/onthespot/blob/v2.0.5/docs/INSTALLATION.md

## Updating an existing b1r1 repository to b1r2

1. Open the existing `OnTheSpot-PortableApps-Builder` repository in GitHub Desktop.
2. Extract **all** files from this b1r2 ZIP over your existing working-tree files, preserving the `.git` directory and any local uncommitted work. The kit contains source only, no compiled application or user `Data` folder.
3. Review the changed files in GitHub Desktop, commit `Fix first-time release detection and preserve installer-only build identity (b1r2)`, then push.
4. Run **Build OnTheSpot PortableApps (Windows)** with **publish = false** first. Use the default `custom-nsis` engine for an initial test, or choose `official` explicitly to test that engine. Only publish after successful runtime and installation checks.
5. No new independent repository is needed for this update. Keep previous validated releases and user `Data` unchanged.

## Quick start for new GitHub Desktop repositories (no upstream fork)

1. In GitHub Desktop, select **File → New repository**. Name it `OnTheSpot-PortableApps-Builder` and choose your own local folder. Use an empty repository.
2. **Choose Public or Private** when publishing the new repository on GitHub. Do not change the visibility after the fact unless you intend to. Public repositories produce public releases; private repositories produce private releases.
3. Download and extract this **builder ZIP** into that new repository's local directory. The hidden `.github` folder must appear at repository root. Do not place a second wrapper folder around its contents.
4. In GitHub Desktop, enter the commit summary `Add OnTheSpot v2 portable source builder b1r2` and commit all source files. Select **Publish repository** and preserve your desired visibility.
5. On GitHub.com, open **Actions → Build OnTheSpot PortableApps (Windows)** → **Run workflow**.
6. Leave **upstream-version** empty for latest suitable stable v2+ release; leave **installer-engine** as **custom-nsis** to begin; keep **publish = false**. Click **Run workflow**.
7. When the job is complete and **green**, open its run summary. Under **Artifacts**, download `OnTheSpotPortable-test-<run ID>`; unzip it. This contains an independent PortableApps ZIP, the selected `.paf.exe` installer, checksums and provenance notes.
8. If the default engine tests successfully, optionally run another **test build** choosing **official**. It compiles actual PortableApps.com Installer **3.9.24** source through the shared Package Builder, not an installer-download wizard. Do not assume success from the default engine alone.
9. Only after checking runtime and upgrades, rerun with **publish = true**. Validated output goes to **your new repository → Releases**. Test artifacts are **not** uploaded when production publishing is enabled.
10. To extract without installation, unpack the **inner** `OnTheSpotPortable_vX.Y.Z_b1r2.zip` to a `PortableApps` folder and start `OnTheSpotPortable/OnTheSpotPortable.exe`. Or use the selected `.paf.exe` installer. The launcher requires no administrator permissions for normal usage.
11. On upgrade, stop the program, **back up the entire `Data` directory**, then upgrade/replace **App**, root launcher, metadata and **Other**. Never overwrite or delete `Data`, including empty folders and `Data/.managed-paths.json`.
12. To rebuild **only the installer**, choose **Actions → Rebuild OnTheSpot Installer Only (Windows)**. Provide **one**: an existing production `source-release-tag` **or** an existing successful test run's numeric `source-test-run-id`. Choose desired engine; leave publish false for first attempt. The existing ZIP's SHA-256 and build identity are verified. The application binaries are **not** rebuilt.

### Where the application stores files

| Path inside `OnTheSpotPortable` | What it contains | Upgrade policy |
| --- | --- | --- |
| `OnTheSpotPortable.exe` | Compiled Windows launcher, opens browser | Replaceable |
| `App/OnTheSpot/runtime` | Self-contained managed Windows Python | Replaceable |
| `App/OnTheSpot/code` | Actual OnTheSpot API code | Replaceable |
| `App/OnTheSpot/ui` | Compiled React interface | Replaceable |
| `App/OnTheSpot/tools` | FFmpeg, FFprobe, Deno | Replaceable |
| `Data/Config` | Config, encrypted account data and key, app logs | **Always preserve** |
| `Data/Cache` | Sessions, caches, cookies and statistics | **Always preserve** |
| `Data/Media/Music`, `Data/Media/Videos` | Downloaded files | **Always preserve** |
| `Data/Home`, `Data/Temp`, `Data/Environment` | Redirected user home, temporary files and other app-related runtime state | **Always preserve** |
| `Data/.managed-paths.json` | Removable-drive path relocation marker | **Always preserve** |

If you deliberately choose a **custom download folder outside `Data`**, the launcher **does not collect, delete or relocate it**. That custom host path remains your responsibility to back up. Portable-managed absolute paths are safely rewritten when the USB drive letter changes.

### Supported modes and installer engines

- This project is specifically **PORTABLEAPPS**. It creates one PortableApps ZIP plus one selected engine installer, not a native-only ZIP.
- **custom-nsis**: existing independent shared NSIS installer, not an official PortableApps.com installer.
- **official**: authentic reviewed PortableApps.com 3.9.24 source compiled using the shared action's bundled verified NSIS toolchain. It does **not** download or run a PortableApps installer EXE as a compiler.
- No silent fallback from `official` to `custom-nsis` is allowed.

Shared Package Builder: https://github.com/vhick/Portable-Package-Builder (verified v1.1.0 and **immutable r5 SHA** `9bf686ec29a46073ca3c27638e62862eb8cc9079`). Source API: `source-dir`, `output-dir`, `engine`, `running-exe`, `package-revision`, `timeout-seconds`. v1.0.0 remains available upstream as a **historical rollback reference**, but **its official engine uses the obsolete installer tool download interface** and must not replace r5 without a deliberate compatibility review.

Shared Publisher: https://github.com/vhick/portable-release-publisher (verified v1.1.1 and **immutable SHA** `cb64f86ac2d8c67506db5832de07f9ff58cbeaeb`). It receives only validated `.zip` / `.paf.exe` files, does a dry run, enforces unique engine-aware tags, and prunes older owned releases **only if manually opted in**.

## Automatic stable builds without untrusted self-updates

1. Inspect GitHub releases and choose latest full `vMAJOR.MINOR.PATCH` with major 2+, excluding drafts and prereleases.
2. Checkout exact upstream tag. Check compatibility with `api/pyproject.toml`, `api/uv.lock`, `ui/package-lock.json`, `Dockerfile`, config paths, FastAPI entrypoint and built UI layout. Fail **before expensive compilation** if it changed incompatibly.
3. Read upstream **Python major.minor**, **Node major** and **uv tool version** from project metadata/Dockerfile. Use **upstream locked package versions** (`uv sync --frozen`, `npm ci`). Intentionally allow only reviewed Python 3.12–3.14 and Node 22/24; unknown major versions require review, not guessed upgrades.
4. Build Windows x64 runtime plus UI; acquire explicitly named stable FFmpeg and upstream-selected Deno Windows binaries from trusted publishers, logging SHA-256. The FFmpeg source is the maintained `FFmpeg-Builds/FFmpeg-Builds` GPL Windows build repo (formerly BtbN); its rolling master asset may change between builds, so its exact downloaded checksum is recorded but full byte-for-byte reproducibility across different days is **not** guaranteed.
5. Add data bootstrap, Win32 launcher, app icon, source/build identity and metadata; validate ZIP by independent extraction and Windows process smoke.
6. Have the **shared** action build and check exactly one `.paf.exe`; verify engine sidecar and hash before optionally invoking the shared publisher.

**Known-good policy:** No application-specific OnTheSpot builder version is marked successful until a Windows build + actual install/upgrade is tested. Existing published releases are left untouched on failures. The optional **Manual Maintenance Check** never updates shared actions, toolchains, or app versions automatically.

## Runtime notes and limitations

- v2 OnTheSpot serves `127.0.0.1:6767` by default. `OnTheSpotPortable.exe --port 16800` changes it; `--no-browser` suppresses browser opening. No LAN binding is performed by default.
- System-wide registry, services and scheduled tasks are unnecessary. Native application environment overrides are used, so **TraceGuard is intentionally not implemented**. Empty directory trees under `Data` remain in place and are never harvested from unrelated host folders.
- External browsers can create their own cache, history or cookies in browser profiles. The launcher cannot portably redirect an unrelated browser. Windows DNS, security, prefetch and firewall traces may also exist. These are **not** falsely represented as fully removable.
- This app downloads content from third-party services. Use it only for downloads you are legally entitled to make and in compliance with applicable service conditions. A user's Spotify account has reportedly been locked after using this upstream project.
- Upstream 2.0.5 has inner metadata showing `2.0.4` in some files. Build identity uses the **actual release tag and commit**; it does not silently forge upstream config/UI versions. This discrepancy can appear in the application UI until upstream updates it.
- Encrypted credentials and their `credentials.key` are kept together in `Data/Config`. On a shared USB stick, **physical access may disclose those files**; encrypt your removable drive and protect your sessions.
- Package size can be large because the bundled Python, FFmpeg and frontend run without requiring Python or Node on the destination computer.
- The compiled native launcher displays a Stop button and owns the server process in a Windows Job Object. Force-killing the launcher closes the server; this is safer than leaving an uncontrolled background service. Test whether your antivirus and Windows version permit Windows Job Objects.
- **No actual production `.paf.exe` or Windows application binary is included in this builder source ZIP.** Those are created from upstream on GitHub Actions. The builder ZIP itself is not an installable application.

## b1r2 GitHub Actions fix (23 November 2026)

- Fixed first-time production builds failing at **Skip existing identical production release** when `gh release view` returned exit code 1 for a tag that did not yet exist. Under `pwsh`, this accidentally ended the step before compilation.
- Both primary build and installer-only workflows now use `scripts/probe_release.py` with the authenticated GitHub Releases API. A confirmed 404 release **and accessible repository** means proceed; a real existing release is skipped (build) or blocked (installer-only); authorization, rate-limit, and network errors fail visibly rather than being mistaken for a new release.
- Installer-only packages retain the original ZIP's **package revision** (b1r1 or b1r2) in release identity rather than silently relabeling application binaries when using a newer builder.
- The supplied user run selected `official` with publishing enabled. The error occurred before the official engine was called. **No Windows application compilation or installer validation has succeeded in that failed run**. Test with publishing disabled first.

## Source and licenses

OnTheSpot uses GPL-2.0; source: https://github.com/ots-downloader/onthespot/tree/v2.0.5 . The kit's independent C++ launcher is MIT; a compiled distribution must also satisfy licenses for FFmpeg, Python, Deno, uv-resolved Python dependencies, and UI npm dependencies. For redistribution, ensure you provide appropriate license texts, notices, and **corresponding source** where required (including GPL FFmpeg). Upstream links alone may not satisfy your legal obligations.

See `docs/SOURCE-AUDIT.md`, `docs/LOCAL-VALIDATION.md`, `docs/COMPATIBILITY-BASELINE.json`, `docs/TROUBLESHOOTING.md` and `docs/WINDOWS-ACCEPTANCE.md` for evidence, limitations and acceptance procedures.
