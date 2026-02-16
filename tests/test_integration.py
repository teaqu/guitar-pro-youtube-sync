#!/usr/bin/env python3
"""
Integration tests for sync.py and gen-gp.py

These tests verify the full end-to-end workflow including:
- Fetching data from Songsterr
- Generating GP files
- Syncing GP files with video points
- File I/O and ZIP operations

NOTE: These tests require network access to the Songsterr API.
They are slower than unit tests and may be marked as integration tests.
"""

import pytest
import zipfile
import json
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET
import sys
import importlib.util

# Import sync.py module
from sync import (
    fetch_song_meta,
    fetch_video_points,
    sync_gp_file,
)

# Import gen-gp.py module
spec = importlib.util.spec_from_file_location("gen_gp", Path(__file__).parent.parent / "gen-gp.py")
gen_gp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen_gp)


@pytest.mark.integration
class TestSongsterrAPI:
    """Integration tests for Songsterr API interactions."""

    def test_fetch_song_meta(self):
        """Test fetching song metadata from Songsterr API."""
        # Using a well-known stable song ID
        song_id = 23063  # Gary Moore - Parisienne Walkways

        meta = fetch_song_meta(song_id)

        assert "revisionId" in meta
        assert "artist" in meta
        assert "title" in meta
        assert "image" in meta
        assert meta["artist"] == "Gary Moore"
        assert meta["title"] == "Parisienne Walkways"

    def test_fetch_video_points(self):
        """Test fetching video points from Songsterr"""
        song_id = 23063

        # First get metadata to get revision ID
        meta = fetch_song_meta(song_id)
        revision_id = meta["revisionId"]

        # Then fetch video points
        entries = fetch_video_points(song_id, revision_id)

        assert len(entries) > 0
        assert isinstance(entries, list)

        # Check first entry structure
        entry = entries[0]
        assert "videoId" in entry
        assert "points" in entry
        assert isinstance(entry["points"], list)
        assert len(entry["points"]) > 0

    def test_fetch_all_tracks(self):
        """Test fetching all track data from Songsterr."""
        song_id = 23063

        meta, tracks = gen_gp.fetch_all_tracks(song_id)

        assert len(tracks) > 0
        assert "artist" in meta
        assert "title" in meta

        # Check first track structure
        track = tracks[0]
        assert "name" in track
        assert "instrument" in track
        assert "measures" in track
        assert len(track["measures"]) > 0


@pytest.mark.integration
class TestGPFileGeneration:
    """Integration tests for GP file generation."""

    def test_generate_gp_file_simple(self, tmp_path):
        """Test generating a GP file from a simple track."""
        # Create a minimal track data structure
        tracks = [{
            "name": "Test Track",
            "instrument": "Steel Guitar",
            "instrumentId": 25,
            "strings": 6,
            "frets": 24,
            "tuning": [64, 59, 55, 50, 45, 40],  # Standard tuning
            "measures": [
                {
                    "signature": [4, 4],
                    "voices": [
                        {
                            "beats": [
                                {
                                    "type": 4,  # Quarter note
                                    "notes": [{"fret": 0, "string": 0}]
                                },
                                {
                                    "type": 4,
                                    "notes": [{"fret": 2, "string": 0}]
                                },
                                {
                                    "type": 4,
                                    "notes": [{"fret": 3, "string": 0}]
                                },
                                {
                                    "type": 4,
                                    "notes": [{"fret": 5, "string": 0}]
                                }
                            ]
                        }
                    ]
                }
            ],
            "automations": {
                "tempo": [{"bpm": 120, "measure": 0, "position": 0}]
            }
        }]

        output_path = tmp_path / "test_output.gp"
        meta = {"artist": "Test Artist", "title": "Test Song"}

        gen_gp.generate_gp(tracks, output_path, meta)

        # Verify the file was created
        assert output_path.exists()

        # Verify it's a valid ZIP file
        assert zipfile.is_zipfile(output_path)

        # Verify it contains the expected files
        with zipfile.ZipFile(output_path, 'r') as zf:
            namelist = zf.namelist()
            assert "Content/score.gpif" in namelist
            assert "meta.json" in namelist

            # Verify the XML is valid
            xml_content = zf.read("Content/score.gpif").decode("utf-8")
            root = ET.fromstring(xml_content)
            assert root.tag == "GPIF"

            # Check metadata in XML
            assert "Test Artist" in xml_content
            assert "Test Song" in xml_content

    def test_generate_gp_from_songsterr(self, tmp_path):
        """Test generating a GP file from real Songsterr data."""
        song_id = 23063

        meta, tracks = gen_gp.fetch_all_tracks(song_id)
        output_path = tmp_path / "songsterr_test.gp"

        gen_gp.generate_gp(tracks, output_path, meta)

        assert output_path.exists()
        assert zipfile.is_zipfile(output_path)

        with zipfile.ZipFile(output_path, 'r') as zf:
            xml_content = zf.read("Content/score.gpif").decode("utf-8")
            root = ET.fromstring(xml_content)

            # Verify tracks were generated
            tracks_elem = root.find("Tracks")
            assert tracks_elem is not None
            track_elems = list(tracks_elem)
            assert len(track_elems) > 0


