# guitar-pro-youtube-sync
Generate Guitar Pro tabs from Songsterr and sync them with YouTube audio. Produces a `.gp` file with embedded audio and per-measure tempo mapping so your tab plays back in time with YouTube.

![Guitar Pro with synced backing track](assets/screenshot.png)

## Download

Pre-built executables are available:

**[Download the latest release](https://github.com/teaqu/guitar-pro-youtube-sync/releases/latest)**

| Platform | File |
|----------|------|
| Windows | `guitar-pro-sync-windows-x86_64.exe` |
| macOS (Apple Silicon) | `guitar-pro-sync-macos-arm64.zip` |
| Linux | `guitar-pro-sync-linux-x86_64.zip` |

Download and extract, then run and follow the prompts. Everything (Python, yt-dlp, ffmpeg) is bundled inside the executable.

> **macOS:** You may see "Apple could not verify this app." Right-click the file, select **Open**, then click **Open** again to bypass Gatekeeper.
>
> **Windows:** Windows Defender or SmartScreen may flag the download. This is a common false positive with PyInstaller-built executables. Click **More info** → **Run anyway**.

## What It Does

Songsterr has timing data that maps each measure of a song's tab to a specific timestamp in a YouTube video. This tool:

1. Generates a Guitar Pro file from Songsterr's tab data and timing points
2. Downloads the corresponding YouTube audio via `yt-dlp`
3. Embeds the audio and SyncPoint automations into the Guitar Pro file

The result is a `.gp` file you can open in Guitar Pro with a synced backing track.

## Development Setup

If you want to run from source instead of the pre-built executable:

### Prerequisites

- **Python 3.10+**
- **[ffmpeg](https://ffmpeg.org/)** -- for audio conversion

### Installation

```bash
git clone https://github.com/teaqu/guitar-pro-youtube-sync.git
cd guitar-pro-youtube-sync
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Make sure `ffmpeg` is installed and available on your PATH:

```bash
# macOS
brew install ffmpeg

# Linux
sudo apt install ffmpeg

# Windows - download from https://ffmpeg.org/download.html
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

 You can also export the gp file with a plus account on Songsterr which may work better than generating one with this script. If you already have the Guitar Pro file you'd like to sync that instead:

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
I have only tested this with the default track so unsure how well this works.

### Use browser cookies (if YouTube blocks yt-dlp)

If yt-dlp gets blocked by YouTube, you can use cookies from your browser:

```bash
python sync.py --song 23063 --cookies chrome
```

Supported browsers: `chrome`, `firefox`, `safari`, `edge`, `brave`, `opera`, `vivaldi`

### Generate a GP file only (no sync)

If you don't want the audio you can also use use `gen_gp.py` directly to generate a Guitar Pro file from Songsterr without audio syncing:

```bash
python gen_gp.py --song 23063
python gen_gp.py --song 23063 -o output.gp
```

### Example output

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

## How It Works

### GP file generation (`gen_gp.py`)

1. Fetches song metadata and all track data from Songsterr
2. Converts Songsterr's JSON format into Guitar Pro's GPIF XML format (notes, beats, bars, rhythms, etc.)
3. Deduplicates notes and beats for compact file sizes
4. Handles instrument-specific details: drum kits with neutral clef and MIDI channel 10, string tunings, bends, slides, harmonics, etc.
5. Packages everything into a `.gp` ZIP archive using `blank.gp` as a template

### Audio sync (`sync.py`)

1. Fetches video points from `songsterr.com/api/video-points/{song_id}/{revision_id}/list` -- timestamps (in seconds) marking where each measure starts in the YouTube video
2. Downloads audio from YouTube using `yt-dlp` and converts to MP3
3. Computes per-measure BPMs by dividing the measure length (in quarter notes, derived from the time signature) by the duration between consecutive video points
4. Patches the `.gp` file (a ZIP containing XML) by injecting SyncPoint automations and embedding the MP3 as a backing track asset

## Testing

The project includes test suites for `sync.py` and `gen_gp.py`:

```bash
# Install test dependencies first
source .venv/bin/activate
pip install -r tests/requirements-test.txt

# Run all tests
pytest

# Run tests excluding slow ones (no audio download)
pytest -m "not slow"

# Run tests with verbose output
pytest -v

# Run tests with coverage report
pytest tests/ --cov=. --cov-report=html --cov-report=term

# Run specific test file
pytest tests/test_sync.py -v
pytest tests/test_gen_gp.py -v
pytest tests/test_integration.py -v

# Run only unit tests (fast, no network required)
pytest tests/test_sync.py tests/test_gen_gp.py -v

# Run only integration tests (slower, requires network)
pytest tests/test_integration.py -v -m integration
```