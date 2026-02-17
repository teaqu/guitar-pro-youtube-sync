#!/usr/bin/env python3
"""Tests for main.py"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from main import prompt_yes_no, prompt_browser_choice, BROWSERS


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
