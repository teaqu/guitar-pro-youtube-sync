"""Tests for interactive YouTube audio download retries."""

import sys
import types
from pathlib import Path
from unittest.mock import Mock

import main


def test_audio_download_succeeds_without_cookies(monkeypatch, tmp_path):
    download = Mock()
    monkeypatch.setattr(main, "download_youtube_audio", download)

    assert main.try_download_audio("video", tmp_path / "audio.mp3", 0, {}) is True
    download.assert_called_once_with("video", tmp_path / "audio.mp3", trim_start=0)


def test_audio_download_retries_saved_browser(monkeypatch, tmp_path):
    download = Mock(side_effect=[RuntimeError("blocked"), None])
    monkeypatch.setattr(main, "download_youtube_audio", download)

    assert main.try_download_audio("video", tmp_path / "audio.mp3", 1.5, {"cookie_browser": "chrome"}) is True
    assert download.call_args_list[1].kwargs["cookies_browser"] == "chrome"


def test_audio_download_tries_another_browser_after_manual_failure(monkeypatch, tmp_path, capsys):
    download = Mock(side_effect=[RuntimeError("blocked"), RuntimeError("reload"), None])
    choose_browser = Mock(side_effect=["safari", "chrome"])
    save = Mock()
    config = {}
    monkeypatch.setattr(main, "download_youtube_audio", download)
    monkeypatch.setattr(main, "prompt_browser_choice", choose_browser)
    monkeypatch.setattr(main, "save_config", save)

    assert main.try_download_audio("video", tmp_path / "audio.mp3", 0, config) is True
    assert [call.kwargs.get("cookies_browser") for call in download.call_args_list] == [None, "safari", "chrome"]
    assert config["cookie_browser"] == "chrome"
    save.assert_called_once_with(config)
    assert "try another browser" in capsys.readouterr().out


def test_safari_cookie_permission_denial_gives_macos_guidance_and_retries(monkeypatch, tmp_path, capsys):
    """A macOS Safari privacy denial must not silently abandon audio."""
    download = Mock(side_effect=[
        RuntimeError("HTTP Error 403: Forbidden"),
        PermissionError("[Errno 1] Operation not permitted: 'Cookies.binarycookies'"),
        RuntimeError("The page needs to be reloaded."),
        None,
    ])
    choose_browser = Mock(side_effect=["safari", "chrome", "firefox"])
    config = {}
    monkeypatch.setattr(main, "download_youtube_audio", download)
    monkeypatch.setattr(main, "prompt_browser_choice", choose_browser)
    monkeypatch.setattr(main, "save_config", Mock())

    assert main.try_download_audio("video", tmp_path / "audio.mp3", 0, config) is True

    output = capsys.readouterr().out
    assert "macOS blocked access to Safari's cookies" in output
    assert "Privacy & Security > Full Disk Access" in output
    assert choose_browser.call_count == 3
    assert config["cookie_browser"] == "firefox"


def test_audio_download_skips_only_when_user_explicitly_selects_skip(monkeypatch, tmp_path, capsys):
    download = Mock(side_effect=[RuntimeError("blocked"), RuntimeError("reload")])
    choose_browser = Mock(side_effect=["chrome", None])
    monkeypatch.setattr(main, "download_youtube_audio", download)
    monkeypatch.setattr(main, "prompt_browser_choice", choose_browser)

    assert main.try_download_audio("video", tmp_path / "audio.mp3", 0, {}) is False
    assert choose_browser.call_count == 2
    assert "Skipping audio." in capsys.readouterr().out


