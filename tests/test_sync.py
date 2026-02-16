#!/usr/bin/env python3
"""Tests for sync.py"""

import pytest
import sys
from pathlib import Path
from xml.etree import ElementTree as ET
import hashlib
import uuid
from unittest.mock import patch, MagicMock, call

# Add parent directory to path to import sync module
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import functions from sync.py
from sync import (
    parse_time_signature,
    measure_length_in_quarter_notes,
    compute_bpms,
    generate_asset_sha1,
    get_original_tempo,
    select_video_entry,
    download_youtube_audio,
)


class TestTimeSignature:
    """Tests for time signature parsing and calculations."""

    def test_parse_time_signature_simple(self):
        assert parse_time_signature("4/4") == (4, 4)
        assert parse_time_signature("3/4") == (3, 4)
        assert parse_time_signature("6/8") == (6, 8)

    def test_parse_time_signature_complex(self):
        assert parse_time_signature("7/8") == (7, 8)
        assert parse_time_signature("5/4") == (5, 4)
        assert parse_time_signature("12/8") == (12, 8)

    def test_measure_length_4_4(self):
        # 4/4 = 4 quarter notes
        assert measure_length_in_quarter_notes("4/4") == 4.0

    def test_measure_length_3_4(self):
        # 3/4 = 3 quarter notes
        assert measure_length_in_quarter_notes("3/4") == 3.0

    def test_measure_length_6_8(self):
        # 6/8 = 6 eighth notes = 3 quarter notes
        assert measure_length_in_quarter_notes("6/8") == 3.0

    def test_measure_length_7_8(self):
        # 7/8 = 7 eighth notes = 3.5 quarter notes
        assert measure_length_in_quarter_notes("7/8") == 3.5

    def test_measure_length_12_8(self):
        # 12/8 = 12 eighth notes = 6 quarter notes
        assert measure_length_in_quarter_notes("12/8") == 6.0


class TestBPMComputation:
    """Tests for BPM computation from video points."""

    def test_compute_bpms_simple(self):
        # 4/4 time, 2 seconds per measure = 120 BPM
        time_sigs = ["4/4", "4/4"]
        points = [0.0, 2.0, 4.0]
        bpms = compute_bpms(time_sigs, points)
        assert len(bpms) == 2
        assert bpms[0] == 120.0
        assert bpms[1] == 120.0

    def test_compute_bpms_varying_tempo(self):
        # First measure: 4/4 in 2 seconds = 120 BPM
        # Second measure: 4/4 in 1 second = 240 BPM
        time_sigs = ["4/4", "4/4"]
        points = [0.0, 2.0, 3.0]
        bpms = compute_bpms(time_sigs, points)
        assert len(bpms) == 2
        assert bpms[0] == 120.0
        assert bpms[1] == 240.0

    def test_compute_bpms_different_time_signatures(self):
        # 6/8 time (3 quarter notes), 3 seconds = 60 BPM
        time_sigs = ["6/8"]
        points = [0.0, 3.0]
        bpms = compute_bpms(time_sigs, points)
        assert len(bpms) == 1
        assert bpms[0] == 60.0

    def test_compute_bpms_clamping(self):
        # Test that BPM is clamped between 10 and 999
        time_sigs = ["4/4", "4/4"]
        # Very long duration should clamp to min BPM
        points = [0.0, 100.0, 200.0]
        bpms = compute_bpms(time_sigs, points)
        assert all(10.0 <= bpm <= 999.0 for bpm in bpms)

    def test_compute_bpms_fewer_points(self):
        # More measures than points should extrapolate
        time_sigs = ["4/4", "4/4", "4/4"]
        points = [0.0, 2.0]
        bpms = compute_bpms(time_sigs, points)
        assert len(bpms) == 3
        # First measure should be computed
        assert bpms[0] == 120.0
        # Remaining measures should use last BPM
        assert bpms[1] == bpms[0]
        assert bpms[2] == bpms[0]

    def test_compute_bpms_more_points(self):
        # More points than measures should work fine
        time_sigs = ["4/4"]
        points = [0.0, 2.0, 4.0, 6.0]
        bpms = compute_bpms(time_sigs, points)
        assert len(bpms) == 1


