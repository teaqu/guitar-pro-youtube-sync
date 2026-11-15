## v1.2.1

- Fix exported Guitar Pro dead notes displaying as ordinary fretted notes (#5). Songsterr's per-note `dead` marking now produces Guitar Pro X noteheads, including individual dead strings within mixed chords, while preserving string positions and rhythms.
- Keep dead notes distinct from ordinary notes during deduplication, and from palm muting, rests, and ghost notes.
- Add regressions using the reported Faint example and validate mixed dead/normal chords in the packaged-app self-test.
- Verify feedpak exports preserve individual dead strings, timing, and sustain while keeping palm mutes separate.
- Fix CDN discovery after Songsterr renames minified variables, and refresh stale live-test metadata assumptions.
- Repair Linux builds by downloading and verifying the static FFmpeg distribution directly.

Executable filenames are unchanged.
