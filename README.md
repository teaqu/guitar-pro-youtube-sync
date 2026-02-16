# Songsterr Downloader and Youtube Sync for Guitar Pro

Generate Guitar Pro tabs from Songsterr and sync them with real YouTube audio. Produces a `.gp` file with embedded audio and per-measure tempo mapping so your tab plays back perfectly in time with the original recording.

![Guitar Pro with synced backing track](screenshot.png)

## What It Does

Songsterr has crowd-sourced timing data that maps each measure of a song's tab to a specific timestamp in a YouTube video. This tool:

1. **Generates a Guitar Pro file** from Songsterr's tab data (all tracks, instruments, tunings, drum kits, etc.)
2. Fetches measure-level timing points from Songsterr's API
3. Downloads the corresponding YouTube audio via `yt-dlp`
4. Computes per-measure BPMs from the timing data
5. Embeds the audio and SyncPoint automations into the Guitar Pro file

The result is a `.gp` file you can open in Guitar Pro with a fully synced backing track -- every measure lines up with the real recording.

## Prerequisites

- **Python 3.10+**
- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** -- for downloading YouTube audio
- **[ffmpeg](https://ffmpeg.org/)** -- for audio conversion (used by yt-dlp)

## Installation

```bash
git clone https://github.com/teaqu/guitar-pro-youtube-sync.git
cd guitar-pro-youtube-sync
python -m venv .venv
source .venv/bin/activate
pip install requests
```

Make sure `yt-dlp` and `ffmpeg` are installed and available on your PATH:

```bash
# macOS
brew install yt-dlp ffmpeg

# Linux
pip install yt-dlp
sudo apt install ffmpeg

# Windows
pip install yt-dlp
# Download ffmpeg from https://ffmpeg.org/download.html
```

## Usage

### One-command sync

Pass a Songsterr URL or song ID. The GP file is generated automatically from Songsterr's tab data:

```bash
python sync.py --song "https://www.songsterr.com/a/wsa/gary-moore-parisienne-walkways-tab-s23063"
```

```bash
python sync.py --song 23063
```

This generates `Gary Moore - Parisienne Walkways.gp` and outputs a `Gary Moore - Parisienne Walkways_synced.gp` with the YouTube audio embedded and all measures tempo-mapped.

### Sync with your own GP file

If you already have the Guitar Pro file you'd like to sync instead of generating one. 

```bash
python sync.py --song 23063 --gp-file my-tab.gp
```

### List available videos

Some songs have multiple video sources (original, alternative, backing track). List them to pick the best one:

```bash
python sync.py --song 23063 --list-videos
```

### Use a specific video

```bash
python sync.py --song 23063 --video-index 2
```

### Generate a GP file only (no sync)

Use `gen-gp.py` directly to generate a Guitar Pro file from Songsterr without syncing:

```bash
python gen-gp.py --song 23063
python gen-gp.py --song 23063 -o output.gp
```

This fetches all tracks from Songsterr and produces a `.gp` file compatible with Guitar Pro 7/8, including correct instrument types, tunings, drum kits, track colors, and icons.

<details>
<summary>Example output</summary>

```
[1/5] Fetching song metadata...
Fetching song metadata from: https://www.songsterr.com/api/meta/23063
  Song: Gary Moore - Parisienne Walkways
  Latest revision: 5099457

[2/5] Fetching video points...
Fetching video points from: https://www.songsterr.com/api/video-points/23063/5099457/list
  Found 23 video entries

[3/5] Selecting video entry...
  Using entry 0: videoId=ZfgyFok56fE, feature=alternative, points=101

  Generating GP file from Songsterr...
  Tracks: 9
  Measures: 100
  Tempo: 88 BPM
  Notes: 3870 total, 271 unique
  Beats: 2994 total, 482 unique

[4/5] Downloading YouTube audio...
  Audio saved: .tmp_audio.mp3

[5/5] Syncing GP file...
  Original tempo: 88.0 BPM
  Measures: 100
  Time signatures: 6/8
  Embedding audio: .tmp_audio.mp3 (6.0 MB)

=== Sync Summary ===
  Measures: 100
  Video points: 101
  BPM range: 79.3 - 189.5
  Average BPM: 91.4

Saved: Gary Moore - Parisienne Walkways_synced.gp
Done!
```

</details>

## How It Works

### GP file generation (`gen-gp.py`)

1. Fetches song metadata and all track data from Songsterr's CDN
2. Converts Songsterr's JSON format into Guitar Pro's GPIF XML format (notes, beats, bars, rhythms, etc.)
3. Deduplicates notes and beats for compact file sizes
4. Handles instrument-specific details: drum kits with neutral clef and MIDI channel 10, string tunings, bends, slides, harmonics, etc.
5. Packages everything into a `.gp` ZIP archive using `blank.gp` as a template

### Audio sync (`sync.py`)

1. Fetches video points from `songsterr.com/api/video-points/{song_id}/{revision_id}/list` -- timestamps (in seconds) marking where each measure starts in the YouTube video
2. Downloads audio from YouTube using `yt-dlp` and converts to MP3
3. Computes per-measure BPMs by dividing the measure length (in quarter notes, derived from the time signature) by the duration between consecutive video points
4. Patches the `.gp` file (a ZIP containing XML) by injecting SyncPoint automations and embedding the MP3 as a backing track asset
