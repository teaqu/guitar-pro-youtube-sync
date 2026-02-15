# guitar-pro-youtube-sync

Sync Guitar Pro tabs with real YouTube audio using Songsterr's timing data. Produces a `.gp` file with embedded audio and per-measure tempo mapping so your tab plays back perfectly in time with the original recording.

## What It Does

Songsterr has crowd-sourced timing data that maps each measure of a song's tab to a specific timestamp in a YouTube video. This tool uses that data to:

1. Fetch measure-level timing points from Songsterr's API
2. Download the corresponding YouTube audio via `yt-dlp`
3. Compute per-measure BPMs from the timing data
4. Embed the audio and SyncPoint automations into a Guitar Pro 7/8 file

The result is a `.gp` file you can open in Guitar Pro with a fully synced backing track -- every measure lines up with the real recording.

## Prerequisites

- **Python 3.10+**
- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** -- for downloading YouTube audio
- **[ffmpeg](https://ffmpeg.org/)** -- for audio conversion (used by yt-dlp)
- **A Guitar Pro 7/8 file (.gp)** for the song you want to sync

### Getting a .gp File

You need a Guitar Pro file to sync against. You can download `.gp` files from Songsterr with a plus account or using [songsterr-downloader](https://github.com/Metaphysics0/songsterr-downloader).

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

### Basic sync

```bash
python sync.py --song <SONGSTERR_SONG_ID> --gp-file <path_to_file.gp>
```

The Songsterr song ID is the number at the end of a Songsterr URL. For example, `https://www.songsterr.com/a/wsa/gary-moore-parisienne-walkways-tab-s23063` has song ID **23063**.

```bash
python sync.py --song 23063 --gp-file parisienne-walkways.gp
```

This outputs a `parisienne-walkways_synced.gp` file in the same directory with the YouTube audio embedded and all measures tempo-mapped.

### List available videos

Some songs have multiple video sources (original, alternative, backing track). List them to pick the best one:

```bash
python sync.py --song 23063 --list-videos
```

### Use a specific video

```bash
python sync.py --song 23063 --gp-file song.gp --video-index 2
```

## How It Works

1. **Fetches metadata** from `songsterr.com/api/meta/{song_id}` to get the latest revision
2. **Fetches video points** from `songsterr.com/api/video-points/{song_id}/{revision_id}/list` -- an array of timestamps (in seconds) marking where each measure starts in the YouTube video
3. **Downloads audio** from YouTube using `yt-dlp` and converts to MP3
4. **Computes BPMs** for each measure by dividing the measure length (in quarter notes, derived from the time signature) by the duration between consecutive video points
5. **Patches the .gp file** (which is a ZIP containing XML) by injecting SyncPoint automations and embedding the MP3 as a backing track asset

The output file is a standard Guitar Pro 7/8 file that opens normally in Guitar Pro with the backing track ready to go.

## Finding Songsterr Song IDs

- Go to [songsterr.com](https://www.songsterr.com) and search for a song
- The song ID is the number at the end of the URL: `tab-s{SONG_ID}`
- Or use the Songsterr API directly: `https://www.songsterr.com/api/songs?pattern=artist+song`
