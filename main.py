#!/usr/bin/env python3
"""
Guitar Pro YouTube Sync - Interactive CLI

Generates Guitar Pro (.gp) files from Songsterr tabs,
optionally synced with YouTube audio.
"""

import sys
from pathlib import Path

import gen_gp
from sync import (
    fetch_song_meta,
    fetch_video_points,
    select_video_entry,
    download_youtube_audio,
    sync_gp_file,
    print_summary,
)
from utils import load_config, save_config


BROWSERS = ["chrome", "firefox", "edge", "brave", "safari", "opera"]


def prompt_yes_no(question: str, default: bool = True) -> bool:
    """Prompt user for yes/no answer."""
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        answer = input(f"{question} {suffix}: ").strip().lower()
        if answer == "":
            return default
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("  Please enter 'y' or 'n'")


def prompt_browser_choice() -> str | None:
    """Prompt user to select a browser for cookie extraction."""
    print("\n  YouTube may require authentication for this video.")
    print("  Select a browser to use cookies from (must be logged into YouTube):")
    for i, browser in enumerate(BROWSERS, 1):
        print(f"    {i}. {browser}")
    skip_num = len(BROWSERS) + 1
    print(f"    {skip_num}. Skip audio")

    while True:
        try:
            choice = input(f"\n  Choice [{skip_num}]: ").strip()
            if choice == "":
                return None
            idx = int(choice)
            if 1 <= idx <= len(BROWSERS):
                return BROWSERS[idx - 1]
            if idx == skip_num:
                return None
            print(f"  Please enter a number between 1 and {skip_num}")
        except ValueError:
            print("  Please enter a number")


def try_download_audio(video_id: str, audio_path: Path, trim_start: float, config: dict) -> bool:
    """Attempt to download audio, with automatic retry using saved browser and manual prompt.

    Returns True if audio was downloaded successfully.
    """
    # First attempt: no cookies
    try:
        download_youtube_audio(video_id, audio_path, trim_start=trim_start)
        return True
    except Exception as e:
        print(f"\n  Audio download failed: {e}")

    # Second attempt: auto-retry with saved browser
    saved_browser = config.get("cookie_browser")
    if saved_browser:
        print(f"\n  Retrying with saved browser ({saved_browser})...")
        try:
            download_youtube_audio(video_id, audio_path, trim_start=trim_start, cookies_browser=saved_browser)
            return True
        except Exception as e:
            print(f"  Still failed: {e}")

    # Third attempt: ask user to pick a browser
    browser = prompt_browser_choice()
    if not browser:
        print("  Skipping audio.")
        return False

    print(f"\n  Retrying with {browser} cookies...")
    try:
        download_youtube_audio(video_id, audio_path, trim_start=trim_start, cookies_browser=browser)
        # Save successful browser for next time
        config["cookie_browser"] = browser
        save_config(config)
        print(f"  (Saved {browser} as default browser for next time)")
        return True
    except Exception as e:
        print(f"\n  Download failed again: {e}")
        print("  Skipping audio.")
        return False


def process_song(config: dict) -> None:
    """Process a single song (generate GP + optional audio sync)."""
    # Get song input
    while True:
        user_input = input("\nEnter Songsterr URL or song ID (or 'q' to quit): ").strip()
        if user_input.lower() in ("q", "quit", "exit"):
            raise SystemExit(0)
        if not user_input:
            continue
        try:
            song_id = gen_gp.parse_song_id(user_input)
            break
        except ValueError as e:
            print(f"\n  Error: {e}")
            print("  Examples: https://www.songsterr.com/a/wsa/metallica-master-of-puppets-tab-s84  or  84")

    # Fetch metadata
    print("\nFetching song info...")
    try:
        meta = fetch_song_meta(song_id)
    except Exception as e:
        print(f"\n  Error fetching song data: {e}")
        return

    artist = meta.get("artist", "Unknown")
    title = meta.get("title", "Unknown")
    num_tracks = len(meta.get("tracks", []))
    print(f"  Found: {artist} - {title} ({num_tracks} tracks)")

    include_audio = prompt_yes_no("\nInclude YouTube audio?", default=True)

    safe_name = "".join(c if c.isalnum() or c in " -_" else "" for c in f"{artist} - {title}").strip()
    total_steps = 3 if include_audio else 1

    # Step 1: Generate GP file
    print(f"\n[1/{total_steps}] Generating Guitar Pro file...")
    try:
        gp_meta, tracks = gen_gp.fetch_all_tracks(song_id)
        gp_file = Path(f"{safe_name or 'output'}.gp").resolve()
        gen_gp.generate_gp(tracks, gp_file, gp_meta)
    except Exception as e:
        print(f"\n  Error generating GP file: {e}")
        return

    if not include_audio:
        print(f"\nDone! File saved to: {gp_file}")
        return

    # Step 2: Download audio
    print(f"\n[2/{total_steps}] Downloading YouTube audio...")
    revision_id = meta["revisionId"]
    try:
        entries = fetch_video_points(song_id, revision_id)
        entry = select_video_entry(entries)
    except Exception as e:
        print(f"\n  Error fetching video data: {e}")
        print("  Continuing without audio...")
        print(f"\nDone! File saved to: {gp_file}")
        return

    points = entry["points"]
    video_id = entry["videoId"]
    trim_start = points[0] if points else 0.0
    audio_path = gp_file.parent / ".tmp_audio.mp3"

    audio_ok = try_download_audio(video_id, audio_path, trim_start, config)

    # Step 3: Sync
    print(f"\n[3/{total_steps}] Syncing audio with tab...")
    synced_path = gp_file.parent / f"{gp_file.stem}_synced{gp_file.suffix}"
    mp3_path = audio_path if audio_ok else None
    bpms = sync_gp_file(gp_file, points, synced_path, mp3_path=mp3_path)

    if audio_path.exists():
        audio_path.unlink()

    print_summary(bpms, points)
    print(f"\nDone! File saved to: {synced_path}")


def main():
    print("=== Guitar Pro YouTube Sync ===")

    config = load_config()

    while True:
        try:
            process_song(config)
            print("\n" + "-" * 40)
        except SystemExit:
            print("\nGoodbye!")
            break
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\nUnexpected error: {e}")
            print("You can try another song.\n")


if __name__ == "__main__":
    main()
