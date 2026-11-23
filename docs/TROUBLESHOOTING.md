# Troubleshooting and safe recovery

| Message or issue | Meaning | What to do |
| --- | --- | --- |
| `RELEASE_NOT_FOUND` (informational) | Target engine-specific tag does not exist yet | Expected for first production build. The check continues normally. |
| `RELEASE_PROBE_API_FAILED` / `RELEASE_REPOSITORY_ACCESS_FAILED` | GitHub API unavailable, token lacks access, or rate-limited | Inspect HTTP status; do not treat authorization/network failures as an absent release. |
| `PRODUCTION_RELEASE_ALREADY_EXISTS` | Target tag is already published | Use the existing release or a new verified build revision; never overwrite an immutable tag. |
| `NO_COMPATIBLE_STABLE_RELEASE` | No safe full v2+ tag matched | Check upstream releases; do not switch to legacy v1 automatically |
| `UPSTREAM_LAYOUT_CHANGED` | Required API/UI/lock file moved | Review upstream changelog; do not bypass the preflight blindly |
| `NODE_VERSION_UNTESTED` / `PYTHON_VERSION_UNTESTED` | Major toolchain moved beyond reviewed range | Review new requirements and test a new builder revision; no untested auto-adoption |
| `UPSTREAM_PORTABILITY_CHANGED` | Config override behavior changed | Audit the new config implementation; protect `Data` before changes |
| `NPM_CI_FAILED` | Frontend lock/dependencies unavailable or incompatible | Check upstream `ui/package-lock.json`, Node major, npm logs |
| `UPSTREAM_LOCKED_DEPENDENCY_INSTALL_FAILED` | uv lock or a Windows dependency failed | Check exact package name in log, PyPI wheel support and any pinned Git revision |
| `TRUSTED_RUNTIME_TOOL_FAILED` | Named FFmpeg/Deno release asset missing or changed | Inspect the trusted maintainer's assets; no arbitrary mirror fallback |
| `LAUNCHER_COMPILE_FAILED` | C++ toolchain or source compilation error | Inspect `Compile genuine Windows PE` log; Windows runner is expected to have VS2022 build tools |
| `PORTABLE_VALIDATION_FAILED` | Missing binaries, invalid metadata, corrupted ZIP or mismatch | Do not publish; inspect the specific path/engine. Preserve old release |
| `WINDOWS_RUNTIME_SMOKE_FAILED` | Local API/UI failed to start or leave portable config | Read real CI log, inspect dependencies and runtime; do not publish |
| `OFFICIAL_HELP_MISSING` / `OFFICIAL_HELP_INVALID` | Shared official engine rejected missing root HTML | Check `OnTheSpotPortable/help.html` beside launcher, rerun test |
| `OFFICIAL_SOURCE_MISSING` / `OFFICIAL_SOURCE_TAMPERED` | Bundled official 3.9.24 source pipeline isn't intact | Keep r5 pin; do not silently switch engine or fetch wizard installer |
| Port 6767 already used | Another local service is listening | Close other instance or use `OnTheSpotPortable.exe --port 16800` |
| Browser doesn't open | Browser association or profile issue | Open `http://127.0.0.1:6767` manually; process must remain running |
| Config won't load | Data config damaged, permissions, or upgrades | **Back up Data first**; do not delete `otsconfig.json` automatically |
| Media saved outside USB | Prior custom external path or legacy config | Verify Settings; custom external paths intentionally stay untouched |
| Existing engine-specific tag | Publisher blocks unsafe overwrite | Use existing release or increment builder revision after a real change |

**Rollback:** Close the launcher; make a full backup of `Data`, including hidden files and empty folders. Keep it intact; replace only application files from a previously known-working ZIP/installer. If an upstream release migrated its config/database irreversibly, restoring an older app **may also require an earlier Data backup**. Do not drop old config keys or overwrite `credentials.key` to force old releases to work.

**Diagnostics:** For startup problems inspect `Data/portable-startup-error.txt` and `Data/Config/logs/`. In GitHub Actions inspect the exact failed step and save its logs. Never publish, share, or paste unredacted `Data/Config/credentials.*`, OAuth tokens, private cookies, account details or full environment dumps.

No program should automatically move, delete, or claim ownership of an existing unrelated host profile. The bootstrap uses only `Data` directory env overrides and selective settings relocation.
