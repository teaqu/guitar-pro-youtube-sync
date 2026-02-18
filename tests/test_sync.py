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
    get_video_options,
    list_video_entries,
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

    @patch('sync.yt_dlp.YoutubeDL')
    def test_download_youtube_audio_with_cookies(self, mock_ydl_cls, tmp_path):
        """Test that cookies option is passed to yt-dlp correctly."""
        # Setup mock: make the download create a fake audio file
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)

        def fake_download(urls):
            (tmp_path / ".dl_audio.mp3").write_bytes(b"fake audio data")
        mock_ydl.download.side_effect = fake_download

        output_path = tmp_path / "output.mp3"
        download_youtube_audio("test123", output_path, trim_start=0.0, cookies_browser="chrome")

        # Verify yt-dlp was initialized with cookies option
        opts = mock_ydl_cls.call_args[0][0]
        assert opts["cookiesfrombrowser"] == ("chrome",)

    @patch('sync.yt_dlp.YoutubeDL')
    def test_download_youtube_audio_without_cookies(self, mock_ydl_cls, tmp_path):
        """Test that yt-dlp works without cookies option."""
        mock_ydl = MagicMock()
        mock_ydl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)

        def fake_download(urls):
            (tmp_path / ".dl_audio.mp3").write_bytes(b"fake audio data")
        mock_ydl.download.side_effect = fake_download

        output_path = tmp_path / "output.mp3"
        download_youtube_audio("test123", output_path, trim_start=0.0, cookies_browser=None)

        # Verify cookies option is NOT in the yt-dlp options
        opts = mock_ydl_cls.call_args[0][0]
        assert "cookiesfrombrowser" not in opts

    @patch('sync.yt_dlp.YoutubeDL')
    def test_download_youtube_audio_different_browsers(self, mock_ydl_cls, tmp_path):
        """Test that different browser names are passed correctly."""
        browsers = ["chrome", "firefox", "safari", "edge"]

        for browser in browsers:
            mock_ydl = MagicMock()
            mock_ydl_cls.return_value.__enter__ = MagicMock(return_value=mock_ydl)
            mock_ydl_cls.return_value.__exit__ = MagicMock(return_value=False)

            output_path = tmp_path / f"output_{browser}.mp3"

            def fake_download(urls, _b=browser):
                (tmp_path / ".dl_audio.mp3").write_bytes(b"fake audio data")
            mock_ydl.download.side_effect = fake_download

            download_youtube_audio("test123", output_path, trim_start=0.0, cookies_browser=browser)
            opts = mock_ydl_cls.call_args[0][0]
            assert opts["cookiesfrombrowser"] == (browser,)