class TestAssetGeneration:
    """Tests for asset SHA1 generation."""

    def test_generate_asset_sha1_deterministic(self):
        # Same data should produce same SHA1
        data = b"test audio data"
        sha1_1 = generate_asset_sha1(data)
        sha1_2 = generate_asset_sha1(data)
        assert sha1_1 == sha1_2

    def test_generate_asset_sha1_format(self):
        # Should return a valid UUID string
        data = b"test audio data"
        result = generate_asset_sha1(data)
        # Should be parseable as UUID
        uuid_obj = uuid.UUID(result)
        assert isinstance(uuid_obj, uuid.UUID)

    def test_generate_asset_sha1_different_data(self):
        # Different data should produce different SHA1
        data1 = b"test audio data 1"
        data2 = b"test audio data 2"
        sha1_1 = generate_asset_sha1(data1)
        sha1_2 = generate_asset_sha1(data2)
        assert sha1_1 != sha1_2


class TestTempoExtraction:
    """Tests for extracting tempo from GP XML."""

    def test_get_original_tempo_basic(self):
        xml = """<?xml version="1.0"?>
        <GPIF>
            <MasterTrack>
                <Automations>
                    <Automation>
                        <Type>Tempo</Type>
                        <Value>120 2</Value>
                    </Automation>
                </Automations>
            </MasterTrack>
        </GPIF>"""
        root = ET.fromstring(xml)
        tempo = get_original_tempo(root)
        assert tempo == 120.0

    def test_get_original_tempo_decimal(self):
        xml = """<?xml version="1.0"?>
        <GPIF>
            <MasterTrack>
                <Automations>
                    <Automation>
                        <Type>Tempo</Type>
                        <Value>88.5 2</Value>
                    </Automation>
                </Automations>
            </MasterTrack>
        </GPIF>"""
        root = ET.fromstring(xml)
        tempo = get_original_tempo(root)
        assert tempo == 88.5

    def test_get_original_tempo_no_automation(self):
        xml = """<?xml version="1.0"?>
        <GPIF>
            <MasterTrack>
                <Automations>
                </Automations>
            </MasterTrack>
        </GPIF>"""
        root = ET.fromstring(xml)
        tempo = get_original_tempo(root)
        assert tempo == 120.0  # Default


class TestVideoEntrySelection:
    """Tests for selecting the correct video entry."""

    def test_select_video_entry_manual_index(self):
        entries = [
            {"videoId": "abc123", "feature": None, "points": [0, 1, 2]},
            {"videoId": "def456", "feature": "alternative", "points": [0, 1, 2]},
        ]
        entry = select_video_entry(entries, video_index=1)
        assert entry["videoId"] == "def456"

    def test_select_video_entry_default(self):
        entries = [
            {"videoId": "alt123", "feature": "alternative", "points": [0, 1, 2]},
            {"videoId": "default456", "feature": None, "points": [0, 1, 2]},
        ]
        entry = select_video_entry(entries, video_index=None)
        assert entry["videoId"] == "default456"

    def test_select_video_entry_universal_alternative(self):
        entries = [
            {"videoId": "alt1", "feature": "alternative", "status": "done", "countries": ["US"], "points": [0, 1, 2]},
            {"videoId": "alt2", "feature": "alternative", "status": "done", "countries": ["All"], "points": [0, 1, 2]},
        ]
        entry = select_video_entry(entries, video_index=None)
        assert entry["videoId"] == "alt2"
        assert entry["countries"] == ["All"]

    def test_select_video_entry_alternative_fallback(self):
        entries = [
            {"videoId": "backing1", "feature": "backing", "status": "done", "points": [0, 1, 2]},
            {"videoId": "alt1", "feature": "alternative", "status": "done", "points": [0, 1, 2]},
        ]
        entry = select_video_entry(entries, video_index=None)
        assert entry["videoId"] == "alt1"

    def test_select_video_entry_backing_fallback(self):
        entries = [
            {"videoId": "backing1", "feature": "backing", "status": "done", "points": [0, 1, 2]},
        ]
        entry = select_video_entry(entries, video_index=None)
        assert entry["videoId"] == "backing1"

    def test_select_video_entry_first_fallback(self):
        entries = [
            {"videoId": "first", "feature": "unknown", "points": [0, 1, 2]},
        ]
        entry = select_video_entry(entries, video_index=None)
        assert entry["videoId"] == "first"

    def test_select_video_entry_invalid_index(self):
        entries = [
            {"videoId": "abc123", "feature": None, "points": [0, 1, 2]},
        ]
        # Should fall back to auto-select when index is out of range
        entry = select_video_entry(entries, video_index=10)
        assert entry["videoId"] == "abc123"