@pytest.mark.integration
class TestAudioSync:
    """Integration tests for audio sync functionality."""

    def test_sync_gp_file_without_audio(self, tmp_path):
        """Test syncing a GP file with video points but no audio."""
        # First generate a GP file
        tracks = [{
            "name": "Test Track",
            "instrument": "Steel Guitar",
            "strings": 6,
            "frets": 24,
            "tuning": [64, 59, 55, 50, 45, 40],
            "measures": [
                {"signature": [4, 4], "voices": [{"beats": [{"type": 4, "notes": [{"fret": 0, "string": 0}]}]}]},
                {"signature": [4, 4], "voices": [{"beats": [{"type": 4, "notes": [{"fret": 2, "string": 0}]}]}]},
                {"signature": [4, 4], "voices": [{"beats": [{"type": 4, "notes": [{"fret": 3, "string": 0}]}]}]},
            ],
            "automations": {"tempo": [{"bpm": 120, "measure": 0, "position": 0}]}
        }]

        input_path = tmp_path / "input.gp"
        gen_gp.generate_gp(tracks, input_path)

        # Create video points (3 measures)
        points = [0.0, 2.0, 4.0, 6.0]

        # Sync without audio
        output_path = tmp_path / "synced.gp"
        bpms = sync_gp_file(input_path, points, output_path, mp3_path=None)

        assert output_path.exists()
        assert len(bpms) == 3

        # Verify BPMs were computed correctly
        # 4/4 time, 2 seconds per measure = 120 BPM
        for bpm in bpms:
            assert 119.0 <= bpm <= 121.0  # Allow small rounding difference

    def test_sync_gp_file_structure(self, tmp_path):
        """Test that synced GP file has correct structure."""
        # Generate input file
        tracks = [{
            "name": "Test Track",
            "instrument": "Steel Guitar",
            "strings": 6,
            "tuning": [64, 59, 55, 50, 45, 40],
            "measures": [
                {"voices": [{"beats": [{"type": 4, "notes": [{"fret": 0, "string": 0}]}]}]},
                {"voices": [{"beats": [{"type": 4, "notes": [{"fret": 2, "string": 0}]}]}]},
            ],
            "automations": {"tempo": [{"bpm": 88, "measure": 0, "position": 0}]}
        }]

        input_path = tmp_path / "input.gp"
        gen_gp.generate_gp(tracks, input_path)

        points = [0.0, 2.5, 5.0]
        output_path = tmp_path / "synced.gp"

        sync_gp_file(input_path, points, output_path, mp3_path=None)

        # Verify the synced file structure
        with zipfile.ZipFile(output_path, 'r') as zf:
            xml_content = zf.read("Content/score.gpif").decode("utf-8")
            root = ET.fromstring(xml_content)

            # Check that Tempo automation exists
            master_track = root.find("MasterTrack")
            automations = master_track.find("Automations")
            assert automations is not None

            automation_types = [auto.find("Type").text for auto in automations]
            assert "Tempo" in automation_types


