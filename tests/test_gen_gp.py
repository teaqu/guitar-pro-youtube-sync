#!/usr/bin/env python3
"""Tests for gen_gp.py"""

import pytest
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

import gen_gp
from gen_gp import (escape_xml, midi_to_pitch_xml, get_instrument_type, parse_song_id,
                     GPIFBuilder, TRIPLET_FEEL_MAP, DRUM_NOTATION_PATCH, tokenize_lyrics,
                     _icon_from_midi_program)


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
        result = get_instrument_type("Drums", 1024)
        assert result["set_type"] == "drumKit"
        assert "Drums" in result["sound_path"]
        assert result["icon"] == 18
        assert result["soundbank_patch"] is None  # drums handled separately

    def test_get_instrument_type_bass(self):
        result = get_instrument_type("Electric Bass (pick)", 34)
        assert result["set_type"] == "electricBass"
        assert "Bass" in result["sound_path"]
        assert result["icon"] == 5
        assert result["soundbank_patch"] == "Pre-Bass"
        assert any("EqBEq" in fx_id for fx_id, _ in result["effect_chain"])

    def test_get_instrument_type_distortion_guitar(self):
        result = get_instrument_type("Distortion Guitar", 30)
        assert result["set_type"] == "electricGuitar"
        assert "Distortion" in result["sound_path"]
        assert result["icon"] == 24
        assert result["soundbank_patch"] == "Classic-Guitar"
        assert any("OverdriveScreamer" in fx_id for fx_id, _ in result["effect_chain"])
        assert any("BritishStack" in fx_id for fx_id, _ in result["effect_chain"])

    def test_get_instrument_type_clean_guitar(self):
        result = get_instrument_type("Electric Guitar (clean)", 27)
        assert result["set_type"] == "electricGuitar"
        assert "Clean Guitar" in result["sound_path"]
        assert result["icon"] == 3
        assert result["soundbank_patch"] == "Strat-Guitar"
        assert any("ComboTop30" in fx_id for fx_id, _ in result["effect_chain"])

    def test_get_instrument_type_acoustic_guitar(self):
        result = get_instrument_type("Acoustic Guitar (steel)", 25)
        assert result["set_type"] == "steelGuitar"
        assert "Acoustic" in result["sound_path"]
        assert result["icon"] == 3
        assert result["soundbank_patch"] == "SteelString-Guitar"

    def test_get_instrument_type_piano(self):
        result = get_instrument_type("Grand Piano", 0)
        assert result["set_type"] == "acousticPiano"
        assert "Piano" in result["sound_path"]
        assert result["icon"] == 10
        assert result["soundbank_patch"] is None
        assert len(result["effect_chain"]) > 0  # still gets orchestral chain

    def test_get_instrument_type_violin(self):
        result = get_instrument_type("Violin", 40)
        assert result["set_type"] == "violin"
        assert result["icon"] == 11
        assert result["soundbank_patch"] == "Violin-Solo"
        assert any("Reverb" in fx_id for fx_id, _ in result["effect_chain"])

    def test_get_instrument_type_trumpet(self):
        result = get_instrument_type("Trumpet", 56)
        assert result["set_type"] == "trumpet"
        assert result["icon"] == 14
        assert result["soundbank_patch"] is None  # no specific patch for brass
        assert len(result["effect_chain"]) > 0

    def test_get_instrument_type_saxophone(self):
        result = get_instrument_type("Saxophone", 66)
        assert result["set_type"] == "saxophone"
        assert result["icon"] == 14
        assert result["soundbank_patch"] == "Sax-Solo"

    def test_get_instrument_type_tenor_sax(self):
        """Songsterr uses 'Tenor Sax' which should match saxophone."""
        result = get_instrument_type("Tenor Sax", 66)
        assert result["set_type"] == "saxophone"
        assert "Winds" in result["sound_path"]
        assert result["icon"] == 14
        assert result["soundbank_patch"] == "Sax-Solo"

    def test_get_instrument_type_lead_voice(self):
        """Songsterr 'Lead 6 (voice)' should map to leadSynthesizer."""
        result = get_instrument_type("Lead 6 (voice)", 85)
        assert result["set_type"] == "leadSynthesizer"
        assert "Synth" in result["sound_path"]
        assert result["icon"] == 12
        assert result["soundbank_patch"] is None

    def test_get_instrument_type_electric_piano(self):
        """'Electric Piano 1' should map to electricPiano, not generic piano."""
        result = get_instrument_type("Electric Piano 1", 4)
        assert result["set_type"] == "electricPiano"
        assert "Electric Piano" in result["sound_path"]
        assert result["icon"] == 10
        assert result["soundbank_patch"] is None

    def test_get_instrument_type_overdriven_guitar(self):
        """'Overdriven Guitar' should map to Overdrive Guitar path."""
        result = get_instrument_type("Overdriven Guitar", 29)
        assert result["set_type"] == "electricGuitar"
        assert "Overdrive" in result["sound_path"]
        assert result["icon"] == 4
        assert result["soundbank_patch"] == "Strat-Guitar"
        assert any("BritishVintage" in fx_id for fx_id, _ in result["effect_chain"])

    def test_get_instrument_type_cello(self):
        result = get_instrument_type("Cello", 42)
        assert result["set_type"] == "cello"
        assert result["soundbank_patch"] == "Cello-Solo"

    def test_effect_params_distortion_guitar(self):
        """Distortion guitar should use distortion-specific overdrive and EQ presets."""
        result = get_instrument_type("Distortion Guitar", 30)
        fx = {fid: params for fid, params in result["effect_chain"]}
        assert fx["E03_OverdriveScreamer"] == "0.85 0 0.67"
        assert fx["E30_EqGEq"] == "0.171717 0.474747 0.474747 0.474747 0.474747 0.474747 0.474747 0.222222"

    def test_effect_params_overdrive_guitar(self):
        """Overdrive guitar should use overdrive-specific pedal and EQ presets."""
        result = get_instrument_type("Overdriven Guitar", 29)
        fx = {fid: params for fid, params in result["effect_chain"]}
        assert fx["E03_OverdriveScreamer"] == "0.84 0.5 0.84"
        assert fx["E30_EqGEq"] == "0.494949 0.373737 0.494949 0.40404 0.484848 0.484848 0.484848 0.363636"

    def test_effect_params_clean_guitar(self):
        """Clean guitar should use clean-specific EQ preset."""
        result = get_instrument_type("Electric Guitar (clean)", 27)
        fx = {fid: params for fid, params in result["effect_chain"]}
        assert fx["E30_EqGEq"] == "0.494949 0.232323 0.373737 0.494949 0.373737 0.494949 0.494949 0.777778"

    def test_effect_params_violin(self):
        """Violin should use violin-specific 10-band EQ preset."""
        result = get_instrument_type("Violin", 40)
        fx = {fid: params for fid, params in result["effect_chain"]}
        assert fx["M08_GraphicEQ10Band"] == "1 1 0.96188 0.494949 0.494949 0.494949 0.494949 0.494949 0.363636 0.494949 0.444444 0.808081 0.606061"

    def test_effect_params_viola(self):
        """Viola should use viola-specific 10-band EQ preset."""
        result = get_instrument_type("Viola", 41)
        fx = {fid: params for fid, params in result["effect_chain"]}
        assert fx["M08_GraphicEQ10Band"] == "0 0 0.37616 0.494949 0.494949 0.606061 0.414141 0.333333 0.414141 0.494949 0.494949 0.494949 0.494949"

    def test_effect_params_cello(self):
        """Cello should use cello-specific 10-band EQ preset."""
        result = get_instrument_type("Cello", 42)
        fx = {fid: params for fid, params in result["effect_chain"]}
        assert fx["M08_GraphicEQ10Band"] == "0 0 0.40476 0.494949 0.494949 0.494949 0.494949 0.494949 0.494949 0.494949 0.494949 0.494949 0.494949"

    def test_get_instrument_type_default(self):
        # Unknown instrument should default to electric guitar
        result = get_instrument_type("Unknown Instrument")
        assert result["set_type"] == "electricGuitar"
        assert result["soundbank_patch"] == "Strat-Guitar"

    def test_get_instrument_type_case_insensitive(self):
        # Should work with different cases
        result1 = get_instrument_type("DRUMS", 1024)
        result2 = get_instrument_type("drums", 1024)
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
        assert "<Tones>1 1</Tones>" in gpif_xml
        assert '<Effect id="M06_DynamicAnalogDynamic">' in gpif_xml
        assert '<Effect id="M08_GraphicEQ10Band">' in gpif_xml
        assert '<Effect id="M05_StudioReverbPlatePercussive">' in gpif_xml

    def test_non_drum_rse_sound(self):
        """Non-drum tracks should include RSE SoundbankPatch, Pickups and EffectChain."""
        tracks = [{
            "name": "Guitar",
            "instrument": "Distortion Guitar",
            "instrumentId": 30,
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

        assert "<SoundbankPatch>Classic-Guitar</SoundbankPatch>" in gpif_xml
        assert "<Tones>1 1</Tones>" in gpif_xml
        assert '<Effect id="E03_OverdriveScreamer">' in gpif_xml
        assert '<Effect id="A06_StackBritishStack">' in gpif_xml
        assert '<Effect id="E30_EqGEq">' in gpif_xml
        assert "<Role>User</Role>" in gpif_xml

    def test_multi_sound_track(self):
        """Tracks with multiple sounds should have multiple Sound entries and Sound automations."""
        tracks = [{
            "name": "Bass",
            "instrument": "Electric Bass (pick)",
            "instrumentId": 34,
            "strings": 4,
            "tuning": [43, 38, 33, 28],
            "sounds": [
                {"instrumentId": 34, "label": "Electric Bass (pick)"},
                {"instrumentId": 29, "label": "Overdriven Guitar"},
            ],
            "trackAutomations": {
                "trackSoundAutomations": [
                    {"soundId": 1, "measure": 20, "position": 0},
                    {"soundId": 0, "measure": 36, "position": 0},
                ]
            },
            "measures": [
                {
                    "voices": [{"beats": [{"type": 4, "notes": [{"fret": 0, "string": 0}]}]}]
                }
            ]
        }]

        builder = GPIFBuilder(tracks, {"artist": "Test", "title": "Test"})
        gpif_xml = builder.build()

        # Should have both sounds
        assert "<SoundbankPatch>Pre-Bass</SoundbankPatch>" in gpif_xml
        assert "<SoundbankPatch>Strat-Guitar</SoundbankPatch>" in gpif_xml
        # Should have sound automations
        assert "<Bar>20</Bar>" in gpif_xml
        assert "<Bar>36</Bar>" in gpif_xml
        assert "Overdriven Guitar;User]]>" in gpif_xml
        assert "Electric Bass (pick);User]]>" in gpif_xml

    def test_non_drum_sound_automation(self):
        """Single-sound non-drum tracks should still get a default Sound automation."""
        tracks = [{
            "name": "Guitar",
            "instrument": "Distortion Guitar",
            "instrumentId": 30,
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

        assert "Distortion Guitar;User]]></Value>" in gpif_xml
        assert "<Type>Sound</Type>" in gpif_xml

    def test_no_soundbank_patch_instrument(self):
        """Instruments without a soundbank_patch should produce self-closing SoundbankPatch."""
        tracks = [{
            "name": "Synth",
            "instrument": "Lead 6 (voice)",
            "instrumentId": 85,
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

        assert "<SoundbankPatch/>" in gpif_xml
        assert "<Tones>1 1</Tones>" in gpif_xml
        assert "<EffectChain>" in gpif_xml

    def test_sound_automation_fractional_position(self):
        """Sound automations with non-zero position should convert ticks to fraction (pos/960)."""
        tracks = [{
            "name": "Guitar",
            "instrument": "Distortion Guitar",
            "instrumentId": 30,
            "strings": 6,
            "tuning": [64, 59, 55, 50, 45, 40],
            "sounds": [
                {"instrumentId": 30, "label": "Distortion Guitar"},
                {"instrumentId": 27, "label": "Electric Guitar (clean)"},
            ],
            "trackAutomations": {
                "trackSoundAutomations": [
                    {"soundId": 1, "measure": 0, "position": 0},
                    {"soundId": 0, "measure": 10, "position": 480},
                ]
            },
            "measures": [
                {
                    "voices": [{"beats": [{"type": 4, "notes": [{"fret": 0, "string": 0}]}]}]
                }
            ]
        }]

        builder = GPIFBuilder(tracks, {"artist": "Test", "title": "Test"})
        gpif_xml = builder.build()

        assert "<Position>0.5</Position>" in gpif_xml
        assert "<Bar>10</Bar>" in gpif_xml

    def test_sound_automation_value_cdata_wrapped(self):
        """Sound automation <Value> must be CDATA-wrapped for GP8 to apply sound switches."""
        tracks = [{
            "name": "Guitar",
            "instrument": "Distortion Guitar",
            "instrumentId": 30,
            "strings": 6,
            "tuning": [64, 59, 55, 50, 45, 40],
            "sounds": [
                {"instrumentId": 30, "label": "Distortion Guitar"},
                {"instrumentId": 27, "label": "Electric Guitar (clean)"},
            ],
            "trackAutomations": {
                "trackSoundAutomations": [
                    {"soundId": 1, "measure": 0, "position": 0},
                    {"soundId": 0, "measure": 19, "position": 0},
                ]
            },
            "measures": [
                {
                    "voices": [{"beats": [{"type": 4, "notes": [{"fret": 0, "string": 0}]}]}]
                }
            ]
        }]

        builder = GPIFBuilder(tracks, {"artist": "Test", "title": "Test"})
        gpif_xml = builder.build()

        # Automation values must use CDATA or GP8 won't apply sound switches during playback
        assert "<Value><![CDATA[Stringed/Electric Guitars/Clean Guitar;Electric Guitar (clean);User]]></Value>" in gpif_xml
        assert "<Value><![CDATA[Stringed/Electric Guitars/Distortion Guitar;Distortion Guitar;User]]></Value>" in gpif_xml

    def test_single_sound_automation_value_cdata_wrapped(self):
        """Single-sound tracks should also have CDATA-wrapped automation values."""
        tracks = [{
            "name": "Guitar",
            "instrument": "Distortion Guitar",
            "instrumentId": 30,
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

        assert "<Value><![CDATA[Stringed/Electric Guitars/Distortion Guitar;Distortion Guitar;User]]></Value>" in gpif_xml

    def test_bass_rse_sound(self):
        """Bass tracks should get Pre-Bass patch and bass-specific EQ."""
        tracks = [{
            "name": "Bass",
            "instrument": "Electric Bass (pick)",
            "instrumentId": 34,
            "strings": 4,
            "tuning": [43, 38, 33, 28],
            "measures": [
                {
                    "voices": [{"beats": [{"type": 4, "notes": [{"fret": 0, "string": 0}]}]}]
                }
            ]
        }]

        builder = GPIFBuilder(tracks, {"artist": "Test", "title": "Test"})
        gpif_xml = builder.build()

        assert "<SoundbankPatch>Pre-Bass</SoundbankPatch>" in gpif_xml
        assert '<Effect id="A10_StackClassic">' in gpif_xml
        assert '<Effect id="E31_EqBEq">' in gpif_xml

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


class TestTokenizeLyrics:
    """Tests for lyrics tokenization."""

    def test_simple_words(self):
        assert tokenize_lyrics("hello world") == ["hello", "world"]

    def test_hyphenated_syllables(self):
        """Hyphens split syllables; hyphen stays with preceding part."""
        assert tokenize_lyrics("Mo-ney") == ["Mo-", "ney"]

    def test_multiple_hyphens(self):
        assert tokenize_lyrics("beau-ti-ful") == ["beau-", "ti-", "ful"]

    def test_mixed_words_and_hyphens(self):
        assert tokenize_lyrics("Mo-ney, get a-way.") == ["Mo-", "ney,", "get", "a-", "way."]

    def test_empty_string(self):
        assert tokenize_lyrics("") == []

    def test_whitespace_only(self):
        assert tokenize_lyrics("   ") == []

    def test_multiple_spaces(self):
        """Multiple spaces within a line produce skip sentinels (N-1 for N spaces)."""
        assert tokenize_lyrics("word1   word2") == ["word1", "\n", "\n", "word2"]

    def test_no_hyphens(self):
        assert tokenize_lyrics("just plain words here") == ["just", "plain", "words", "here"]

    def test_trailing_hyphen(self):
        """A word ending in hyphen produces a token with trailing hyphen."""
        assert tokenize_lyrics("go-") == ["go-"]


class TestBeatLevelLyrics:
    """Tests for beat-level lyrics assignment."""

    def _make_track_with_lyrics(self, num_measures, notes_per_measure, lyrics_text,
                                 lyrics_offset=0):
        """Helper to create a track with notes and lyrics."""
        measures = []
        for _ in range(num_measures):
            beats = []
            for j in range(notes_per_measure):
                beats.append({
                    "type": 4,
                    "notes": [{"fret": j, "string": 0}]
                })
            measures.append({"voices": [{"beats": beats}]})

        return {
            "name": "Vocals",
            "instrument": "Lead 6 (voice)",
            "strings": 6,
            "tuning": [64, 59, 55, 50, 45, 40],
            "measures": measures,
            "newLyrics": [
                {"text": lyrics_text, "offset": lyrics_offset},
            ],
        }

    def test_lyrics_assigned_to_beats(self):
        """Beats with notes should get lyrics tokens."""
        track = self._make_track_with_lyrics(2, 2, "one two three four")
        builder = GPIFBuilder([track], {"artist": "Test", "title": "Test"})
        gpif_xml = builder.build()

        assert "<Lyrics>" in gpif_xml
        assert "<![CDATA[one]]>" in gpif_xml
        assert "<![CDATA[two]]>" in gpif_xml
        assert "<![CDATA[three]]>" in gpif_xml
        assert "<![CDATA[four]]>" in gpif_xml

    def test_lyrics_offset(self):
        """Lyrics with offset > 0 should skip early measures."""
        track = self._make_track_with_lyrics(3, 1, "hello world", lyrics_offset=1)
        builder = GPIFBuilder([track], {"artist": "Test", "title": "Test"})
        gpif_xml = builder.build()

        # Should have lyrics on beats in measures 1 and 2, not measure 0
        assert "<![CDATA[hello]]>" in gpif_xml
        assert "<![CDATA[world]]>" in gpif_xml

    def test_lyrics_skip_rest_beats(self):
        """Rest beats should not consume lyrics tokens."""
        measures = [
            {"voices": [{"beats": [
                {"type": 4, "notes": [{"fret": 0, "string": 0}]},
                {"type": 4, "rest": True},
                {"type": 4, "notes": [{"fret": 2, "string": 0}]},
            ]}]},
        ]
        track = {
            "name": "Vocals", "instrument": "Lead 6 (voice)",
            "strings": 6, "tuning": [64, 59, 55, 50, 45, 40],
            "measures": measures,
            "newLyrics": [{"text": "first second", "offset": 0}],
        }
        builder = GPIFBuilder([track], {"artist": "Test", "title": "Test"})
        gpif_xml = builder.build()

        assert "<![CDATA[first]]>" in gpif_xml
        assert "<![CDATA[second]]>" in gpif_xml

    def test_lyrics_hyphenated_in_beats(self):
        """Hyphenated syllables should appear as separate beat lyrics."""
        track = self._make_track_with_lyrics(1, 3, "Mo-ney get")
        builder = GPIFBuilder([track], {"artist": "Test", "title": "Test"})
        gpif_xml = builder.build()

        assert "<![CDATA[Mo-]]>" in gpif_xml
        assert "<![CDATA[ney]]>" in gpif_xml
        assert "<![CDATA[get]]>" in gpif_xml

    def test_no_lyrics_without_newlyrics(self):
        """Tracks without newLyrics should not have beat-level lyrics."""
        tracks = [{
            "name": "Guitar", "instrument": "Steel Guitar",
            "strings": 6, "tuning": [64, 59, 55, 50, 45, 40],
            "measures": [{"voices": [{"beats": [
                {"type": 4, "notes": [{"fret": 0, "string": 0}]}
            ]}]}],
        }]
        builder = GPIFBuilder(tracks, {"artist": "Test", "title": "Test"})
        gpif_xml = builder.build()

        # Should have track-level Lyrics (dispatched) but no beat-level Lyrics
        import xml.etree.ElementTree as ET
        root = ET.fromstring(gpif_xml)
        for beat in root.find('Beats'):
            assert beat.find('Lyrics') is None

    def test_lyrics_five_lines_padded(self):
        """Beat lyrics should have 5 Line elements (GP standard), empty lines padded."""
        track = self._make_track_with_lyrics(1, 1, "word")
        builder = GPIFBuilder([track], {"artist": "Test", "title": "Test"})
        gpif_xml = builder.build()

        import xml.etree.ElementTree as ET
        root = ET.fromstring(gpif_xml)
        for beat in root.find('Beats'):
            lyrics_elem = beat.find('Lyrics')
            if lyrics_elem is not None:
                lines = lyrics_elem.findall('Line')
                assert len(lines) == 5, f"Expected 5 lyric lines, got {len(lines)}"
                assert lines[0].text == "word"
                # Lines 1-4 should be empty
                for line in lines[1:]:
                    assert line.text is None or line.text == ""

    def test_lyrics_beat_signature_includes_lyrics(self):
        """Beats with different lyrics should not be deduplicated."""
        measures = [
            {"voices": [{"beats": [
                {"type": 4, "notes": [{"fret": 0, "string": 0}]},
                {"type": 4, "notes": [{"fret": 0, "string": 0}]},
            ]}]},
        ]
        track = {
            "name": "Vocals", "instrument": "Lead 6 (voice)",
            "strings": 6, "tuning": [64, 59, 55, 50, 45, 40],
            "measures": measures,
            "newLyrics": [{"text": "hello world", "offset": 0}],
        }
        builder = GPIFBuilder([track], {"artist": "Test", "title": "Test"})
        gpif_xml = builder.build()

        # Both lyrics should appear even though the beats have same notes
        assert "<![CDATA[hello]]>" in gpif_xml
        assert "<![CDATA[world]]>" in gpif_xml

    def test_track_level_lyrics_dispatched(self):
        """Track-level lyrics should have dispatched='true' attribute."""
        track = self._make_track_with_lyrics(1, 1, "word")
        builder = GPIFBuilder([track], {"artist": "Test", "title": "Test"})
        gpif_xml = builder.build()

        assert 'dispatched="true"' in gpif_xml

    def test_voice0_only_for_lyrics(self):
        """Only voice 0 beats should receive lyrics, not beats from other voices."""
        measures = [
            {"voices": [
                {"beats": [
                    {"type": 4, "notes": [{"fret": 0, "string": 0}]},
                    {"type": 4, "notes": [{"fret": 1, "string": 0}]},
                ]},
                {"beats": [
                    {"type": 4, "notes": [{"fret": 5, "string": 1}]},
                    {"type": 4, "notes": [{"fret": 6, "string": 1}]},
                ]},
            ]},
        ]
        track = {
            "name": "Vocals", "instrument": "Lead 6 (voice)",
            "strings": 6, "tuning": [64, 59, 55, 50, 45, 40],
            "measures": measures,
            "newLyrics": [{"text": "only-one", "offset": 0}],
        }
        builder = GPIFBuilder([track], {"artist": "Test", "title": "Test"})
        gpif_xml = builder.build()

        import xml.etree.ElementTree as ET
        root = ET.fromstring(gpif_xml)
        lyrics_beats = [b for b in root.find('Beats') if b.find('Lyrics') is not None]
        # Should have lyrics on 2 beats (from "only-" and "one")
        # Voice 1 beats should NOT consume lyrics tokens
        lyrics_texts = []
        for b in lyrics_beats:
            line = b.find('Lyrics/Line')
            if line is not None and line.text:
                lyrics_texts.append(line.text)
        assert "only-" in lyrics_texts
        assert "one" in lyrics_texts
        assert len(lyrics_texts) == 2


class TestGraceNotes:
    """Tests for grace note handling (Songsterr graceNote -> GP GraceNotes)."""

    def _build_gpif(self, tracks, meta=None):
        builder = GPIFBuilder(tracks, meta or {"artist": "Test", "title": "Test"})
        return builder.build()

    def _make_track(self, beats):
        """Helper to create a single-measure track with given beats."""
        return {
            "name": "Guitar", "instrument": "Distortion Guitar",
            "strings": 6, "tuning": [64, 59, 55, 50, 45, 40],
            "measures": [{"voices": [{"beats": beats}]}],
        }

    def test_grace_note_on_beat(self):
        """graceNote='onBeat' should produce <GraceNotes>OnBeat</GraceNotes>."""
        track = self._make_track([
            {"type": 32, "graceNote": "onBeat", "notes": [{"fret": 3, "string": 2}]},
            {"type": 8, "notes": [{"fret": 5, "string": 2}]},
        ])
        gpif_xml = self._build_gpif([track])
        assert "<GraceNotes>OnBeat</GraceNotes>" in gpif_xml

    def test_grace_note_before_beat(self):
        """graceNote='beforeBeat' should produce <GraceNotes>BeforeBeat</GraceNotes>."""
        track = self._make_track([
            {"type": 16, "graceNote": "beforeBeat", "notes": [{"fret": 3, "string": 2}]},
            {"type": 8, "notes": [{"fret": 5, "string": 2}]},
        ])
        gpif_xml = self._build_gpif([track])
        assert "<GraceNotes>BeforeBeat</GraceNotes>" in gpif_xml

    def test_no_grace_note_without_flag(self):
        """Beats without graceNote should not have <GraceNotes>."""
        track = self._make_track([
            {"type": 8, "notes": [{"fret": 5, "string": 2}]},
        ])
        gpif_xml = self._build_gpif([track])
        assert "<GraceNotes>" not in gpif_xml

    def test_grace_note_dedup_separation(self):
        """Grace and non-grace beats with same notes/rhythm must not be deduplicated."""
        track = self._make_track([
            {"type": 32, "graceNote": "onBeat", "notes": [{"fret": 3, "string": 2}]},
            {"type": 32, "notes": [{"fret": 3, "string": 2}]},
        ])
        builder = GPIFBuilder([track], {"artist": "Test", "title": "Test"})
        gpif_xml = builder.build()

        root = ET.fromstring(gpif_xml)
        beats_with_grace = [b for b in root.find('Beats') if b.find('GraceNotes') is not None]
        beats_without_grace = [b for b in root.find('Beats')
                               if b.find('GraceNotes') is None and b.find('Notes') is not None]
        # Both beats should exist as separate elements
        assert len(beats_with_grace) >= 1
        assert len(beats_without_grace) >= 1
        # Their IDs must differ
        grace_ids = {b.get('id') for b in beats_with_grace}
        non_grace_ids = {b.get('id') for b in beats_without_grace}
        assert grace_ids.isdisjoint(non_grace_ids)

    def test_grace_note_in_full_measure(self):
        """A measure with a grace note should not overflow when parsed correctly."""
        track = self._make_track([
            {"type": 8, "notes": [{"fret": 0, "string": 4}]},
            {"type": 32, "graceNote": "onBeat", "notes": [{"fret": 3, "string": 2}]},
            {"type": 8, "notes": [{"fret": 4, "string": 2}]},
            {"type": 8, "notes": [{"fret": 4, "string": 2}]},
            {"type": 8, "notes": [{"fret": 0, "string": 3}]},
            {"type": 8, "notes": [{"fret": 4, "string": 2}]},
            {"type": 8, "notes": [{"fret": 3, "string": 3}]},
            {"type": 8, "notes": [{"fret": 4, "string": 2}]},
            {"type": 8, "notes": [{"fret": 0, "string": 1}]},
        ])
        gpif_xml = self._build_gpif([track])

        root = ET.fromstring(gpif_xml)
        # The grace note beat should have the GraceNotes tag
        grace_beats = [b for b in root.find('Beats') if b.find('GraceNotes') is not None]
        assert len(grace_beats) >= 1
        assert grace_beats[0].find('GraceNotes').text == "OnBeat"


class TestLetRing:
    """Tests for let ring handling (Songsterr letRing -> GP LetRing)."""

    def _build_gpif(self, tracks, meta=None):
        builder = GPIFBuilder(tracks, meta or {"artist": "Test", "title": "Test"})
        return builder.build()

    def _make_track(self, beats):
        return {
            "name": "Guitar", "instrument": "Distortion Guitar",
            "strings": 6, "tuning": [64, 59, 55, 50, 45, 40],
            "measures": [{"voices": [{"beats": beats}]}],
        }

    def test_let_ring_on_notes(self):
        """letRing=True on a beat should produce <LetRing/> on its notes."""
        track = self._make_track([
            {"type": 8, "letRing": True, "notes": [{"fret": 0, "string": 3}]},
        ])
        gpif_xml = self._build_gpif([track])
        assert "<LetRing/>" in gpif_xml

    def test_no_let_ring_without_flag(self):
        """Beats without letRing should not produce <LetRing/> on notes."""
        track = self._make_track([
            {"type": 8, "notes": [{"fret": 0, "string": 3}]},
        ])
        gpif_xml = self._build_gpif([track])
        assert "<LetRing/>" not in gpif_xml

    def test_let_ring_multiple_notes_in_beat(self):
        """All notes in a letRing beat should get <LetRing/>."""
        track = self._make_track([
            {"type": 4, "letRing": True, "notes": [
                {"fret": 0, "string": 0},
                {"fret": 2, "string": 1},
                {"fret": 2, "string": 2},
            ]},
        ])
        gpif_xml = self._build_gpif([track])

        root = ET.fromstring(gpif_xml)
        notes_with_lr = [n for n in root.find('Notes') if n.find('LetRing') is not None]
        assert len(notes_with_lr) == 3

    def test_let_ring_dedup_separation(self):
        """Notes with and without letRing on same fret/string must not be deduplicated."""
        track = self._make_track([
            {"type": 8, "letRing": True, "notes": [{"fret": 0, "string": 3}]},
            {"type": 8, "notes": [{"fret": 0, "string": 3}]},
        ])
        builder = GPIFBuilder([track], {"artist": "Test", "title": "Test"})
        gpif_xml = builder.build()

        root = ET.fromstring(gpif_xml)
        notes_with_lr = [n for n in root.find('Notes') if n.find('LetRing') is not None]
        notes_without_lr = [n for n in root.find('Notes') if n.find('LetRing') is None]
        assert len(notes_with_lr) >= 1
        assert len(notes_without_lr) >= 1
        lr_ids = {n.get('id') for n in notes_with_lr}
        no_lr_ids = {n.get('id') for n in notes_without_lr}
        assert lr_ids.isdisjoint(no_lr_ids)

    def test_let_ring_mixed_beats(self):
        """Only beats with letRing=True should have notes with <LetRing/>."""
        track = self._make_track([
            {"type": 8, "letRing": True, "notes": [{"fret": 0, "string": 3}]},
            {"type": 8, "notes": [{"fret": 2, "string": 3}]},
            {"type": 8, "letRing": True, "notes": [{"fret": 3, "string": 3}]},
        ])
        gpif_xml = self._build_gpif([track])

        root = ET.fromstring(gpif_xml)
        notes_with_lr = [n for n in root.find('Notes') if n.find('LetRing') is not None]
        # Frets 0 and 3 should have LetRing, fret 2 should not
        lr_frets = set()
        for n in notes_with_lr:
            for prop in n.findall('.//Property'):
                if prop.get('name') == 'Fret':
                    lr_frets.add(prop.find('Fret').text)
        assert '0' in lr_frets
        assert '3' in lr_frets
        assert '2' not in lr_frets


class TestChordNames:
    """Tests for chord name handling (Songsterr chord -> GP DiagramCollection + Beat Chord)."""

    def _build_gpif(self, tracks, meta=None):
        builder = GPIFBuilder(tracks, meta or {"artist": "Test", "title": "Test"})
        return builder.build()

    def _make_track(self, beats):
        return {
            "name": "Guitar", "instrument": "Distortion Guitar",
            "strings": 6, "tuning": [64, 59, 55, 50, 45, 40],
            "measures": [{"voices": [{"beats": beats}]}],
        }

    def test_chord_name_in_diagram_collection(self):
        """Beats with chord data should populate the track's DiagramCollection."""
        track = self._make_track([
            {"type": 4, "chord": {"text": "Am"}, "notes": [{"fret": 0, "string": 0}]},
        ])
        gpif_xml = self._build_gpif([track])

        root = ET.fromstring(gpif_xml)
        diag_prop = root.find('.//Track//Property[@name="DiagramCollection"]')
        items = diag_prop.find('Items')
        assert len(items) == 1
        assert items[0].get('name') == 'Am'

    def test_chord_ref_on_beat(self):
        """Beats with chord data should have <Chord>id</Chord> referencing DiagramCollection."""
        track = self._make_track([
            {"type": 4, "chord": {"text": "E5"}, "notes": [{"fret": 0, "string": 0}]},
        ])
        gpif_xml = self._build_gpif([track])

        root = ET.fromstring(gpif_xml)
        chord_beats = [b for b in root.find('Beats') if b.find('Chord') is not None]
        assert len(chord_beats) >= 1
        assert chord_beats[0].find('Chord').text == '0'

    def test_multiple_chords(self):
        """Multiple distinct chord names should create separate DiagramCollection items."""
        track = self._make_track([
            {"type": 4, "chord": {"text": "Ab"}, "notes": [{"fret": 4, "string": 0}]},
            {"type": 4, "chord": {"text": "E5"}, "notes": [{"fret": 0, "string": 0}]},
            {"type": 4, "chord": {"text": "Ab"}, "notes": [{"fret": 4, "string": 0}]},
        ])
        gpif_xml = self._build_gpif([track])

        root = ET.fromstring(gpif_xml)
        diag_prop = root.find('.//Track//Property[@name="DiagramCollection"]')
        items = diag_prop.find('Items')
        names = [item.get('name') for item in items]
        assert 'Ab' in names
        assert 'E5' in names
        assert len(items) == 2  # Ab appears twice but only one item

    def test_no_chord_without_data(self):
        """Beats without chord data should not have <Chord> element."""
        track = self._make_track([
            {"type": 4, "notes": [{"fret": 0, "string": 0}]},
        ])
        gpif_xml = self._build_gpif([track])

        root = ET.fromstring(gpif_xml)
        chord_beats = [b for b in root.find('Beats') if b.find('Chord') is not None]
        assert len(chord_beats) == 0

    def test_chord_show_name_not_diagram(self):
        """Chord diagram items should have ShowName=true and ShowDiagram=false."""
        track = self._make_track([
            {"type": 4, "chord": {"text": "G"}, "notes": [{"fret": 3, "string": 0}]},
        ])
        gpif_xml = self._build_gpif([track])

        root = ET.fromstring(gpif_xml)
        diag = root.find('.//Track//Property[@name="DiagramCollection"]//Diagram')
        props = {p.get('name'): p.get('value') for p in diag.findall('Property')}
        assert props['ShowName'] == 'true'
        assert props['ShowDiagram'] == 'false'

    def test_chord_ref_uses_cdata(self):
        """Beat chord refs must use CDATA wrapper for GP compatibility."""
        track = self._make_track([
            {"type": 4, "chord": {"text": "Am"}, "notes": [{"fret": 0, "string": 0}]},
        ])
        gpif_xml = self._build_gpif([track])

        assert "<Chord><![CDATA[0]]></Chord>" in gpif_xml

    def test_chord_dedup_separation(self):
        """Beats with different chords on same notes/rhythm must not be deduplicated."""
        track = self._make_track([
            {"type": 4, "chord": {"text": "Am"}, "notes": [{"fret": 0, "string": 0}]},
            {"type": 4, "chord": {"text": "Em"}, "notes": [{"fret": 0, "string": 0}]},
        ])
        builder = GPIFBuilder([track], {"artist": "Test", "title": "Test"})
        gpif_xml = builder.build()

        root = ET.fromstring(gpif_xml)
        chord_beats = [b for b in root.find('Beats') if b.find('Chord') is not None]
        chord_vals = {b.find('Chord').text for b in chord_beats}
        assert len(chord_vals) == 2  # Two different chord refs


class TestLyricsSkipSentinels:
    """Tests for the space-based skip sentinel mechanism in lyrics positioning."""

    def test_leading_spaces_produce_sentinels(self):
        """Leading spaces on a line emit skip sentinels between phrases."""
        tokens = tokenize_lyrics("hello.\n   world")
        assert tokens == ["hello.", "\n", "\n", "\n", "world"]

    def test_trailing_spaces_contribute_to_next_line(self):
        """Trailing spaces on a line add to the skip count for the next phrase."""
        tokens = tokenize_lyrics("hello.  \nworld")
        assert tokens == ["hello.", "\n", "\n", "world"]

    def test_trailing_plus_leading_spaces_combine(self):
        """Trailing + leading spaces combine for total skip count."""
        tokens = tokenize_lyrics("end.  \n   start")
        # 2 trailing + 3 leading = 5 sentinels
        assert tokens == ["end.", "\n", "\n", "\n", "\n", "\n", "start"]

    def test_no_sentinels_without_extra_spaces(self):
        """Lines without leading/trailing spaces produce no sentinels."""
        tokens = tokenize_lyrics("line one.\nline two.")
        assert tokens == ["line", "one.", "line", "two."]

    def test_internal_double_space_produces_sentinel(self):
        """Double spaces within a line produce a skip sentinel between words."""
        tokens = tokenize_lyrics("lear  jet.")
        assert tokens == ["lear", "\n", "jet."]

    def test_internal_triple_space_produces_two_sentinels(self):
        """Triple spaces within a line produce two skip sentinels."""
        tokens = tokenize_lyrics("a   b")
        assert tokens == ["a", "\n", "\n", "b"]

    def test_no_sentinels_at_start_of_first_line(self):
        """Leading spaces on the very first line don't produce sentinels."""
        tokens = tokenize_lyrics("   hello")
        assert tokens == ["hello"]

    def test_empty_lines_skipped(self):
        """Empty lines between phrases don't produce spurious sentinels."""
        tokens = tokenize_lyrics("hello.\n\n\nworld")
        assert tokens == ["hello.", "world"]

    def test_hyphens_preserved_with_sentinels(self):
        """Hyphenated syllables work correctly alongside sentinels."""
        tokens = tokenize_lyrics("Mo-ney.\n   Mo-ney")
        assert tokens == ["Mo-", "ney.", "\n", "\n", "\n", "Mo-", "ney"]

    def _make_vocal_track(self, measures_spec, lyrics_text, lyrics_offset=0):
        """Build a minimal vocal track from a compact measure spec.

        measures_spec: list of lists, each inner list describes beats in a measure.
            'n' = note beat, 'r' = rest beat
        """
        measures = []
        for beats_spec in measures_spec:
            beats = []
            for b in beats_spec:
                if b == 'r':
                    beats.append({"type": 4, "rest": True})
                else:
                    beats.append({"type": 4, "notes": [{"fret": 0, "string": 0}]})
            measures.append({"voices": [{"beats": beats}]})
        return {
            "name": "Vocals", "instrument": "Lead 6 (voice)",
            "strings": 6, "tuning": [64, 59, 55, 50, 45, 40],
            "measures": measures,
            "newLyrics": [{"text": lyrics_text, "offset": lyrics_offset}],
        }

    @staticmethod
    def _get_beat_lyrics(builder):
        """Extract ordered list of lyric texts from built XML."""
        gpif_xml = builder.build()
        root = ET.fromstring(gpif_xml)

        voice_beats = {}
        for voice in root.find('Voices'):
            vid = voice.get('id')
            be = voice.find('Beats')
            if be is not None and be.text:
                voice_beats[vid] = be.text.strip().split()

        bar_voice0 = {}
        for bar in root.find('Bars'):
            bid = bar.get('id')
            ve = bar.find('Voices')
            if ve is not None and ve.text:
                vs = ve.text.strip().split()
                if vs and vs[0] != '-1':
                    bar_voice0[bid] = vs[0]

        beat_lyrics = {}
        for beat in root.find('Beats'):
            bid = beat.get('id')
            lyrics_el = beat.find('Lyrics')
            if lyrics_el is not None:
                line = lyrics_el.find('Line')
                if line is not None and line.text:
                    beat_lyrics[bid] = line.text

        result = []
        for mb in root.find('MasterBars'):
            bars_el = mb.find('Bars')
            if bars_el is None:
                continue
            bar0_id = bars_el.text.strip().split()[0]
            v0_id = bar_voice0.get(bar0_id)
            if not v0_id:
                continue
            for bid in voice_beats.get(v0_id, []):
                if bid in beat_lyrics:
                    result.append(beat_lyrics[bid])
        return result

    def test_skip_sentinels_skip_note_beats(self):
        """Skip sentinels cause note-beats to be skipped during assignment."""
        # 2 measures, 3 note-beats each. Lyrics: "end.\n\n\nstart" = 2 sentinels
        track = self._make_vocal_track(
            [['n', 'n', 'n'], ['n', 'n', 'n']],
            "end.\n  start",  # 2 leading = 2 sentinels
        )
        builder = GPIFBuilder([track], {"artist": "T", "title": "T"})
        lyrics = self._get_beat_lyrics(builder)
        # 'end.' on beat 0, then 2 skipped, then 'start' on beat 3
        assert lyrics == ["end.", "start"]

    def test_skip_sentinels_with_rests(self):
        """Skipping counts only note-beats; rests are already non-eligible."""
        # m0: [n, n], m1: [r, r], m2: [n, n, n]
        # 2 sentinels should skip 2 note-beats in m2
        track = self._make_vocal_track(
            [['n', 'n'], ['r', 'r'], ['n', 'n', 'n']],
            "end.\n  start",
        )
        builder = GPIFBuilder([track], {"artist": "T", "title": "T"})
        lyrics = self._get_beat_lyrics(builder)
        # 'end.' on m0 beat 0, skip 2 note-beats (m2 b0, m2 b1), 'start' on m2 b2
        assert lyrics == ["end.", "start"]

    def test_internal_skip_between_words(self):
        """Internal double-space skip should skip a note-beat mid-phrase."""
        # 4 note-beats, lyrics "a  b" = skip 1 between a and b
        track = self._make_vocal_track(
            [['n', 'n', 'n', 'n']],
            "a  b",
        )
        builder = GPIFBuilder([track], {"artist": "T", "title": "T"})
        lyrics = self._get_beat_lyrics(builder)
        # 'a' on beat 0, skip beat 1, 'b' on beat 2
        assert lyrics == ["a", "b"]

    def test_no_skip_single_space(self):
        """Normal single-space word separation should not skip any beats."""
        track = self._make_vocal_track(
            [['n', 'n', 'n']],
            "a b c",
        )
        builder = GPIFBuilder([track], {"artist": "T", "title": "T"})
        lyrics = self._get_beat_lyrics(builder)
        assert lyrics == ["a", "b", "c"]

    def test_excess_tokens_ignored(self):
        """More lyric tokens than note-beats: extras are silently dropped."""
        track = self._make_vocal_track(
            [['n', 'n']],
            "a b c d e",
        )
        builder = GPIFBuilder([track], {"artist": "T", "title": "T"})
        lyrics = self._get_beat_lyrics(builder)
        assert lyrics == ["a", "b"]

    def test_excess_beats_no_lyrics(self):
        """More note-beats than tokens: trailing beats get no lyrics."""
        track = self._make_vocal_track(
            [['n', 'n', 'n', 'n', 'n']],
            "a b",
        )
        builder = GPIFBuilder([track], {"artist": "T", "title": "T"})
        lyrics = self._get_beat_lyrics(builder)
        assert lyrics == ["a", "b"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