class TestGetVideoOptions:
    """Tests for get_video_options grouping logic."""

    TRACKS_META = [
        {"name": "Lead Vocals", "instrument": "voice"},
        {"name": "David Gilmour - Lead Guitar", "instrument": "guitar"},
        {"name": "Roger Waters - Bass", "instrument": "bass"},
        {"name": "Nick Mason - Drums", "instrument": "drums"},
    ]

    def _entry(self, video_id, feature=None, status="done", tracks=None, countries=None):
        return {
            "videoId": video_id,
            "feature": feature,
            "status": status,
            "tracks": tracks,
            "countries": countries,
            "points": [0, 1, 2],
        }

    def test_full_mix_from_default(self):
        entries = [
            self._entry("default1", feature=None),
            self._entry("alt1", feature="alternative"),
        ]
        opts = get_video_options(entries)
        assert opts["full_mix"]["videoId"] == "default1"

    def test_full_mix_fallback_to_universal_alternative(self):
        entries = [
            self._entry("alt1", feature="alternative", countries=["US"]),
            self._entry("alt2", feature="alternative", countries=["All"]),
        ]
        opts = get_video_options(entries)
        assert opts["full_mix"]["videoId"] == "alt2"

    def test_full_mix_fallback_to_any_alternative(self):
        entries = [
            self._entry("alt1", feature="alternative", countries=["US"]),
        ]
        opts = get_video_options(entries)
        assert opts["full_mix"]["videoId"] == "alt1"

    def test_full_mix_none_when_no_default_or_alternative(self):
        entries = [
            self._entry("back1", feature="backing"),
        ]
        opts = get_video_options(entries)
        assert opts["full_mix"] is None

    def test_backing_tracks_collected(self):
        entries = [
            self._entry("default1", feature=None),
            self._entry("back1", feature="backing", tracks=None),
            self._entry("back2", feature="backing", tracks=[2]),
        ]
        opts = get_video_options(entries)
        assert len(opts["categories"]["backing"]) == 2
        assert opts["categories"]["backing"][0]["entry"]["videoId"] == "back1"
        assert opts["categories"]["backing"][1]["entry"]["videoId"] == "back2"

    def test_solo_tracks_collected(self):
        entries = [
            self._entry("default1", feature=None),
            self._entry("solo1", feature="solo", tracks=[0]),
            self._entry("solo2", feature="solo", tracks=[1, 3]),
        ]
        opts = get_video_options(entries)
        assert len(opts["categories"]["solo"]) == 2
        assert opts["categories"]["solo"][0]["entry"]["videoId"] == "solo1"
        assert opts["categories"]["solo"][1]["entry"]["videoId"] == "solo2"

    def test_skips_non_done_entries(self):
        entries = [
            self._entry("default1", feature=None),
            self._entry("back1", feature="backing", status="processing"),
            self._entry("solo1", feature="solo", status="failed"),
        ]
        opts = get_video_options(entries)
        assert "backing" not in opts["categories"]
        assert "solo" not in opts["categories"]

    def test_deduplicates_by_video_id(self):
        entries = [
            self._entry("default1", feature=None),
            self._entry("back1", feature="backing", tracks=None),
            self._entry("back1", feature="backing", tracks=[2]),
        ]
        opts = get_video_options(entries)
        assert len(opts["categories"]["backing"]) == 1

    def test_track_label_with_metadata(self):
        entries = [
            self._entry("back1", feature="backing", tracks=[1, 2]),
        ]
        opts = get_video_options(entries, self.TRACKS_META)
        assert opts["categories"]["backing"][0]["label"] == "Lead Guitar, Bass"

    def test_track_label_all_instruments(self):
        entries = [
            self._entry("back1", feature="backing", tracks=None),
        ]
        opts = get_video_options(entries, self.TRACKS_META)
        assert opts["categories"]["backing"][0]["label"] == "All instruments"

    def test_track_label_without_metadata(self):
        entries = [
            self._entry("back1", feature="backing", tracks=[1, 2]),
        ]
        opts = get_video_options(entries, tracks_meta=None)
        assert opts["categories"]["backing"][0]["label"] == "Tracks [1, 2]"

    def test_track_label_short_name_extraction(self):
        """Track names with ' - ' should use the part after the last separator."""
        tracks_meta = [
            {"name": "Roger Waters - Fender Precision Bass", "instrument": "bass"},
        ]
        entries = [
            self._entry("back1", feature="backing", tracks=[0]),
        ]
        opts = get_video_options(entries, tracks_meta)
        assert opts["categories"]["backing"][0]["label"] == "Fender Precision Bass"

    def test_track_label_index_out_of_range(self):
        entries = [
            self._entry("back1", feature="backing", tracks=[99]),
        ]
        opts = get_video_options(entries, self.TRACKS_META)
        assert opts["categories"]["backing"][0]["label"] == "Track 99"

    def test_alternatives_not_in_categories(self):
        entries = [
            self._entry("default1", feature=None),
            self._entry("alt1", feature="alternative"),
            self._entry("alt2", feature="alternative", countries=["All"]),
        ]
        opts = get_video_options(entries)
        assert "alternative" not in opts["categories"]
        assert len(opts["categories"]) == 0

    def test_discovers_unknown_feature_types(self):
        """Any feature type from the API should be collected dynamically."""
        entries = [
            self._entry("default1", feature=None),
            self._entry("pt1", feature="playthrough", tracks=[1]),
            self._entry("lesson1", feature="lesson", tracks=None),
        ]
        opts = get_video_options(entries, self.TRACKS_META)
        assert "playthrough" in opts["categories"]
        assert "lesson" in opts["categories"]
        assert opts["categories"]["playthrough"][0]["entry"]["videoId"] == "pt1"
        assert opts["categories"]["lesson"][0]["label"] == "All instruments"

    def test_category_order_matches_entry_order(self):
        """Categories should appear in the order their feature is first seen."""
        entries = [
            self._entry("solo1", feature="solo", tracks=[0]),
            self._entry("back1", feature="backing", tracks=None),
            self._entry("pt1", feature="playthrough", tracks=[1]),
        ]
        opts = get_video_options(entries, self.TRACKS_META)
        keys = list(opts["categories"].keys())
        assert keys == ["solo", "backing", "playthrough"]

    def test_realistic_mixed_entries(self):
        """Simulate a real song with all three types."""
        entries = [
            self._entry("alt1", feature="alternative", countries=["All"]),
            self._entry("alt2", feature="alternative", countries=["US"]),
            self._entry("back_all", feature="backing", tracks=None),
            self._entry("back_bass", feature="backing", tracks=[2]),
            self._entry("solo_guitar", feature="solo", tracks=[1]),
            self._entry("default1", feature=None),
        ]
        opts = get_video_options(entries, self.TRACKS_META)
        assert opts["full_mix"]["videoId"] == "default1"
        assert len(opts["categories"]["backing"]) == 2
        assert len(opts["categories"]["solo"]) == 1
        assert opts["categories"]["backing"][0]["label"] == "All instruments"
        assert opts["categories"]["backing"][1]["label"] == "Bass"
        assert opts["categories"]["solo"][0]["label"] == "Lead Guitar"

    def test_realistic_with_playthrough(self):
        """Simulate Nirvana Heart Shaped Box with playthrough."""
        entries = [
            self._entry("default1", feature=None),
            self._entry("alt1", feature="alternative", countries=["All"]),
            self._entry("back1", feature="backing", tracks=None),
            self._entry("solo1", feature="solo", tracks=[0]),
            self._entry("pt1", feature="playthrough", tracks=[1, 3]),
        ]
        opts = get_video_options(entries, self.TRACKS_META)
        assert opts["full_mix"]["videoId"] == "default1"
        cats = opts["categories"]
        assert set(cats.keys()) == {"backing", "solo", "playthrough"}
        assert cats["playthrough"][0]["label"] == "Lead Guitar, Drums"


