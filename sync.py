#!/usr/bin/env python3
"""
Songsterr → Fully Synced GP File Generator

Takes a Songsterr song ID, downloads video points and YouTube audio,
then retimes a Guitar Pro file to match the real YouTube audio timing.

Usage:
    python sync.py --song 23063 --gp-file original.gp
    python sync.py --song 23063 --list-videos
"""

import argparse
import hashlib
import json
import re
import subprocess
import sys
import uuid
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import requests


def fetch_video_points(song_id: int, revision_id: int) -> list[dict]:
    """Fetch video points JSON from Songsterr API."""
    url = f"https://www.songsterr.com/api/video-points/{song_id}/{revision_id}/list"
    print(f"Fetching video points from: {url}")
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    print(f"  Found {len(data)} video entries")
    return data


def fetch_song_meta(song_id: int) -> dict:
    """Fetch song metadata from Songsterr API."""
    url = f"https://www.songsterr.com/api/meta/{song_id}"
    print(f"Fetching song metadata from: {url}")
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


def select_video_entry(entries: list[dict], video_index: int | None = None) -> dict:
    """Select which video entry to use for timing.

    Priority: manual index > default (feature=None) > universal alternative > alternative > backing > first.
    The default entry (feature=None) is the original video shown on the Songsterr website.
    """
    if video_index is not None:
        if video_index < len(entries):
            entry = entries[video_index]
            print(f"  Using entry {video_index}: videoId={entry['videoId']}, feature={entry.get('feature')}, points={len(entry['points'])}")
            return entry
        else:
            print(f"  WARNING: video_index {video_index} out of range, falling back to auto-select")

    # Prefer the default Songsterr video (feature is None)
    defaults = [e for e in entries if e.get("feature") is None]
    if defaults:
        entry = defaults[0]
        print(f"  Auto-selected default video: videoId={entry['videoId']}, points={len(entry['points'])}")
        return entry

    alternatives = [e for e in entries if e.get("feature") == "alternative" and e.get("status") == "done"]
    universal = [e for e in alternatives if e.get("countries") == ["All"]]
    if universal:
        entry = universal[0]
        print(f"  Auto-selected universal alternative: videoId={entry['videoId']}, points={len(entry['points'])}")
        return entry

    if alternatives:
        entry = alternatives[0]
        print(f"  Auto-selected alternative: videoId={entry['videoId']}, points={len(entry['points'])}")
        return entry

    backings = [e for e in entries if e.get("feature") == "backing" and e.get("status") == "done"]
    if backings:
        entry = backings[0]
        print(f"  Auto-selected backing: videoId={entry['videoId']}, points={len(entry['points'])}")
        return entry

    entry = entries[0]
    print(f"  Fallback to first entry: videoId={entry['videoId']}, points={len(entry['points'])}")
    return entry


