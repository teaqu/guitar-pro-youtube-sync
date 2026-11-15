#!/usr/bin/env bash
set -euo pipefail

# Static LGPL build: avoid setup-ffmpeg's dependency on a third-party README.
build=ffmpeg-n8.1-latest-linux64-lgpl-8.1
archive="$build.tar.xz"
base=https://github.com/FFmpeg-Builds/FFmpeg-Builds/releases/download/latest
mkdir -p "$RUNNER_TEMP/ffmpeg-static"
cd "$RUNNER_TEMP/ffmpeg-static"
curl --fail --location --retry 3 "$base/$archive" --output "$archive"
curl --fail --location --retry 3 "$base/checksums.sha256" --output checksums.sha256
sha256sum --check --ignore-missing checksums.sha256
tar -xJf "$archive"
"$build/bin/ffmpeg" -version
"$build/bin/ffprobe" -version
echo "$PWD/$build/bin" >> "$GITHUB_PATH"