class TestListVideoEntries:
    """Tests for list_video_entries output formatting."""

    def _entry(self, video_id, feature=None, status="done", tracks=None, countries=None):
        return {
            "videoId": video_id,
            "feature": feature,
            "status": status,
            "tracks": tracks,
            "countries": countries,
            "points": [0, 1, 2],
        }

    def test_shows_youtube_urls(self, capsys):
        entries = [self._entry("abc123", feature="backing")]
        list_video_entries(entries)
        output = capsys.readouterr().out
        assert "https://youtu.be/abc123" in output

    def test_shows_all_countries(self, capsys):
        entries = [self._entry("vid1", feature="alternative", countries=["All"])]
        list_video_entries(entries)
        output = capsys.readouterr().out
        assert "All" in output

    def test_shows_country_count(self, capsys):
        entries = [self._entry("vid1", feature="alternative", countries=["US", "GB", "DE"])]
        list_video_entries(entries)
        output = capsys.readouterr().out
        assert "3 countries" in output

    def test_shows_na_for_no_countries(self, capsys):
        entries = [self._entry("vid1", feature="backing")]
        list_video_entries(entries)
        output = capsys.readouterr().out
        assert "N/A" in output

    def test_shows_feature_or_na(self, capsys):
        entries = [
            self._entry("vid1", feature=None),
            self._entry("vid2", feature="solo"),
        ]
        list_video_entries(entries)
        output = capsys.readouterr().out
        assert "N/A" in output
        assert "solo" in output

    def test_shows_tracks_or_all(self, capsys):
        entries = [
            self._entry("vid1", feature="backing", tracks=[1, 2]),
            self._entry("vid2", feature="backing", tracks=None),
        ]
        list_video_entries(entries)
        output = capsys.readouterr().out
        assert "[1, 2]" in output
        assert "All" in output

    def test_multiple_entries_indexed(self, capsys):
        entries = [
            self._entry("vid1", feature="alternative"),
            self._entry("vid2", feature="backing"),
            self._entry("vid3", feature="solo"),
        ]
        list_video_entries(entries)
        output = capsys.readouterr().out
        lines = output.strip().split("\n")
        # "Available video entries:" + header + separator + 3 entries = 6 lines
        assert len(lines) == 6
        assert "https://youtu.be/vid1" in lines[3]
        assert "https://youtu.be/vid2" in lines[4]
        assert "https://youtu.be/vid3" in lines[5]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
