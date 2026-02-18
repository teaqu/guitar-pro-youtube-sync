#!/usr/bin/env python3
"""Tests for main.py"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from main import prompt_yes_no, prompt_browser_choice, prompt_video_type, _format_feature_name, BROWSERS


class TestPromptYesNo:
    """Tests for yes/no prompt helper."""

    def test_yes_answers(self, monkeypatch):
        for answer in ["y", "Y", "yes", "YES", "Yes"]:
            monkeypatch.setattr("builtins.input", lambda _a, ans=answer: ans)
            assert prompt_yes_no("Test?") is True

    def test_no_answers(self, monkeypatch):
        for answer in ["n", "N", "no", "NO", "No"]:
            monkeypatch.setattr("builtins.input", lambda _a, ans=answer: ans)
            assert prompt_yes_no("Test?") is False

    def test_default_yes(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "")
        assert prompt_yes_no("Test?", default=True) is True

    def test_default_no(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "")
        assert prompt_yes_no("Test?", default=False) is False


class TestPromptBrowserChoice:
    """Tests for browser selection prompt."""

    def test_valid_browser_selection(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "1")
        result = prompt_browser_choice()
        assert result == BROWSERS[0]

    def test_skip_selection(self, monkeypatch):
        skip_num = str(len(BROWSERS) + 1)
        monkeypatch.setattr("builtins.input", lambda _: skip_num)
        result = prompt_browser_choice()
        assert result is None

    def test_empty_input_skips(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "")
        result = prompt_browser_choice()
        assert result is None

    def test_all_browsers_selectable(self, monkeypatch):
        for i, browser in enumerate(BROWSERS, 1):
            monkeypatch.setattr("builtins.input", lambda _, idx=str(i): idx)
            result = prompt_browser_choice()
            assert result == browser


class TestFormatFeatureName:
    """Tests for _format_feature_name display label conversion."""

    def test_known_features(self):
        assert _format_feature_name("backing") == "Backing Track"
        assert _format_feature_name("solo") == "Solo"
        assert _format_feature_name("playthrough") == "Playthrough"

    def test_unknown_feature_titlecased(self):
        assert _format_feature_name("lesson") == "Lesson"
        assert _format_feature_name("cover") == "Cover"

    def test_unknown_feature_with_underscores(self):
        assert _format_feature_name("drum_cover") == "Drum Cover"
        assert _format_feature_name("bass_only") == "Bass Only"


class TestPromptVideoType:
    """Tests for interactive video type selection."""

    TRACKS_META = [
        {"name": "Lead Vocals", "instrument": "voice"},
        {"name": "Lead Guitar", "instrument": "guitar"},
        {"name": "Bass", "instrument": "bass"},
        {"name": "Drums", "instrument": "drums"},
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

    def test_auto_selects_when_only_full_mix(self, monkeypatch):
        """No menu shown when only full mix available."""
        entries = [
            self._entry("default1", feature=None),
            self._entry("alt1", feature="alternative", countries=["All"]),
        ]
        result = prompt_video_type(entries, self.TRACKS_META)
        assert result["videoId"] == "default1"

    def test_select_full_mix_default(self, monkeypatch):
        """Pressing enter selects Full Mix (first option)."""
        entries = [
            self._entry("default1", feature=None),
            self._entry("back1", feature="backing", tracks=None),
        ]
        monkeypatch.setattr("builtins.input", lambda _: "")
        result = prompt_video_type(entries, self.TRACKS_META)
        assert result["videoId"] == "default1"

    def test_select_backing_single(self, monkeypatch):
        """Selecting backing with one option skips sub-menu."""
        entries = [
            self._entry("default1", feature=None),
            self._entry("back1", feature="backing", tracks=None),
        ]
        monkeypatch.setattr("builtins.input", lambda _: "2")
        result = prompt_video_type(entries, self.TRACKS_META)
        assert result["videoId"] == "back1"

    def test_select_backing_submenu(self, monkeypatch):
        """Selecting backing with multiple options shows sub-menu."""
        entries = [
            self._entry("default1", feature=None),
            self._entry("back1", feature="backing", tracks=None),
            self._entry("back2", feature="backing", tracks=[2]),
        ]
        inputs = iter(["2", "2"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        result = prompt_video_type(entries, self.TRACKS_META)
        assert result["videoId"] == "back2"

    def test_select_solo(self, monkeypatch):
        entries = [
            self._entry("default1", feature=None),
            self._entry("back1", feature="backing", tracks=None),
            self._entry("solo1", feature="solo", tracks=[1]),
        ]
        monkeypatch.setattr("builtins.input", lambda _: "3")
        result = prompt_video_type(entries, self.TRACKS_META)
        assert result["videoId"] == "solo1"

    def test_select_dynamic_feature(self, monkeypatch):
        """Dynamically discovered features like playthrough are selectable."""
        entries = [
            self._entry("default1", feature=None),
            self._entry("pt1", feature="playthrough", tracks=[1]),
        ]
        monkeypatch.setattr("builtins.input", lambda _: "2")
        result = prompt_video_type(entries, self.TRACKS_META)
        assert result["videoId"] == "pt1"

    def test_youtube_urls_in_output(self, monkeypatch, capsys):
        """YouTube URLs appear in the menu output."""
        entries = [
            self._entry("default1", feature=None),
            self._entry("solo1", feature="solo", tracks=[1]),
        ]
        monkeypatch.setattr("builtins.input", lambda _: "")
        prompt_video_type(entries, self.TRACKS_META)
        output = capsys.readouterr().out
        assert "https://youtu.be/default1" in output
        assert "https://youtu.be/solo1" in output

    def test_youtube_urls_in_submenu(self, monkeypatch, capsys):
        """YouTube URLs appear in backing track sub-menu."""
        entries = [
            self._entry("default1", feature=None),
            self._entry("back1", feature="backing", tracks=None),
            self._entry("back2", feature="backing", tracks=[2]),
        ]
        inputs = iter(["2", "1"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        prompt_video_type(entries, self.TRACKS_META)
        output = capsys.readouterr().out
        assert "https://youtu.be/back1" in output
        assert "https://youtu.be/back2" in output
