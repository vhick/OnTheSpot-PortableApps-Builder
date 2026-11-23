# Windows acceptance checklist — required before public production publishing

Treat each as **Not Tested** until manually demonstrated. Save the results in your own repository; do not claim they were done by this source kit.

- [ ] Build `custom-nsis` on Windows Actions with `publish=false`; ZIP, launcher PE, UI, and .paf.exe pass validation.
- [ ] Build `official` separately with `publish=false`; verify source-based 3.9.24 compile and correct provenance.
- [ ] Extract ZIP into an ordinary directory with spaces and a non-ASCII path; launch app and open local web UI.
- [ ] Verify server binds only 127.0.0.1; test start/stop, browser opening, default/custom port, and duplicate-start rejection.
- [ ] Confirm `Data/Config`, `Data/Cache`, `Data/Media/Music`, `Data/Media/Videos` are created and persist after shutdown.
- [ ] Create an empty nested folder inside `Data`; verify it survives moving ZIP/package directory and upgrading.
- [ ] Move application from D: to E: (or copy to another folder); verify previous portable-managed paths update, downloads remain accessible, custom external paths are untouched.
- [ ] Authenticate an authorized service account; restart and confirm accounts, encrypted store + key, cache and settings persist.
- [ ] Download only content you are permitted to; test a supported format requiring FFmpeg and a video path requiring Deno.
- [ ] Install clean via custom installer; verify root launcher and complete files in target folder.
- [ ] Install clean via official installer separately; verify root launcher and complete files.
- [ ] Reinstall the same app over an existing Data folder; verify no user data is deleted or overwritten.
- [ ] Upgrade with downloaded files, custom profiles, empty folders and credentials present; verify obsolete binary replacement without deleting user files.
- [ ] Run installer-only from a verified test run and/or published ZIP; confirm app binary hashes match original ZIP and do not rebuild.
- [ ] Test launcher forcibly terminated; ensure Python/Uvicorn child server stops and existing Data is retained.
- [ ] Test `Data` read-only or corrupt config; failure must preserve files rather than reset or harvest a host profile.
- [ ] Restore the previous known-good app build; document whether any Data schema changes prevent older releases from running.
- [ ] Verify independent ZIP SHA-256, selected-engine EXE signature/provenance and GitHub release asset integrity.
- [ ] Review license compliance (OnTheSpot GPL-2.0, FFmpeg GPL, bundled dependencies) and source distribution/notice obligations.
- [ ] Check Windows security scanner findings manually; no claim of code signing or guaranteed AV acceptance.

Record **PASS / FAIL / NOT TESTED**, Windows edition, source version, build revision, installer engine, time, and any attached error logs. A failed item blocks public production publishing until understood.
