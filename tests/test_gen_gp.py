#!/usr/bin/env python3
"""Tests for gen_gp.py"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

import gen_gp
from gen_gp import (escape_xml, midi_to_pitch_xml, get_instrument_type, parse_song_id,
                     GPIFBuilder, TRIPLET_FEEL_MAP, DRUM_NOTATION_PATCH)


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

    def test_get_instrument_type_tenor_sax(self):
        """Songsterr uses 'Tenor Sax' which should match saxophone."""
        result = get_instrument_type("Tenor Sax")
        assert result["set_type"] == "saxophone"
        assert "Winds" in result["sound_path"]

    def test_get_instrument_type_lead_voice(self):
        """Songsterr 'Lead 6 (voice)' should map to leadSynthesizer."""
        result = get_instrument_type("Lead 6 (voice)")
        assert result["set_type"] == "leadSynthesizer"
        assert "Synth" in result["sound_path"]

    def test_get_instrument_type_electric_piano(self):
        """'Electric Piano 1' should map to electricPiano, not generic piano."""
        result = get_instrument_type("Electric Piano 1")
        assert result["set_type"] == "electricPiano"
        assert "Electric Piano" in result["sound_path"]

    def test_get_instrument_type_overdriven_guitar(self):
        """'Overdriven Guitar' should map to Overdrive Guitar path."""
        result = get_instrument_type("Overdriven Guitar")
        assert result["set_type"] == "electricGuitar"
        assert "Overdrive" in result["sound_path"]

    def test_get_instrument_type_distortion_guitar(self):
        result = get_instrument_type("Distortion Guitar")
        assert result["set_type"] == "electricGuitar"
        assert "Distortion" in result["sound_path"]

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


class TestTripletFeel:
    """Tests for triplet feel handling in MasterBars."""

    def test_triplet_feel_map_values(self):
        assert TRIPLET_FEEL_MAP["8th"] == "Triplet8th"
        assert TRIPLET_FEEL_MAP["16th"] == "Triplet16th"

    def test_triplet_feel_in_master_bar(self):
        """MasterBars should include TripletFeel when present in track data."""
        tracks = [{
            "name": "Test Track",
            "instrument": "Steel Guitar",
            "strings": 6,
            "tuning": [64, 59, 55, 50, 45, 40],
            "measures": [
                {
                    "tripletFeel": "8th",
                    "voices": [{"beats": [{"type": 4, "notes": [{"fret": 0, "string": 0}]}]}]
                },
                {
                    "voices": [{"beats": [{"type": 4, "notes": [{"fret": 0, "string": 0}]}]}]
                }
            ]
        }]

        builder = GPIFBuilder(tracks, {"artist": "Test", "title": "Test"})
        gpif_xml = builder.build()

        assert "<TripletFeel>Triplet8th</TripletFeel>" in gpif_xml

    def test_triplet_feel_carries_forward(self):
        """TripletFeel set on one measure should carry to subsequent measures."""
        tracks = [{
            "name": "Test Track",
            "instrument": "Steel Guitar",
            "strings": 6,
            "tuning": [64, 59, 55, 50, 45, 40],
            "measures": [
                {
                    "tripletFeel": "8th",
                    "voices": [{"beats": [{"type": 4, "notes": [{"fret": 0, "string": 0}]}]}]
                },
                {
                    # No tripletFeel here — should inherit from measure 0
                    "voices": [{"beats": [{"type": 4, "notes": [{"fret": 0, "string": 0}]}]}]
                }
            ]
        }]

        builder = GPIFBuilder(tracks, {"artist": "Test", "title": "Test"})
        gpif_xml = builder.build()

        # Both MasterBars should have TripletFeel
        count = gpif_xml.count("<TripletFeel>Triplet8th</TripletFeel>")
        assert count == 2, f"Expected 2 TripletFeel elements, got {count}"

    def test_no_triplet_feel_when_absent(self):
        """MasterBars should not include TripletFeel when not set in track data."""
        tracks = [{
            "name": "Test Track",
            "instrument": "Steel Guitar",
            "strings": 6,
            "tuning": [64, 59, 55, 50, 45, 40],
            "measures": [
                {
                    "voices": [{"beats": [{"type": 4, "notes": [{"fret": 0, "string": 0}]}]}]
                }
            ]
        }]

        builder = GPIFBuilder(tracks, {"artist": "Test", "title": "Test"})
        gpif_xml = builder.build()

        assert "<TripletFeel>" not in gpif_xml


class TestDrumTrackFeatures:
    """Tests for drum track specific features."""

    def test_drum_notation_patch_in_output(self):
        """Drum tracks should include a NotationPatch element."""
        tracks = [{
            "name": "Drums",
            "instrument": "Drums",
            "strings": 6,
            "tuning": None,
            "measures": [
                {
                    "voices": [{"beats": [{"type": 4, "notes": [{"fret": 36, "string": 0}]}]}]
                }
            ]
        }]

        builder = GPIFBuilder(tracks)
        gpif_xml = builder.build()

        assert "<NotationPatch>" in gpif_xml
        assert "Drumkit-Standard" in gpif_xml
        assert "Snare (hit)" in gpif_xml
        assert "Hi-Hat (closed)" in gpif_xml
        assert "Kick (hit)" in gpif_xml

    def test_drum_sound_factory_role(self):
        """Drum tracks should use Factory role and include RSE SoundbankPatch."""
        tracks = [{
            "name": "Drums",
            "instrument": "Drums",
            "strings": 6,
            "tuning": None,
            "measures": [
                {
                    "voices": [{"beats": [{"type": 4, "notes": [{"fret": 36, "string": 0}]}]}]
                }
            ]
        }]

        builder = GPIFBuilder(tracks)
        gpif_xml = builder.build()

        assert "<Role>Factory</Role>" in gpif_xml
        assert "<SoundbankPatch>Drumkit-Master</SoundbankPatch>" in gpif_xml

    def test_non_drum_no_notation_patch(self):
        """Non-drum tracks should not include NotationPatch."""
        tracks = [{
            "name": "Guitar",
            "instrument": "Steel Guitar",
            "strings": 6,
            "tuning": [64, 59, 55, 50, 45, 40],
            "measures": [
                {
                    "voices": [{"beats": [{"type": 4, "notes": [{"fret": 0, "string": 0}]}]}]
                }
            ]
        }]

        builder = GPIFBuilder(tracks, {"artist": "Test", "title": "Test"})
        gpif_xml = builder.build()

        assert "<NotationPatch>" not in gpif_xml


class TestGPFileStructure:
    """Tests for overall GP file structural validity."""

    def _build_gpif(self, tracks, meta=None):
        builder = GPIFBuilder(tracks, meta or {"artist": "Test", "title": "Test"})
        return builder.build()

    def test_master_bar_xproperties_before_section(self):
        """XProperties should appear before Section in MasterBar."""
        tracks = [{
            "name": "Test Track",
            "instrument": "Steel Guitar",
            "strings": 6,
            "tuning": [64, 59, 55, 50, 45, 40],
            "measures": [
                {
                    "marker": {"text": "Intro"},
                    "voices": [{"beats": [{"type": 4, "notes": [{"fret": 0, "string": 0}]}]}]
                }
            ]
        }]

        gpif_xml = self._build_gpif(tracks)
        xprops_pos = gpif_xml.index("<XProperties>")
        section_pos = gpif_xml.index("<Section>")
        assert xprops_pos < section_pos, "XProperties should come before Section in MasterBar"

    def test_section_no_letter_element(self):
        """Section should contain Text but not Letter element."""
        tracks = [{
            "name": "Test Track",
            "instrument": "Steel Guitar",
            "strings": 6,
            "tuning": [64, 59, 55, 50, 45, 40],
            "measures": [
                {
                    "marker": {"text": "Verse"},
                    "voices": [{"beats": [{"type": 4, "notes": [{"fret": 0, "string": 0}]}]}]
                }
            ]
        }]

        gpif_xml = self._build_gpif(tracks)

        import xml.etree.ElementTree as ET
        root = ET.fromstring(gpif_xml)
        section = root.find('.//MasterBars/MasterBar/Section')
        assert section is not None
        assert section.find('Text') is not None
        assert section.find('Letter') is None, "Section should not contain Letter element"

    def test_referential_integrity(self):
        """All IDs referenced in the GPIF should point to existing elements."""
        tracks = [{
            "name": "Test Track",
            "instrument": "Steel Guitar",
            "strings": 6,
            "tuning": [64, 59, 55, 50, 45, 40],
            "measures": [
                {
                    "voices": [
                        {"beats": [
                            {"type": 4, "notes": [{"fret": 0, "string": 0}, {"fret": 2, "string": 1}]},
                            {"type": 8, "notes": [{"fret": 3, "string": 2}]},
                        ]}
                    ]
                },
                {
                    "voices": [
                        {"beats": [
                            {"type": 4, "notes": [{"fret": 0, "string": 0}]},
                        ]}
                    ]
                }
            ]
        }]

        gpif_xml = self._build_gpif(tracks)

        import xml.etree.ElementTree as ET
        root = ET.fromstring(gpif_xml)

        # Collect defined IDs
        note_ids = {n.get('id') for n in root.find('Notes')}
        beat_ids = {b.get('id') for b in root.find('Beats')}
        voice_ids = {v.get('id') for v in root.find('Voices')}
        bar_ids = {b.get('id') for b in root.find('Bars')}
        rhythm_ids = {r.get('id') for r in root.find('Rhythms')}

        # Check beat -> note references
        for beat in root.find('Beats'):
            notes_elem = beat.find('Notes')
            if notes_elem is not None and notes_elem.text:
                for nid in notes_elem.text.strip().split():
                    assert nid in note_ids, f"Beat references missing note {nid}"

        # Check voice -> beat references
        for voice in root.find('Voices'):
            beats_elem = voice.find('Beats')
            if beats_elem is not None and beats_elem.text:
                for bid in beats_elem.text.strip().split():
                    assert bid in beat_ids, f"Voice references missing beat {bid}"

        # Check bar -> voice references
        for bar in root.find('Bars'):
            voices_elem = bar.find('Voices')
            if voices_elem is not None and voices_elem.text:
                for vid in voices_elem.text.strip().split():
                    if vid != '-1':
                        assert vid in voice_ids, f"Bar references missing voice {vid}"

        # Check beat -> rhythm references
        for beat in root.find('Beats'):
            rhythm = beat.find('Rhythm')
            if rhythm is not None:
                assert rhythm.get('ref') in rhythm_ids, f"Beat references missing rhythm {rhythm.get('ref')}"

    def test_multi_track_with_drums(self):
        """Test GP file with both guitar and drum tracks has correct structure."""
        tracks = [
            {
                "name": "Guitar",
                "instrument": "Overdriven Guitar",
                "strings": 6,
                "tuning": [64, 59, 55, 50, 45, 40],
                "measures": [
                    {
                        "tripletFeel": "8th",
                        "voices": [{"beats": [{"type": 4, "notes": [{"fret": 5, "string": 0}]}]}]
                    }
                ]
            },
            {
                "name": "Drums",
                "instrument": "Drums",
                "strings": 6,
                "tuning": None,
                "measures": [
                    {
                        "voices": [{"beats": [{"type": 4, "notes": [{"fret": 36, "string": 0}]}]}]
                    }
                ]
            }
        ]

        gpif_xml = self._build_gpif(tracks)

        import xml.etree.ElementTree as ET
        root = ET.fromstring(gpif_xml)

        tracks_elem = root.find('Tracks')
        assert len(list(tracks_elem)) == 2

        # Guitar track should not have NotationPatch
        guitar_track = tracks_elem[0]
        assert guitar_track.find('NotationPatch') is None

        # Drum track should have NotationPatch
        drum_track = tracks_elem[1]
        assert drum_track.find('NotationPatch') is not None

        # Both MasterBars should have TripletFeel
        mbars = root.find('MasterBars')
        for mb in mbars:
            tf = mb.find('TripletFeel')
            assert tf is not None
            assert tf.text == "Triplet8th"

        # Drum track should have Factory sound role
        drum_sound = drum_track.find('Sounds/Sound')
        assert drum_sound.find('Role').text == "Factory"

        # Guitar track should have Overdrive path
        guitar_sound = guitar_track.find('Sounds/Sound')
        assert "Overdrive" in guitar_sound.find('Path').text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