class TestCookiesOption:
    """Tests for browser cookies option in download_youtube_audio."""

    @patch('sync.subprocess.run')
    def test_download_youtube_audio_with_cookies(self, mock_run, tmp_path):
        """Test that --cookies option is passed to yt-dlp correctly."""
        # Setup mock
        mock_run.return_value = MagicMock(returncode=0)

        # Create a fake audio file that would be created by yt-dlp
        audio_file = tmp_path / ".dl_audio.mp3"
        audio_file.write_bytes(b"fake audio data")

        output_path = tmp_path / "output.mp3"
        video_id = "test123"

        # Call with cookies
        download_youtube_audio(video_id, output_path, trim_start=0.0, cookies_browser="chrome")

        # Verify subprocess was called
        assert mock_run.called
        cmd = mock_run.call_args[0][0]

        # Check that the command includes --cookies-from-browser chrome
        assert "yt-dlp" in cmd
        assert "--cookies-from-browser" in cmd
        assert "chrome" in cmd
        assert f"https://www.youtube.com/watch?v={video_id}" in cmd

    @patch('sync.subprocess.run')
    def test_download_youtube_audio_without_cookies(self, mock_run, tmp_path):
        """Test that yt-dlp works without cookies option."""
        # Setup mock
        mock_run.return_value = MagicMock(returncode=0)

        # Create a fake audio file
        audio_file = tmp_path / ".dl_audio.mp3"
        audio_file.write_bytes(b"fake audio data")

        output_path = tmp_path / "output.mp3"
        video_id = "test123"

        # Call without cookies
        download_youtube_audio(video_id, output_path, trim_start=0.0, cookies_browser=None)

        # Verify subprocess was called
        assert mock_run.called
        cmd = mock_run.call_args[0][0]

        # Check that the command does NOT include cookies option
        assert "yt-dlp" in cmd
        assert "--cookies-from-browser" not in cmd
        assert f"https://www.youtube.com/watch?v={video_id}" in cmd

    @patch('sync.subprocess.run')
    def test_download_youtube_audio_different_browsers(self, mock_run, tmp_path):
        """Test that different browser names are passed correctly."""
        mock_run.return_value = MagicMock(returncode=0)

        video_id = "test123"
        browsers = ["chrome", "firefox", "safari", "edge"]

        for browser in browsers:
            # Use different output path for each browser to avoid early return
            output_path = tmp_path / f"output_{browser}.mp3"
            audio_file = tmp_path / ".dl_audio.mp3"
            audio_file.write_bytes(b"fake audio data")

            download_youtube_audio(video_id, output_path, trim_start=0.0, cookies_browser=browser)
            cmd = mock_run.call_args[0][0]
            assert "--cookies-from-browser" in cmd
            assert browser in cmd

            # Clean up for next iteration
            if audio_file.exists():
                audio_file.unlink()
            if output_path.exists():
                output_path.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