def test_process_song_reports_timing_only_file_after_explicit_audio_skip(monkeypatch, tmp_path, capsys):
    """The final result must say that an explicitly skipped download has no audio."""
    gp_file = tmp_path / "Artist - Song.gp"
    synced_file = tmp_path / "Artist - Song_synced.gp"
    inputs = iter(["19", "1", "y", str(len(main.BROWSERS) + 1)])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
    monkeypatch.setattr(main, "fetch_song_meta", Mock(return_value={
        "artist": "Artist", "title": "Song", "revisionId": 1, "tracks": [],
    }))
    monkeypatch.setattr(main.gen_gp, "fetch_all_tracks", Mock(return_value=({}, [])))
    monkeypatch.setattr(main.gen_gp, "generate_gp", Mock(side_effect=lambda _tracks, path, _meta: path.write_bytes(b"gp")))
    monkeypatch.setattr(main, "fetch_video_points", Mock(return_value=[]))
    monkeypatch.setattr(main, "prompt_video_type", Mock(return_value={"videoId": "video", "points": [0.0, 1.0]}))
    download = Mock(side_effect=RuntimeError("HTTP Error 403: Forbidden"))
    monkeypatch.setattr(main, "download_youtube_audio", download)
    monkeypatch.setattr(main, "sync_gp_file", Mock(side_effect=lambda _source, _points, output, **_kwargs: (output.write_bytes(b"synced"), [120])[1]))
    monkeypatch.setattr(main, "print_summary", Mock())
    monkeypatch.chdir(tmp_path)

    main.process_song({})

    output = capsys.readouterr().out
    assert "Skipping audio." in output
    assert "Audio was not downloaded; the synced file contains tab timing only." in output
    assert f"Done! File saved to: {synced_file}" in output
    assert gp_file.exists()
    assert synced_file.exists()
    download.assert_called_once()


def test_process_song_retries_safari_then_chrome_before_downloading(monkeypatch, tmp_path, capsys):
    """Exercise the CLI flow while replacing only the external downloader boundary."""
    inputs = iter(["19", "1", "y", "5", "1", "2"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
    monkeypatch.setattr(main, "fetch_song_meta", Mock(return_value={
        "artist": "Artist", "title": "Song", "revisionId": 1, "tracks": [],
    }))
    monkeypatch.setattr(main.gen_gp, "fetch_all_tracks", Mock(return_value=({}, [])))
    monkeypatch.setattr(main.gen_gp, "generate_gp", Mock(side_effect=lambda _tracks, path, _meta: path.write_bytes(b"gp")))
    monkeypatch.setattr(main, "fetch_video_points", Mock(return_value=[]))
    monkeypatch.setattr(main, "prompt_video_type", Mock(return_value={"videoId": "video", "points": [0.0, 1.0]}))

    attempts = []
    def download(_video, output, **kwargs):
        attempts.append(kwargs.get("cookies_browser"))
        if len(attempts) == 1:
            raise RuntimeError("HTTP Error 403: Forbidden")
        if attempts[-1] == "safari":
            raise PermissionError("[Errno 1] Operation not permitted: 'Cookies.binarycookies'")
        if attempts[-1] == "chrome":
            raise RuntimeError("The page needs to be reloaded.")
        output.write_bytes(b"audio")

    monkeypatch.setattr(main, "download_youtube_audio", download)
    monkeypatch.setattr(main, "save_config", Mock())
    monkeypatch.setattr(main, "sync_gp_file", Mock(side_effect=lambda _source, _points, output, **_kwargs: (output.write_bytes(b"synced"), [120])[1]))
    monkeypatch.setattr(main, "print_summary", Mock())
    monkeypatch.chdir(tmp_path)

    main.process_song({})

    output = capsys.readouterr().out
    assert attempts == [None, "safari", "chrome", "firefox"]
    assert "macOS blocked access to Safari's cookies" in output
    assert "Audio embedded in synced file." in output


def test_main_exits_cleanly_when_standard_input_closes(monkeypatch, capsys):
    monkeypatch.setattr(main, "load_config", Mock(return_value={}))
    monkeypatch.setattr(main, "process_song", Mock(side_effect=EOFError))
    monkeypatch.setattr(sys, "argv", ["main.py"])

    main.main()

    assert "Unexpected error" not in capsys.readouterr().out


def test_main_runs_self_test_before_loading_config(monkeypatch):
    run_self_test = Mock()
    monkeypatch.setitem(sys.modules, "diagnostics", types.SimpleNamespace(run_self_test=run_self_test))
    monkeypatch.setattr(main, "load_config", Mock(side_effect=AssertionError("must not load config")))
    monkeypatch.setattr(sys, "argv", ["main.py", "--self-test"])

    main.main()

    run_self_test.assert_called_once_with(live=False)
