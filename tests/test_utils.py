#!/usr/bin/env python3
"""Tests for utils.py"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import resource_path, get_ffmpeg_dir, load_config, save_config


class TestResourcePath:
    """Tests for resource_path()."""

    def test_returns_path_in_dev_mode(self):
        result = resource_path("assets/blank.gp")
        assert isinstance(result, Path)
        assert str(result).endswith("assets/blank.gp")

    def test_returns_existing_file(self):
        result = resource_path("assets/blank.gp")
        assert result.exists()

    def test_frozen_mode_uses_meipass(self):
        with patch.object(sys, 'frozen', True, create=True), \
             patch.object(sys, '_MEIPASS', '/tmp/fake_meipass', create=True):
            result = resource_path("assets/blank.gp")
            assert str(result) == "/tmp/fake_meipass/assets/blank.gp"


class TestGetFfmpegDir:
    """Tests for get_ffmpeg_dir()."""

    def test_returns_empty_string_when_no_bundled_ffmpeg(self):
        result = get_ffmpeg_dir()
        # In dev mode, ffmpeg_bin directory doesn't exist
        assert result == ""

    def test_returns_path_when_dir_exists(self, tmp_path):
        ffmpeg_dir = tmp_path / "ffmpeg_bin"
        ffmpeg_dir.mkdir()
        with patch('utils.resource_path', return_value=ffmpeg_dir):
            result = get_ffmpeg_dir()
            assert result == str(ffmpeg_dir)


class TestConfig:
    """Tests for load_config() and save_config()."""

    def test_load_config_returns_empty_dict_when_no_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr('utils.CONFIG_FILE', tmp_path / "nonexistent.json")
        result = load_config()
        assert result == {}

    def test_save_and_load_config_roundtrip(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        monkeypatch.setattr('utils.CONFIG_DIR', tmp_path)
        monkeypatch.setattr('utils.CONFIG_FILE', config_file)

        save_config({"cookie_browser": "firefox", "test_key": 42})
        result = load_config()
        assert result == {"cookie_browser": "firefox", "test_key": 42}

    def test_load_config_handles_corrupt_json(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        config_file.write_text("not valid json{{{")
        monkeypatch.setattr('utils.CONFIG_FILE', config_file)
        result = load_config()
        assert result == {}

    def test_save_config_creates_directory(self, tmp_path, monkeypatch):
        nested = tmp_path / "a" / "b"
        config_file = nested / "config.json"
        monkeypatch.setattr('utils.CONFIG_DIR', nested)
        monkeypatch.setattr('utils.CONFIG_FILE', config_file)

        save_config({"key": "value"})
        assert config_file.exists()
        assert json.loads(config_file.read_text()) == {"key": "value"}
