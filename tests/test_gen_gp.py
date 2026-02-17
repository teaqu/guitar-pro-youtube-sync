#!/usr/bin/env python3
"""Tests for gen_gp.py"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

import gen_gp
from gen_gp import escape_xml, midi_to_pitch_xml, get_instrument_type, parse_song_id, GPIFBuilder


class TestXMLEscaping:
    """Tests for XML escaping function."""

    def test_escape_xml_ampersand(self):
        assert escape_xml("Rock & Roll") == "Rock &amp; Roll"

    def test_escape_xml_less_than(self):
        assert escape_xml("a < b") == "a &lt; b"

    def test_escape_xml_greater_than(self):
        assert escape_xml("a > b") == "a &gt; b"

    def test_escape_xml_quotes(self):
        assert escape_xml('He said "hello"') == 'He said &quot;hello&quot;'

    def test_escape_xml_multiple(self):
        assert escape_xml('A & B < "C"') == 'A &amp; B &lt; &quot;C&quot;'

    def test_escape_xml_no_special_chars(self):
        assert escape_xml("Normal text") == "Normal text"


class TestMidiToPitch:
    """Tests for MIDI note to pitch XML conversion."""

    def test_midi_to_pitch_middle_c(self):
        # MIDI 60 = C4
        result = midi_to_pitch_xml(60)
        assert "<Step>C</Step>" in result
        assert "<Octave>5</Octave>" in result  # MIDI octave numbering
        assert "<Accidental/>" in result

    def test_midi_to_pitch_c_sharp(self):
        # MIDI 61 = C#4
        result = midi_to_pitch_xml(61)
        assert "<Step>C</Step>" in result
        assert "<Accidental>#</Accidental>" in result
        assert "<Octave>5</Octave>" in result

    def test_midi_to_pitch_a4(self):
        # MIDI 69 = A4 (440 Hz)
        result = midi_to_pitch_xml(69)
        assert "<Step>A</Step>" in result
        assert "<Accidental/>" in result
        assert "<Octave>5</Octave>" in result

    def test_midi_to_pitch_low_e(self):
        # MIDI 40 = E2 (low E string on guitar)
        result = midi_to_pitch_xml(40)
        assert "<Step>E</Step>" in result
        assert "<Accidental/>" in result
        assert "<Octave>3</Octave>" in result


class TestInstrumentType:
    """Tests for instrument type detection."""

    def test_get_instrument_type_drums(self):
        result = get_instrument_type("Drums")
        assert result["set_type"] == "drumKit"
        assert "Drums" in result["sound_path"]
        assert result["icon"] == 18

    def test_get_instrument_type_bass(self):
        result = get_instrument_type("Electric Bass")
        assert result["set_type"] == "electricBass"
        assert "Bass" in result["sound_path"]
        assert result["icon"] == 5

    def test_get_instrument_type_distortion_guitar(self):
        result = get_instrument_type("Distortion Guitar")
        assert result["set_type"] == "electricGuitar"
        assert "Distortion" in result["sound_path"]
        assert result["icon"] == 24

    def test_get_instrument_type_clean_guitar(self):
        result = get_instrument_type("Clean Guitar")
        assert result["set_type"] == "electricGuitar"
        assert "Clean" in result["sound_path"]
        assert result["icon"] == 24

    def test_get_instrument_type_acoustic_guitar(self):
        result = get_instrument_type("Acoustic Guitar")
        assert result["set_type"] == "steelGuitar"
        assert "Acoustic" in result["sound_path"]
        assert result["icon"] == 27

    def test_get_instrument_type_piano(self):
        result = get_instrument_type("Grand Piano")
        assert result["set_type"] == "piano"
        assert "Piano" in result["sound_path"]
        assert result["icon"] == 38

    def test_get_instrument_type_violin(self):
        result = get_instrument_type("Violin")
        assert result["set_type"] == "violin"
        assert result["icon"] == 1

    def test_get_instrument_type_trumpet(self):
        result = get_instrument_type("Trumpet")
        assert result["set_type"] == "trumpet"
        assert result["icon"] == 11

    def test_get_instrument_type_saxophone(self):
        result = get_instrument_type("Saxophone")
        assert result["set_type"] == "saxophone"
        assert result["icon"] == 19

    def test_get_instrument_type_default(self):
        # Unknown instrument should default to electric guitar
        result = get_instrument_type("Unknown Instrument")
        assert result["set_type"] == "electricGuitar"
        assert result["icon"] == 24

    def test_get_instrument_type_case_insensitive(self):
        # Should work with different cases
        result1 = get_instrument_type("DRUMS")
        result2 = get_instrument_type("drums")
        assert result1["set_type"] == result2["set_type"]


class TestSongIDParsing:
    """Tests for parsing song IDs from URLs or numbers."""

    def test_parse_song_id_number(self):
        assert parse_song_id("23063") == 23063

    def test_parse_song_id_url(self):
        url = "https://www.songsterr.com/a/wsa/gary-moore-parisienne-walkways-tab-s23063"
        assert parse_song_id(url) == 23063

    def test_parse_song_id_url_with_extras(self):
        url = "https://www.songsterr.com/a/wsa/ozzy-osbourne-crazy-train-tab-s61178?foo=bar"
        assert parse_song_id(url) == 61178

    def test_parse_song_id_whitespace(self):
        assert parse_song_id("  12345  ") == 12345

    def test_parse_song_id_invalid(self):
        with pytest.raises(ValueError):
            parse_song_id("not-a-valid-id")

    def test_parse_song_id_invalid_url(self):
        with pytest.raises(ValueError):
            parse_song_id("https://example.com/no-song-id")


class TestGPIFBuilder:
    """Tests for GPIFBuilder class."""

    def test_builder_initialization(self):
        tracks = [{"name": "Test Track", "measures": []}]
        builder = GPIFBuilder(tracks)
        assert builder.tracks == tracks
        assert builder._counters["note"] == 0
        assert builder._counters["beat"] == 0

    def test_builder_rhythm_caching(self):
        tracks = [{"name": "Test Track", "measures": []}]
        builder = GPIFBuilder(tracks)

        # Same rhythm should return same ID
        rid1 = builder._get_rhythm_id(4, 0, None)
        rid2 = builder._get_rhythm_id(4, 0, None)
        assert rid1 == rid2

    def test_builder_rhythm_different_values(self):
        tracks = [{"name": "Test Track", "measures": []}]
        builder = GPIFBuilder(tracks)

        # Different rhythms should return different IDs
        rid1 = builder._get_rhythm_id(4, 0, None)  # Quarter note
        rid2 = builder._get_rhythm_id(8, 0, None)  # Eighth note
        assert rid1 != rid2

    def test_builder_rhythm_with_dots(self):
        tracks = [{"name": "Test Track", "measures": []}]
        builder = GPIFBuilder(tracks)

        rid1 = builder._get_rhythm_id(4, 0, None)  # Quarter note
        rid2 = builder._get_rhythm_id(4, 1, None)  # Dotted quarter note
        assert rid1 != rid2

    def test_builder_rhythm_with_tuplet(self):
        tracks = [{"name": "Test Track", "measures": []}]
        builder = GPIFBuilder(tracks)

        rid1 = builder._get_rhythm_id(8, 0, None)  # Eighth note
        rid2 = builder._get_rhythm_id(8, 0, 3)     # Eighth note triplet
        assert rid1 != rid2

    def test_note_signature_basic(self):
        tracks = [{"name": "Test Track", "measures": []}]
        builder = GPIFBuilder(tracks)

        note1 = {
            "fret": 5, "gp_string": 2, "midi_note": 69,
            "articulation": 0, "tie_origin": False, "tie_destination": False,
            "hopo_origin": False, "hopo_destination": False,
        }
        note2 = {
            "fret": 5, "gp_string": 2, "midi_note": 69,
            "articulation": 0, "tie_origin": False, "tie_destination": False,
            "hopo_origin": False, "hopo_destination": False,
        }

        sig1 = builder._note_signature(note1)
        sig2 = builder._note_signature(note2)
        assert sig1 == sig2

    def test_note_signature_different(self):
        tracks = [{"name": "Test Track", "measures": []}]
        builder = GPIFBuilder(tracks)

        note1 = {
            "fret": 5, "gp_string": 2, "midi_note": 69,
            "articulation": 0, "tie_origin": False, "tie_destination": False,
            "hopo_origin": False, "hopo_destination": False,
        }
        note2 = {
            "fret": 7, "gp_string": 2, "midi_note": 71,  # Different fret
            "articulation": 0, "tie_origin": False, "tie_destination": False,
            "hopo_origin": False, "hopo_destination": False,
        }

        sig1 = builder._note_signature(note1)
        sig2 = builder._note_signature(note2)
        assert sig1 != sig2

    def test_build_simple_track(self):
        tracks = [{
            "name": "Test Track",
            "instrument": "Steel Guitar",
            "strings": 6,
            "tuning": [64, 59, 55, 50, 45, 40],  # Standard tuning
            "measures": [
                {
                    "voices": [
                        {
                            "beats": [
                                {
                                    "type": 4,  # Quarter note
                                    "notes": [{"fret": 0, "string": 0}]
                                }
                            ]
                        }
                    ]
                }
            ]
        }]

        builder = GPIFBuilder(tracks, {"artist": "Test Artist", "title": "Test Song"})
        gpif_xml = builder.build()

        # Check that XML is valid and contains expected elements
        assert "<?xml version" in gpif_xml
        assert "<GPIF>" in gpif_xml
        assert "</GPIF>" in gpif_xml
        assert "Test Artist" in gpif_xml
        assert "Test Song" in gpif_xml
        assert "Test Track" in gpif_xml

    def test_build_drum_track(self):
        tracks = [{
            "name": "Drums",
            "instrument": "Drums",
            "strings": 6,
            "tuning": None,  # Drums have no tuning
            "measures": [
                {
                    "voices": [
                        {
                            "beats": [
                                {
                                    "type": 4,  # Quarter note
                                    "notes": [{"fret": 36, "string": 0}]  # Bass drum (MIDI 36)
                                }
                            ]
                        }
                    ]
                }
            ]
        }]

        builder = GPIFBuilder(tracks)
        gpif_xml = builder.build()

        assert "<GPIF>" in gpif_xml
        assert "Drums" in gpif_xml


class TestRhythmMapping:
    """Tests for duration to rhythm name mapping."""

    def test_rhythm_xml_quarter_note(self):
        tracks = [{"name": "Test", "measures": []}]
        builder = GPIFBuilder(tracks)
        rid = builder._get_rhythm_id(4, 0, None)
        xml = builder._rhythm_xmls[0]
        assert "<NoteValue>Quarter</NoteValue>" in xml

    def test_rhythm_xml_eighth_note(self):
        tracks = [{"name": "Test", "measures": []}]
        builder = GPIFBuilder(tracks)
        rid = builder._get_rhythm_id(8, 0, None)
        xml = builder._rhythm_xmls[0]
        assert "<NoteValue>Eighth</NoteValue>" in xml

    def test_rhythm_xml_whole_note(self):
        tracks = [{"name": "Test", "measures": []}]
        builder = GPIFBuilder(tracks)
        rid = builder._get_rhythm_id(1, 0, None)
        xml = builder._rhythm_xmls[0]
        assert "<NoteValue>Whole</NoteValue>" in xml

    def test_rhythm_xml_dotted(self):
        tracks = [{"name": "Test", "measures": []}]
        builder = GPIFBuilder(tracks)
        rid = builder._get_rhythm_id(4, 1, None)
        xml = builder._rhythm_xmls[0]
        assert "AugmentationDot" in xml
        assert 'count="1"' in xml

    def test_rhythm_xml_triplet(self):
        tracks = [{"name": "Test", "measures": []}]
        builder = GPIFBuilder(tracks)
        rid = builder._get_rhythm_id(8, 0, 3)
        xml = builder._rhythm_xmls[0]
        assert "PrimaryTuplet" in xml
        assert 'num="3"' in xml
        assert 'den="2"' in xml


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
