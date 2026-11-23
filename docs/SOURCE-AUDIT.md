# OnTheSpot v2.0.5 source audit — 23 November 2026

| Topic | Evidence found | Packaging decision |
| --- | --- | --- |
| Stable upstream | GitHub release `v2.0.5` dated 17 Nov 2026 | Dynamic full, non-prerelease v2+ resolver; reject v1 legacy |
| Application | Dockerfile uses Python 3.12 backend, Node 22 React frontend, and single FastAPI/Uvicorn process | Bundle exact production frontend and Python API on Windows, launch local browser |
| Python package | `api/pyproject.toml` and `api/uv.lock`; `librespot` pinned to Git through `tool.uv.sources` | `uv sync --frozen --no-dev --no-install-project`; copy locked installed dependencies |
| npm | `ui/package.json`, `ui/package-lock.json`, Vite build | `npm ci` and `npm run build` using Node major from Dockerfile |
| Toolchain | Dockerfile pins uv 0.11.33 and Deno 2.9.5 at inspected tag | Resolve from upstream Dockerfile, verified against supported majors |
| Media conversion | Dockerfile uses apt FFmpeg; app checks `FFMPEG_PATH` | Package trusted FFmpeg + FFprobe Windows binary and set env before config imports |
| Config | `api/src/onthespot/otsconfig.py` `ONTHESPOTDIR` | Redirect to `Data/Config`; never harvest host profile |
| Cache | `ONTHESPOTCACHEDIR`, fallback under config | Redirect to `Data/Cache`; preserve empty trees |
| Logging and sessions | `otsconfig.py` under config/cache | Keep under Data and preserve across upgrades |
| Credentials | `credentials.py` Fernet encryption with `credentials.key` beside `credentials.enc` | Keep both under `Data/Config` without resetting or replacing |
| Downloads | `otsconfig_default.json` keys `audio_download_path`, `video_download_path`, and `download_profiles` | Initialize inside `Data/Media`; repair only path values previously managed under old Data root |
| Exports | `export_locations.py` defaults to user home unless set | Redirect `USERPROFILE`/`HOME` and Windows appdata; preserve custom export settings |
| Web UI | `main.py` reads `ONTHESPOT_WEBUI_DIST` and mounts built React UI | Set variable to bundled `App/OnTheSpot/ui`, bind 127.0.0.1 |
| Windows service/driver | No installation requirement in official v2 source instructions | No host service/driver/autostart implementation |
| Child lifecycle | Uvicorn is single process; internal workers may start | Native Windows launcher signals a graceful-stop event, then bounds shutdown with a Job Object; child termination smoke tests |
| Licensing | GPL-2.0 repository license | Copy upstream GPL text, provide source/provenance, review bundled tool licenses |
| Binary assets | Docker provides Linux images; no proven Windows v2 binary packaging in audit | Build source on Windows; do not download Linux Docker image as Windows application |
| Upstream version mismatch | `api/pyproject.toml` version 2.0.4 inside release 2.0.5 | Record actual GitHub tag and inner version separately; do not falsify either |
| Shared package builder | v1.1.0 source action has `engine`, `source-dir`, `output-dir`, etc. GitHub shows r5 commit | Pin verified immutable r5 `9bf686ec29a46073ca3c27638e62862eb8cc9079` |
| Official installer source | shared `scripts/build-official.ps1` verifies 3.9.24.0 bundled source and preflights `help.html` | No duplicated compiler tooling, no downloaded GUI installer EXE |
| Publisher | v1.1.1, `files`, `tag`, `release-title`, `tag-prefix`, `keep-releases`, `prune`, `dry-run` | Pin immutable `cb64f86ac2d8c67506db5832de07f9ff58cbeaeb` |

**Verified code references** (read-only):

- https://github.com/ots-downloader/onthespot/releases/tag/v2.0.5
- https://raw.githubusercontent.com/ots-downloader/onthespot/v2.0.5/Dockerfile
- https://raw.githubusercontent.com/ots-downloader/onthespot/v2.0.5/api/pyproject.toml
- https://raw.githubusercontent.com/ots-downloader/onthespot/v2.0.5/api/src/onthespot/otsconfig.py
- https://raw.githubusercontent.com/ots-downloader/onthespot/v2.0.5/api/src/onthespot/otsconfig_default.json
- https://raw.githubusercontent.com/ots-downloader/onthespot/v2.0.5/api/src/onthespot/credentials.py
- https://raw.githubusercontent.com/ots-downloader/onthespot/v2.0.5/api/src/onthespot/main.py
- https://raw.githubusercontent.com/ots-downloader/onthespot/v2.0.5/docs/INSTALLATION.md
- https://github.com/vhick/Portable-Package-Builder/releases/tag/v1.1.0
- https://raw.githubusercontent.com/vhick/Portable-Package-Builder/v1.1.0/action.yml
- https://raw.githubusercontent.com/vhick/Portable-Package-Builder/v1.1.0/scripts/build-official.ps1
- https://github.com/vhick/portable-release-publisher/releases/tag/v1.1.1

## Evidence categories

**Completed:** Code-level inspection of the above named upstream paths, verified shared action inputs, SHA discovery, and local unit regressions.

**Pending actual Windows CI:** Locked uv environment resolution on Windows, managed Python relocation, React compilation, FFmpeg/Deno acquisition, C++ launcher compilation, full staging, real local web-UI process smoke, selected NSIS engine compilation and validation.

**Pending manual acceptance:** Real clean install, reinstall, upgrade over existing installation, data preservation after restart, custom download-path preservation, user-authenticated service features, removal of obsolete binaries, antivirus review, repeated USB drive letter relocation, rollback after config migration.

A clean compiler exit is not presented as proof of any of these pending outcomes.