@pytest.mark.integration
class TestEndToEnd:
    """End-to-end integration tests for the complete workflow."""

    def test_full_workflow_gen_gp(self, tmp_path):
        """Test the complete workflow: Songsterr -> GP file."""
        song_id = 23063

        # Step 1: Fetch data
        meta, tracks = gen_gp.fetch_all_tracks(song_id)

        # Step 2: Generate GP file
        output_path = tmp_path / "full_test.gp"
        gen_gp.generate_gp(tracks, output_path, meta)

        # Step 3: Verify output
        assert output_path.exists()
        file_size = output_path.stat().st_size
        assert file_size > 1000  # Should be at least 1KB

        # Step 4: Verify ZIP contents
        with zipfile.ZipFile(output_path, 'r') as zf:
            xml_content = zf.read("Content/score.gpif").decode("utf-8")
            root = ET.fromstring(xml_content)

            # Verify essential elements
            score = root.find("Score")
            assert score is not None

            title = score.find("Title").text
            artist = score.find("Artist").text
            assert title
            assert artist

    def test_full_workflow_sync(self, tmp_path):
        """Test the complete workflow: Songsterr -> GP file -> Sync."""
        song_id = 23063

        # Step 1: Fetch all data
        meta = fetch_song_meta(song_id)
        revision_id = meta["revisionId"]
        entries = fetch_video_points(song_id, revision_id)
        track_meta, tracks = gen_gp.fetch_all_tracks(song_id)

        # Step 2: Generate GP file
        gp_path = tmp_path / "test.gp"
        gen_gp.generate_gp(tracks, gp_path, track_meta)

        # Step 3: Get video points
        entry = entries[0]
        points = entry["points"]

        # Step 4: Sync (without audio for faster testing)
        synced_path = tmp_path / "test_synced.gp"
        bpms = sync_gp_file(gp_path, points, synced_path, mp3_path=None)

        # Step 5: Verify results
        assert synced_path.exists()
        assert len(bpms) > 0
        assert all(10.0 <= bpm <= 999.0 for bpm in bpms)  # BPMs in valid range

        # Verify synced file is valid
        with zipfile.ZipFile(synced_path, 'r') as zf:
            xml_content = zf.read("Content/score.gpif").decode("utf-8")
            root = ET.fromstring(xml_content)

            # Should have SyncPoint automations now
            master_track = root.find("MasterTrack")
            automations = master_track.find("Automations")
            automation_types = [auto.find("Type").text for auto in automations]

            # Should have Tempo automation
            assert "Tempo" in automation_types


@pytest.mark.integration
class TestWithAudio:
    """Integration tests that include audio download (slower tests)."""

    @pytest.mark.slow
    def test_sync_with_real_audio(self, tmp_path):
        """Test syncing with real audio download from YouTube.

        This test:
        - Requires yt-dlp to be installed
        - Requires network access
        - Downloads actual audio from YouTube (slow)
        - May be blocked by YouTube's rate limiting
        """
        from sync import download_youtube_audio

        song_id = 23063
        meta = fetch_song_meta(song_id)
        revision_id = meta["revisionId"]
        entries = fetch_video_points(song_id, revision_id)

        entry = entries[0]
        video_id = entry["videoId"]
        points = entry["points"]

        # Generate GP file
        track_meta, tracks = gen_gp.fetch_all_tracks(song_id)
        gp_path = tmp_path / "test.gp"
        gen_gp.generate_gp(tracks, gp_path, track_meta)

        # Download audio
        audio_path = tmp_path / "test_audio.mp3"
        trim_start = points[0] if points else 0.0
        download_youtube_audio(video_id, audio_path, trim_start=trim_start)

        # Sync with audio
        synced_path = tmp_path / "test_synced.gp"
        bpms = sync_gp_file(gp_path, points, synced_path, mp3_path=audio_path)

        # Verify audio was embedded
        with zipfile.ZipFile(synced_path, 'r') as zf:
            xml_content = zf.read("Content/score.gpif").decode("utf-8")

            # Should have BackingTrack element
            assert "<BackingTrack>" in xml_content
            assert "<Assets>" in xml_content

            # Should have embedded MP3 file
            asset_files = [name for name in zf.namelist() if name.startswith("Content/Assets/") and name.endswith(".mp3")]
            assert len(asset_files) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