def download_youtube_audio(video_id: str, output_path: Path, trim_start: float = 0.0) -> Path:
    """Download YouTube video and extract MP3 audio.

    Args:
        trim_start: Trim audio to start at this timestamp (seconds).
                    Used to skip the video intro before measure 1.
    """
    if output_path.exists():
        print(f"  Audio already exists: {output_path}")
        return output_path

    url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"Downloading YouTube audio: {url}")

    # Download to a temp name first, then rename
    temp_template = str(output_path.parent / f".dl_audio.%(ext)s")
    cmd = [
        "yt-dlp",
        "-x",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "-o", temp_template,
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        print(f"  yt-dlp stderr: {result.stderr}")
        raise RuntimeError(f"yt-dlp failed with exit code {result.returncode}")

    # Find the downloaded file and rename to desired output
    for f in output_path.parent.glob(".dl_audio.*"):
        if f.suffix == ".part":
            continue
        if f.suffix != ".mp3":
            subprocess.run(["ffmpeg", "-i", str(f), "-b:a", "320k", str(output_path)],
                           capture_output=True, timeout=120)
            f.unlink()
        else:
            f.rename(output_path)
        break

    # Trim audio to start at measure 1 (skip video intro)
    if trim_start > 0 and output_path.exists():
        trimmed = output_path.parent / ".tmp_trimmed.mp3"
        print(f"  Trimming audio: skipping first {trim_start:.2f}s of video intro")
        trim_result = subprocess.run(
            ["ffmpeg", "-y", "-ss", str(trim_start), "-i", str(output_path),
             "-c", "copy", str(trimmed)],
            capture_output=True, timeout=120,
        )
        if trim_result.returncode == 0 and trimmed.exists():
            trimmed.rename(output_path)
        elif trimmed.exists():
            trimmed.unlink()

    print(f"  Audio saved: {output_path}")
    return output_path


def find_gp_file(search_dir: Path) -> Path | None:
    """Look for an existing GP file in a directory."""
    for ext in (".gp", ".gp8", ".gpx"):
        for f in search_dir.glob(f"*{ext}"):
            if "synced" not in f.stem:
                return f
    return None


def parse_time_signature(time_str: str) -> tuple[int, int]:
    """Parse time signature string like '6/8' into (numerator, denominator)."""
    parts = time_str.split("/")
    return int(parts[0]), int(parts[1])


def measure_length_in_quarter_notes(time_str: str) -> float:
    """Calculate measure length in quarter notes from time signature string."""
    num, denom = parse_time_signature(time_str)
    return num * (4.0 / denom)


def compute_bpms(
    time_signatures: list[str],
    points: list[float],
) -> list[float]:
    """Compute BPM per measure using time signature strings and video points."""
    num_measures = len(time_signatures)
    num_points = len(points)

    if num_points < num_measures:
        print(f"  WARNING: {num_points} points < {num_measures} measures. Will extrapolate last measures.")
    elif num_points > num_measures:
        print(f"  INFO: {num_points} points > {num_measures} measures. Extra points will be ignored.")

    bpms = []

    for i in range(num_measures):
        quarter_notes = measure_length_in_quarter_notes(time_signatures[i])

        if i < num_points - 1:
            duration_seconds = points[i + 1] - points[i]
        elif i < num_points:
            bpms.append(bpms[-1] if bpms else 120.0)
            continue
        else:
            bpms.append(bpms[-1] if bpms else 120.0)
            continue

        if duration_seconds <= 0:
            bpms.append(bpms[-1] if bpms else 120.0)
            continue

        bpm = quarter_notes * 60.0 / duration_seconds
        bpm = max(10.0, min(999.0, bpm))
        bpms.append(round(bpm, 2))

    return bpms


def generate_asset_sha1(mp3_data: bytes) -> str:
    """Generate a SHA1-based UUID string for the MP3 asset (matching GP8 format)."""
    sha1 = hashlib.sha1(mp3_data).hexdigest()
    return str(uuid.UUID(sha1[:32]))



# GP8 internally normalises all audio to 44100 Hz for SyncPoint frame calculations,
# regardless of the MP3's actual sample rate.
GP8_INTERNAL_SAMPLE_RATE = 44100


def get_original_tempo(root: ET.Element) -> float:
    """Extract the original tempo from the GP file's existing Tempo automation."""
    master_track = root.find("MasterTrack")
    automations = master_track.find("Automations")
    if automations is not None:
        for auto in automations:
            type_elem = auto.find("Type")
            if type_elem is not None and type_elem.text == "Tempo":
                value = auto.find("Value")
                if value is not None and value.text:
                    return float(value.text.split()[0])
    return 120.0


def _build_automations_xml(original_tempo: float, bpms: list[float], points: list[float], embed_audio: bool) -> str:
    """Build the Automations XML block as a string."""
    lines = ["<Automations>"]

    # Single Tempo automation
    lines.append(f"""<Automation>
<Type>Tempo</Type>
<Linear>false</Linear>
<Bar>0</Bar>
<Position>0</Position>
<Visible>true</Visible>
<Value>{round(original_tempo)} 2</Value>
</Automation>""")

    # SyncPoint automations (only when embedding audio)
    if embed_audio and points:
        bar0_time = points[0]
        prev_modified = None
        for i in range(min(len(bpms), len(points))):
            modified_tempo = round(bpms[i], 5)
            if prev_modified is not None and abs(modified_tempo - prev_modified) < 0.5:
                continue
            prev_modified = modified_tempo
            frame_offset = round((points[i] - bar0_time) * GP8_INTERNAL_SAMPLE_RATE)
            lines.append(f"""<Automation>
<Type>SyncPoint</Type>
<Linear>false</Linear>
<Bar>{i}</Bar>
<Position>0</Position>
<Visible>true</Visible>
<Value>
<BarIndex>{i}</BarIndex>
<BarOccurrence>0</BarOccurrence>
<ModifiedTempo>{modified_tempo}</ModifiedTempo>
<OriginalTempo>{round(original_tempo)}</OriginalTempo>
<FrameOffset>{frame_offset}</FrameOffset>
</Value>
</Automation>""")

    lines.append("</Automations>")
    return "\n".join(lines)


def _build_backing_track_xml(frame_padding: int) -> str:
    """Build the BackingTrack XML block as a string."""
    return f"""<BackingTrack>
<IconId>21</IconId>
<Color>0 0 0</Color>
<Name></Name>
<ShortName></ShortName>
<PlaybackState>Default</PlaybackState>
<ChannelStrip>
<Parameters>0.500000 0.500000 0.500000 0.500000 0.500000 0.500000 0.500000 0.500000 0.500000 0.000000 0.500000 0.500000 0.800000 0.500000 0.500000 0.500000</Parameters>
</ChannelStrip>
<Enabled>true</Enabled>
<Source>Local</Source>
<AssetId>0</AssetId>
<YouTubeVideoUrl></YouTubeVideoUrl>
<Filter>6</Filter>
<FramesPerPixel>100</FramesPerPixel>
<FramePadding>{frame_padding}</FramePadding>
<Semitones>0</Semitones>
<Cents>0</Cents>
</BackingTrack>"""


def _build_assets_xml(mp3_path: Path, asset_id: str, embedded_path: str) -> str:
    """Build the Assets XML block as a string."""
    original_path = str(mp3_path.parent / "audio.mp3")
    return f"""<Assets>
<Asset id="0">
<OriginalFilePath><![CDATA[{original_path}]]></OriginalFilePath>
<OriginalFileSha1>{asset_id}</OriginalFileSha1>
<EmbeddedFilePath><![CDATA[{embedded_path}]]></EmbeddedFilePath>
</Asset>
</Assets>"""


def sync_gp_file(gp_file: Path, points: list[float], output_path: Path, mp3_path: Path | None = None) -> list[float]:
    """
    Sync a GP7/8 file by embedding audio and adding SyncPoint automations.
    Uses string-based XML manipulation to preserve the original formatting.
    Returns the computed BPM list.
    """
    if not zipfile.is_zipfile(str(gp_file)):
        print(f"  ERROR: {gp_file} is not a valid GP7/8 file (not a ZIP archive)")
        sys.exit(1)

    # Read the raw XML as a string (preserving CDATA, formatting, etc.)
    with zipfile.ZipFile(str(gp_file), "r") as zf:
        xml_raw = zf.read("Content/score.gpif").decode("utf-8")

    # Also parse with ET for extracting time signatures and original tempo
    root = ET.fromstring(xml_raw)

    original_tempo = get_original_tempo(root)
    print(f"  Original tempo: {original_tempo} BPM")

    # Extract time signatures per measure
    master_bars = root.find("MasterBars")
    time_signatures = []
    for bar in master_bars:
        ts_elem = bar.find("Time")
        time_signatures.append(ts_elem.text if ts_elem is not None else "4/4")

    num_measures = len(time_signatures)
    print(f"  Measures: {num_measures}")
    print(f"  Time signatures: {', '.join(sorted(set(time_signatures)))}")

    bpms = compute_bpms(time_signatures, points)

    # --- String-based XML modifications ---
    xml = xml_raw

    # 1. Replace <Automations>...</Automations> in MasterTrack
    has_audio = mp3_path and mp3_path.exists()
    mp3_data = None
    embedded_path = None
    asset_id = None

    if has_audio:
        mp3_data = mp3_path.read_bytes()
        asset_id = generate_asset_sha1(mp3_data)
        embedded_path = f"Content/Assets/{asset_id}.mp3"
        print(f"  Embedding audio: {mp3_path.name} ({len(mp3_data) / 1024 / 1024:.1f} MB)")

    new_automations = _build_automations_xml(original_tempo, bpms, points, bool(has_audio))
    xml = re.sub(
        r'<Automations>.*?</Automations>',
        new_automations,
        xml,
        count=1,
        flags=re.DOTALL,
    )

    if has_audio and mp3_data:
        # Frame padding is 0 because we trim the audio to start at measure 1
        frame_padding = 0
        print(f"  Frame padding: {frame_padding} (audio trimmed to start at measure 1)")

        # 2. Remove existing BackingTrack and Assets if present
        xml = re.sub(r'<BackingTrack>.*?</BackingTrack>\s*', '', xml, flags=re.DOTALL)
        xml = re.sub(r'<Assets>.*?</Assets>\s*', '', xml, flags=re.DOTALL)

        # 3. Insert BackingTrack after </MasterTrack>
        backing_xml = _build_backing_track_xml(frame_padding)
        xml = xml.replace('</MasterTrack>', '</MasterTrack>\n' + backing_xml)

        # 4. Insert Assets before </GPIF> (end of file)
        assets_xml = _build_assets_xml(mp3_path, asset_id, embedded_path)
        xml = xml.replace('</GPIF>', assets_xml + '\n</GPIF>')

    xml_bytes = xml.encode("utf-8")

    # Write the output ZIP
    with zipfile.ZipFile(str(output_path), "w", zipfile.ZIP_DEFLATED) as zf_out:
        # Add directory entries that GP8 expects
        for dirname in ["Content/", "Content/Assets/", "Content/ScoreViews/", "Content/Stylesheets/"]:
            zf_out.mkdir(dirname)

        with zipfile.ZipFile(str(gp_file), "r") as zf_in:
            for item in zf_in.infolist():
                if item.filename.endswith("/"):
                    continue
                if item.filename == "Content/score.gpif":
                    zf_out.writestr(item.filename, xml_bytes)
                elif item.filename == "meta.json" and mp3_data:
                    zf_out.writestr(item.filename, b'{\n    "hasAudio": true,\n    "version": "1.0.0"\n}\n')
                elif item.filename == "Content/Preferences.json" and mp3_data:
                    prefs = json.loads(zf_in.read(item.filename))
                    if "view" in prefs and isinstance(prefs["view"], dict):
                        prefs["view"]["backingTrackVisible"] = True
                    zf_out.writestr(item.filename, json.dumps(prefs, separators=(",", ":")).encode("utf-8"))
                else:
                    zf_out.writestr(item.filename, zf_in.read(item.filename))

        # Add the MP3 file into the ZIP
        if mp3_data and embedded_path:
            zf_out.writestr(embedded_path, mp3_data)
            print(f"  Embedded audio at: {embedded_path}")

    return bpms


def print_summary(bpms: list[float], points: list[float]) -> None:
    """Print a summary of the sync results."""
    print("\n=== Sync Summary ===")
    print(f"  Measures: {len(bpms)}")
    print(f"  Video points: {len(points)}")

    if bpms:
        print(f"  BPM range: {min(bpms):.1f} - {max(bpms):.1f}")
        print(f"  Average BPM: {sum(bpms) / len(bpms):.1f}")
        print(f"  Initial BPM: {bpms[0]:.1f}")

    show_n = min(5, len(bpms))
    print(f"\n  First {show_n} measures:")
    for i in range(show_n):
        pt = points[i] if i < len(points) else "N/A"
        print(f"    Measure {i + 1}: {bpms[i]:.1f} BPM @ {pt}s")

    if len(bpms) > 10:
        print(f"\n  Last {show_n} measures:")
        for i in range(len(bpms) - show_n, len(bpms)):
            pt = points[i] if i < len(points) else "N/A"
            print(f"    Measure {i + 1}: {bpms[i]:.1f} BPM @ {pt}s")


def list_video_entries(entries: list[dict]) -> None:
    """Print all available video entries for user selection."""
    print("\nAvailable video entries:")
    print(f"{'Idx':>4} {'VideoID':>13} {'Feature':>12} {'Points':>7} {'Tracks':>10} {'Countries':>12}")
    print("-" * 65)
    for i, e in enumerate(entries):
        countries = e.get("countries")
        country_str = "All" if countries == ["All"] else (f"{len(countries)} countries" if countries else "N/A")
        tracks = e.get("tracks") or "All"
        feature = e.get("feature") or "N/A"
        print(f"{i:>4} {e['videoId']:>13} {feature:>12} {len(e['points']):>7} {str(tracks):>10} {country_str:>12}")


def main():
    parser = argparse.ArgumentParser(
        description="Songsterr → Synced GP File Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python sync.py --song 23063 --gp-file my_tab.gp
  python sync.py --song https://www.songsterr.com/a/wsa/gary-moore-parisienne-walkways-tab-s23063 --gp-file my_tab.gp
  python sync.py --song 23063 --list-videos
        """,
    )
    parser.add_argument("--song", type=str, required=True,
                        help="Songsterr song ID or URL (e.g. 23063 or https://www.songsterr.com/a/wsa/...-tab-s23063)")
    parser.add_argument("--video-index", type=int, default=None,
                        help="Index of the video entry to use (see --list-videos)")
    parser.add_argument("--gp-file", type=str, default=None,
                        help="Path to GP7/8 file")
    parser.add_argument("--list-videos", action="store_true",
                        help="List available video entries and exit")

    args = parser.parse_args()

    # Parse song ID from URL or raw number
    song_id_str = args.song.strip()
    m = re.search(r'-s(\d+)', song_id_str)
    if m:
        song_id = int(m.group(1))
    elif song_id_str.isdigit():
        song_id = int(song_id_str)
    else:
        print(f"  ERROR: Could not parse song ID from: {song_id_str}")
        print("  Provide a numeric ID or a Songsterr URL (e.g. https://www.songsterr.com/a/wsa/...-tab-s23063)")
        sys.exit(1)

    # Step 1: Get latest revision
    print("\n[1/5] Fetching song metadata...")
    meta = fetch_song_meta(song_id)
    revision_id = meta["revisionId"]
    print(f"  Song: {meta['artist']} - {meta['title']}")
    print(f"  Latest revision: {revision_id}")

    # Step 2: Fetch video points
    print("\n[2/5] Fetching video points...")
    entries = fetch_video_points(song_id, revision_id)

    if args.list_videos:
        list_video_entries(entries)
        return

    # Step 3: Select video entry
    print("\n[3/5] Selecting video entry...")
    entry = select_video_entry(entries, args.video_index)
    points = entry["points"]
    video_id = entry["videoId"]

    # Resolve GP file
    gp_file = None
    if args.gp_file:
        gp_file = Path(args.gp_file).resolve()
    else:
        gp_file = find_gp_file(Path("."))

    if not gp_file or not gp_file.exists():
        print("\n  ERROR: No GP file found!")
        print("  Please provide a GP7/8 file:")
        print(f"    1. Download from https://www.songsterr.com/a/wsa/-tab-s{song_id}")
        print(f"    2. Pass it with --gp-file /path/to/file.gp")
        sys.exit(1)

    # Output goes next to the original GP file
    gp_dir = gp_file.parent

    # Step 4: Download YouTube audio (trimmed to start at measure 1)
    print("\n[4/5] Downloading YouTube audio...")
    audio_path = gp_dir / ".tmp_audio.mp3"
    trim_start = points[0] if points else 0.0
    try:
        download_youtube_audio(video_id, audio_path, trim_start=trim_start)
    except Exception as e:
        print(f"  WARNING: Audio download failed: {e}")
        print("  Continuing without audio...")

    # Step 5: Sync GP file
    print("\n[5/5] Syncing GP file...")
    print(f"  Loading: {gp_file}")

    synced_path = gp_dir / f"{gp_file.stem}_synced{gp_file.suffix}"
    bpms = sync_gp_file(gp_file, points, synced_path, mp3_path=audio_path)

    # Clean up temp MP3 (it's now embedded in the GP file)
    if audio_path.exists():
        audio_path.unlink()
        print("  Cleaned up temporary audio file")

    print_summary(bpms, points)

    print(f"\nSaved: {synced_path}")
    print("Done!")


if __name__ == "__main__":
    main()
