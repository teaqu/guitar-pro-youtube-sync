#!/usr/bin/env python3
"""
Generate a Guitar Pro 7/8 (.gp) file from Songsterr tab data.

Uses blank.gp as a template (for binary files, stylesheets, etc.)
and generates a new score.gpif with the tab data.

Usage:
    python gen_gp.py --song 61178 [-o output.gp]
    python gen_gp.py --song https://www.songsterr.com/a/wsa/ozzy-osbourne-crazy-train-tab-s61178
    python gen_gp.py input.json [-o output.gp]
"""

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

import requests

from utils import resource_path

DURATION_MAP = {
    1: "Whole", 2: "Half", 4: "Quarter", 8: "Eighth",
    16: "16th", 32: "32nd", 64: "64th",
}

VELOCITY_MAP = {
    "ppp": "PPP", "pp": "PP", "p": "P", "mp": "MP",
    "mf": "MF", "f": "F", "ff": "FF", "fff": "FFF",
}

# Songsterr and GP use the same bend/whammy value scale (50 = half tone, 100 = full tone)
# Offsets differ: Songsterr uses 0-60, GP uses 0-100
BEND_OFFSET_SCALE = 100.0 / 60.0

NOTE_NAMES = [
    ("C", ""), ("C", "#"), ("D", ""), ("D", "#"), ("E", ""), ("F", ""),
    ("F", "#"), ("G", ""), ("G", "#"), ("A", ""), ("A", "#"), ("B", ""),
]

SLIDE_MAP = {"below": 16, "above": 8, "toNext": 1, "legato": 1}

# Songsterr tripletFeel -> GP TripletFeel mapping
TRIPLET_FEEL_MAP = {
    "8th": "Triplet8th",
    "16th": "Triplet16th",
}

# Standard drum notation patch for drum tracks
DRUM_NOTATION_PATCH = '''<NotationPatch>
<Name>Drumkit-Standard</Name>
<LineCount>5</LineCount>
<Elements>
<Element><Name>Snare</Name><Articulations>
<Articulation><Name>Snare (hit)</Name><StaffLine>3</StaffLine></Articulation>
<Articulation><Name>Snare (side stick)</Name><StaffLine>3</StaffLine></Articulation>
<Articulation><Name>Snare (rim shot)</Name><StaffLine>3</StaffLine></Articulation>
</Articulations></Element>
<Element><Name>Charley</Name><Articulations>
<Articulation><Name>Hi-Hat (closed)</Name><StaffLine>-1</StaffLine></Articulation>
<Articulation><Name>Hi-Hat (half)</Name><StaffLine>-1</StaffLine></Articulation>
<Articulation><Name>Hi-Hat (open)</Name><StaffLine>-1</StaffLine></Articulation>
<Articulation><Name>Pedal Hi-Hat (hit)</Name><StaffLine>9</StaffLine></Articulation>
</Articulations></Element>
<Element><Name>Acoustic Kick Drum</Name><Articulations>
<Articulation><Name>Kick (hit)</Name><StaffLine>8</StaffLine></Articulation>
</Articulations></Element>
<Element><Name>Kick Drum</Name><Articulations>
<Articulation><Name>Kick (hit)</Name><StaffLine>7</StaffLine></Articulation>
</Articulations></Element>
<Element><Name>Tom Very High</Name><Articulations>
<Articulation><Name>High Floor Tom (hit)</Name><StaffLine>1</StaffLine></Articulation>
</Articulations></Element>
<Element><Name>Tom High</Name><Articulations>
<Articulation><Name>High Tom (hit)</Name><StaffLine>2</StaffLine></Articulation>
</Articulations></Element>
<Element><Name>Tom Medium</Name><Articulations>
<Articulation><Name>Mid Tom (hit)</Name><StaffLine>4</StaffLine></Articulation>
</Articulations></Element>
<Element><Name>Tom Low</Name><Articulations>
<Articulation><Name>Low Tom (hit)</Name><StaffLine>5</StaffLine></Articulation>
</Articulations></Element>
<Element><Name>Tom Very Low</Name><Articulations>
<Articulation><Name>Very Low Tom (hit)</Name><StaffLine>6</StaffLine></Articulation>
</Articulations></Element>
<Element><Name>Ride</Name><Articulations>
<Articulation><Name>Ride (edge)</Name><StaffLine>0</StaffLine></Articulation>
<Articulation><Name>Ride (middle)</Name><StaffLine>0</StaffLine></Articulation>
<Articulation><Name>Ride (bell)</Name><StaffLine>0</StaffLine></Articulation>
</Articulations></Element>
<Element><Name>Splash</Name><Articulations>
<Articulation><Name>Splash (hit)</Name><StaffLine>-2</StaffLine></Articulation>
</Articulations></Element>
<Element><Name>China</Name><Articulations>
<Articulation><Name>China (hit)</Name><StaffLine>-3</StaffLine></Articulation>
</Articulations></Element>
<Element><Name>Crash High</Name><Articulations>
<Articulation><Name>Crash high (hit)</Name><StaffLine>-2</StaffLine></Articulation>
</Articulations></Element>
<Element><Name>Crash Medium</Name><Articulations>
<Articulation><Name>Crash medium (hit)</Name><StaffLine>-1</StaffLine></Articulation>
</Articulations></Element>
<Element><Name>Cowbell Low</Name><Articulations>
<Articulation><Name>Cowbell low (hit)</Name><StaffLine>1</StaffLine></Articulation>
</Articulations></Element>
<Element><Name>Cowbell Medium</Name><Articulations>
<Articulation><Name>Cowbell medium (hit)</Name><StaffLine>0</StaffLine></Articulation>
</Articulations></Element>
<Element><Name>Cowbell High</Name><Articulations>
<Articulation><Name>Cowbell high (hit)</Name><StaffLine>-1</StaffLine></Articulation>
</Articulations></Element>
</Elements>
</NotationPatch>'''

# Standard GP drum kit: MIDI note -> articulation index
DRUM_MIDI_TO_ART = {
    38: 0, 37: 1, 91: 2, 42: 3, 92: 4, 46: 5, 44: 6, 35: 7, 36: 8,
    50: 9, 48: 10, 47: 11, 45: 12, 43: 13, 93: 14, 51: 15, 53: 16,
    94: 17, 55: 18, 95: 19, 52: 20, 96: 21, 49: 22, 97: 23, 57: 24,
    98: 25, 99: 26, 100: 27, 56: 28, 101: 29, 102: 30, 103: 31,
    77: 32, 76: 33, 60: 34, 104: 35, 105: 36, 61: 37, 106: 38,
    107: 39, 66: 40, 65: 41, 68: 42, 67: 43, 64: 44, 108: 45,
    109: 46, 63: 47, 110: 48, 62: 49, 72: 50, 71: 51, 73: 52,
    74: 53, 86: 54, 87: 55, 54: 56, 111: 57, 112: 58, 113: 59,
    79: 60, 78: 61, 58: 62, 81: 63, 80: 64, 114: 65, 115: 66,
    116: 67, 69: 68, 117: 69, 85: 70, 75: 71, 70: 72, 118: 73,
    119: 74, 120: 75, 82: 76, 122: 77, 84: 78, 123: 79, 83: 80,
    39: 84, 40: 85, 31: 86, 41: 87, 59: 88, 126: 89, 127: 90,
    29: 91, 30: 92, 33: 93, 34: 94,
}

SONGSTERR_CDN = "https://dqsljvtekg760.cloudfront.net"
BLANK_GP = resource_path("assets/blank.gp")
DRUM_KIT_XML = resource_path("assets/drum_kit.xml")


def escape_xml(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def midi_to_pitch_xml(midi_note: int) -> str:
    step, accidental = NOTE_NAMES[midi_note % 12]
    octave = midi_note // 12
    acc_xml = f"<Accidental>{accidental}</Accidental>" if accidental else "<Accidental/>"
    return f"<Pitch><Step>{step}</Step>{acc_xml}<Octave>{octave}</Octave></Pitch>"


def tokenize_lyrics(text: str) -> list[str]:
    """Tokenize lyrics text into syllables for beat-level assignment.

    Words are separated by whitespace, and hyphens within words split syllables.
    The hyphen is kept with the preceding syllable (e.g., "Mo-ney" -> ["Mo-", "ney"]).

    Spaces encode the number of note-beats to skip:

    * **Leading/trailing** spaces on each line contribute to the skip count at
      phrase boundaries.  Between consecutive non-empty lines the skip count is
      ``trailing_spaces(prev_line) + leading_spaces(next_line)``.
    * **Internal multi-spaces** (2+ consecutive spaces within a line) contribute
      ``len(run) - 1`` additional skips between the surrounding tokens.

    Each skip is emitted as a ``'\\n'`` sentinel token consumed by
    ``_assign_lyrics()``.
    """
    tokens: list[str] = []
    lines = text.split('\n')
    prev_trailing = 0

    def _tokenize_word(word: str):
        """Split a word into syllable tokens on hyphens."""
        parts = re.split(r'(-)', word)
        current = ''
        for p in parts:
            if p == '-':
                current += '-'
                tokens.append(current)
                current = ''
            else:
                current += p
        if current:
            tokens.append(current)

    for line in lines:
        leading = len(line) - len(line.lstrip(' '))
        trailing = len(line) - len(line.rstrip(' '))
        inner = line.strip()

        if not inner:
            continue  # skip empty lines

        # Emit inter-line skip sentinels
        skip_count = prev_trailing + leading
        if tokens and skip_count > 0:
            tokens.extend('\n' for _ in range(skip_count))

        # Split inner text on runs of 2+ spaces (kept as separators)
        segments = re.split(r'( {2,})', inner)
        for segment in segments:
            if not segment:
                continue
            if segment[0] == ' ':
                # Multi-space run → (len - 1) skip sentinels
                tokens.extend('\n' for _ in range(len(segment) - 1))
            else:
                for word in segment.split():
                    _tokenize_word(word)

        prev_trailing = trailing

    return tokens


def _icon_from_midi_program(instrument_id: int) -> int:
    """Map MIDI program number to GP icon ID (matches Songsterr's GP export)."""
    if instrument_id >= 1024:
        return 18  # Drums
    if 0 <= instrument_id <= 7:
        return 10  # Piano
    if 8 <= instrument_id <= 15:
        return 10  # Chromatic Percussion (vibraphone, etc.)
    if 16 <= instrument_id <= 23:
        return 10  # Organ
    if 24 <= instrument_id <= 27:
        return 3   # Acoustic/Clean Guitar
    if 28 <= instrument_id <= 31:
        return 4   # Overdriven/Distortion Guitar
    if 32 <= instrument_id <= 39:
        return 5   # Bass
    if 40 <= instrument_id <= 55:
        return 14  # Strings/Ensemble
    if 56 <= instrument_id <= 63:
        return 14  # Brass
    if 64 <= instrument_id <= 79:
        return 14  # Reed/Pipe (sax, oboe, flute, etc.)
    if 80 <= instrument_id <= 95:
        return 12  # Synth Lead/Pad
    return 4  # Default: electric guitar icon


    # RSE effect chain presets (effect_id, parameters)
_FX_OVERDRIVE_SCREAMER = ("E03_OverdriveScreamer", "0.85 0 0.67")
_FX_STACK_BRITISH = ("A06_StackBritishStack", "1 0.91 0.67 0.32 0.69 0.51 0.95 0")
_FX_STACK_BRITISH_VINTAGE = ("A05_StackBritishVintage", "0.85 0.67 0.36 0.66 0.52")
_FX_STACK_CLASSIC = ("A10_StackClassic", "0.45 0 0 0.63 0.37 0.39 0.39 0.71")
_FX_COMBO_TOP30 = ("A01_ComboTop30", "0.61 0.59 0.38 0.511667 0.21 0.29 0 0")
_FX_EQ_GUITAR = ("E30_EqGEq", "0.494949 0.494949 0.494949 0.494949 0.494949 0.494949 0.494949 0.494949")
_FX_EQ_BASS = ("E31_EqBEq", "0.657143 0.6 0.6 0.685714 0.342857 0.628571 0.714286 0.5")
_FX_EQ_10BAND = ("M08_GraphicEQ10Band", "0 0 0.5 0.494949 0.494949 0.494949 0.494949 0.494949 0.494949 0.494949 0.494949 0.494949 0.494949")
_FX_REVERB_ROOM = ("M04_StudioReverbRoomAmbience", "1 0.30476 0.4 0.5 0.2")

# Grouped effect chains per instrument category
_CHAIN_DISTORTION = [_FX_OVERDRIVE_SCREAMER, _FX_STACK_BRITISH, _FX_EQ_GUITAR]
_CHAIN_OVERDRIVE = [_FX_OVERDRIVE_SCREAMER, _FX_STACK_BRITISH_VINTAGE, _FX_EQ_GUITAR]
_CHAIN_CLEAN_GUITAR = [_FX_COMBO_TOP30, _FX_EQ_GUITAR]
_CHAIN_BASS = [_FX_STACK_CLASSIC, _FX_EQ_BASS]
_CHAIN_ORCHESTRAL = [_FX_EQ_10BAND, _FX_REVERB_ROOM]

# SoundbankPatch names for solo orchestral instruments
_ORCHESTRAL_PATCHES: dict[str, str] = {
    "violin": "Violin-Solo", "viola": "Viola-Solo", "cello": "Cello-Solo",
    "contrabass": "Contrabass-Solo", "sax": "Sax-Solo",
}


def get_instrument_type(instrument_name: str, instrument_id: int = 25) -> dict:
    """Map Songsterr instrument name to GP InstrumentSet type, Sound path, icon, color, and RSE config."""
    name_lower = instrument_name.lower()

    # Colors: green=winds, red=guitar, yellow=bass, blue=drums, purple=keys
    GREEN = "181 209 130"
    RED = "235 152 125"
    YELLOW = "234 212 125"
    BLUE = "117 201 227"
    PURPLE = "183 147 210"

    icon = _icon_from_midi_program(instrument_id)

    # Drums (RSE handled separately in _build_track_xml)
    if "drum" in name_lower or "percussion" in name_lower:
        return {"set_type": "drumKit", "sound_path": "Drums/Drums/Drumkit",
                "icon": 18, "color": BLUE,
                "soundbank_patch": None, "effect_chain": []}
    # Bass
    if "bass" in name_lower:
        return {"set_type": "electricBass", "sound_path": "Stringed/Basses/Clean Bass",
                "icon": icon, "color": YELLOW,
                "soundbank_patch": "Pre-Bass", "effect_chain": _CHAIN_BASS}
    # Synthesizer / voice leads
    if "synth" in name_lower or "voice" in name_lower:
        return {"set_type": "leadSynthesizer", "sound_path": "Orchestra/Synth/Lead",
                "icon": icon, "color": PURPLE,
                "soundbank_patch": None, "effect_chain": _CHAIN_ORCHESTRAL}
    # Guitar variants
    if "distortion" in name_lower:
        return {"set_type": "electricGuitar", "sound_path": "Stringed/Electric Guitars/Distortion Guitar",
                "icon": icon, "color": RED,
                "soundbank_patch": "Classic-Guitar", "effect_chain": _CHAIN_DISTORTION}
    if "overdrive" in name_lower or "overdriven" in name_lower:
        return {"set_type": "electricGuitar", "sound_path": "Stringed/Electric Guitars/Overdrive Guitar",
                "icon": icon, "color": RED,
                "soundbank_patch": "Strat-Guitar", "effect_chain": _CHAIN_OVERDRIVE}
    if "clean" in name_lower and "guitar" in name_lower:
        return {"set_type": "electricGuitar", "sound_path": "Stringed/Electric Guitars/Clean Guitar",
                "icon": icon, "color": RED,
                "soundbank_patch": "Strat-Guitar", "effect_chain": _CHAIN_CLEAN_GUITAR}
    if "acoustic" in name_lower and "guitar" in name_lower:
        return {"set_type": "steelGuitar", "sound_path": "Stringed/Acoustic Guitars/Steel Guitar",
                "icon": icon, "color": RED,
                "soundbank_patch": "SteelString-Guitar", "effect_chain": _CHAIN_CLEAN_GUITAR}
    if "guitar" in name_lower:
        return {"set_type": "electricGuitar", "sound_path": "Stringed/Electric Guitars/Overdrive Guitar",
                "icon": icon, "color": RED,
                "soundbank_patch": "Strat-Guitar", "effect_chain": _CHAIN_OVERDRIVE}
    # Piano/keys (electric piano before generic piano)
    if "electric piano" in name_lower:
        return {"set_type": "electricPiano", "sound_path": "Orchestra/Keyboard/Electric Piano",
                "icon": icon, "color": PURPLE,
                "soundbank_patch": None, "effect_chain": _CHAIN_ORCHESTRAL}
    if "piano" in name_lower or "keyboard" in name_lower or "organ" in name_lower:
        return {"set_type": "piano", "sound_path": "Keys/Pianos/Grand Piano",
                "icon": icon, "color": PURPLE,
                "soundbank_patch": None, "effect_chain": _CHAIN_ORCHESTRAL}
    # Strings
    strings = {"violin": ("violin", "Violin"), "viola": ("viola", "Viola"),
               "cello": ("cello", "Cello"), "contrabass": ("contrabass", "Contrabass")}
    for key, (stype, gp_name) in strings.items():
        if key in name_lower:
            return {"set_type": stype, "sound_path": f"Orchestra/Strings/{gp_name}",
                    "icon": icon, "color": GREEN,
                    "soundbank_patch": _ORCHESTRAL_PATCHES.get(key),
                    "effect_chain": _CHAIN_ORCHESTRAL}
    # Brass
    brass = {"trumpet": ("trumpet", "Trumpet"), "trombone": ("trombone", "Trombone"),
             "tuba": ("tuba", "Tuba"), "french horn": ("frenchHorn", "French Horn")}
    for key, (stype, gp_name) in brass.items():
        if key in name_lower:
            return {"set_type": stype, "sound_path": f"Orchestra/Winds/{gp_name}",
                    "icon": icon, "color": GREEN,
                    "soundbank_patch": None, "effect_chain": _CHAIN_ORCHESTRAL}
    # Woodwinds (match "sax" in addition to "saxophone")
    woodwinds = {"flute": ("flute", "Flute"), "oboe": ("oboe", "Oboe"),
                 "clarinet": ("clarinet", "Clarinet"), "bassoon": ("bassoon", "Bassoon"),
                 "sax": ("saxophone", "Saxophone")}
    for key, (stype, gp_name) in woodwinds.items():
        if key in name_lower:
            return {"set_type": stype, "sound_path": f"Orchestra/Winds/{gp_name}",
                    "icon": icon, "color": GREEN,
                    "soundbank_patch": _ORCHESTRAL_PATCHES.get(key),
                    "effect_chain": _CHAIN_ORCHESTRAL}
    # Default to electric guitar
    return {"set_type": "electricGuitar",
            "sound_path": "Stringed/Electric Guitars/Overdrive Guitar",
            "icon": icon, "color": RED,
            "soundbank_patch": "Strat-Guitar", "effect_chain": _CHAIN_OVERDRIVE}


# ---------------------------------------------------------------------------
# Songsterr API
# ---------------------------------------------------------------------------

def fetch_song_meta(song_id: int) -> dict:
    url = f"https://www.songsterr.com/api/meta/{song_id}"
    print(f"Fetching song metadata: {url}")
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_track_json(song_id: int, revision_id: int, image_hash: str, part_index: int) -> dict:
    url = f"{SONGSTERR_CDN}/{song_id}/{revision_id}/{image_hash}/{part_index}.json"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_all_tracks(song_id: int) -> tuple[dict, list[dict]]:
    """Fetch song meta and all track JSONs. Returns (meta, [track_data, ...])."""
    meta = fetch_song_meta(song_id)
    revision_id = meta["revisionId"]
    image_hash = meta["image"]
    tracks_meta = meta.get("tracks", [])

    print(f"  Song: {meta['artist']} - {meta['title']}")
    print(f"  Revision: {revision_id}")
    print(f"  Tracks: {len(tracks_meta)}")

    tracks = []
    for i, tm in enumerate(tracks_meta):
        print(f"  Fetching track {i}: {tm['name']} ({tm['instrument']})...")
        data = fetch_track_json(song_id, revision_id, image_hash, i)
        tracks.append(data)

    return meta, tracks


# ---------------------------------------------------------------------------
# GPIF Builder (multi-track)
# ---------------------------------------------------------------------------

class GPIFBuilder:
    """Builds a multi-track GPIF XML from a list of Songsterr track JSONs."""

    def __init__(self, tracks: list[dict], meta: dict | None = None):
        self.tracks = tracks
        self.meta = meta or {}
        self._counters = {"note": 0, "beat": 0, "voice": 0, "bar": 0, "rhythm": 0}
        self._rhythm_cache: dict[tuple, int] = {}

        self._note_objs: list[dict] = []
        self._beat_objs: list[dict] = []  # Store beats as dicts for dedup
        self._voice_xmls: list[str] = []
        self._bar_xmls: list[str] = []
        self._rhythm_xmls: list[str] = []

        # Dedup mappings (filled in build())
        self._note_id_map: dict[int, int] = {}  # original → canonical
        self._beat_id_map: dict[int, int] = {}  # original → canonical

        # Per-track state
        self._current_tuning: list[int] = []
        self._current_num_strings: int = 6
        self._current_is_drums: bool = False
        self._last_note_on_string: dict[int, dict] = {}

        # Per-track beat tracking for lyrics assignment (voice 0 only)
        # _track_beat_info[track_idx] = [(beat_id, has_notes), ...] in order
        self._track_beat_info: list[list[tuple[int, bool]]] = []
        self._current_track_beats: list[tuple[int, bool]] = []
        self._tracking_lyrics_voice: bool = False

    def _alloc(self, kind: str) -> int:
        val = self._counters[kind]
        self._counters[kind] += 1
        return val

    def _get_rhythm_id(self, note_type: int, dots: int = 0, tuplet: int | None = None) -> int:
        key = (note_type, dots, tuplet)
        if key in self._rhythm_cache:
            return self._rhythm_cache[key]
        rid = self._alloc("rhythm")
        self._rhythm_cache[key] = rid
        note_value = DURATION_MAP.get(note_type, "Quarter")
        parts = [f'<Rhythm id="{rid}">', f'  <NoteValue>{note_value}</NoteValue>']
        if dots:
            parts.append(f'  <AugmentationDot count="{dots}"/>')
        if tuplet:
            tuplet_map = {3: (3, 2), 5: (5, 4), 6: (6, 4), 7: (7, 4), 9: (9, 8)}
            num, den = tuplet_map.get(tuplet, (tuplet, tuplet - 1))
            parts.append(f'  <PrimaryTuplet num="{num}" den="{den}"/>')
        parts.append('</Rhythm>')
        self._rhythm_xmls.append('\n'.join(parts))
        return rid

    # --- Note ---

    def _process_note(self, note_data: dict) -> int | None:
        if note_data.get("rest"):
            return None
        nid = self._alloc("note")
        fret = note_data.get("fret", 0)

        if self._current_is_drums:
            # Drums: fret IS the MIDI note, string is a float staff position
            # Reverse like regular instruments: drum staff has LineCount=5
            gp_string = 5 - note_data.get("string", 0)
            midi_note = fret  # Used for articulation lookup only
            articulation = DRUM_MIDI_TO_ART.get(fret, 0)
        else:
            songsterr_string = note_data.get("string", 0)
            gp_string = (self._current_num_strings - 1) - int(songsterr_string)
            midi_note = self._current_tuning[gp_string] + fret
            articulation = 0

        obj = {
            "id": nid, "fret": fret, "gp_string": gp_string, "midi_note": midi_note,
            "articulation": articulation, "is_drums": self._current_is_drums,
            "tie_origin": False, "tie_destination": note_data.get("tie", False),
            "hopo_origin": False, "hopo_destination": note_data.get("hp", False),
            "bend": note_data.get("bend"), "slide": note_data.get("slide"),
            "ghost": note_data.get("ghost", False), "staccato": note_data.get("staccato", False),
            "accentuated": note_data.get("accentuated"),
        }

        if obj["tie_destination"] and gp_string in self._last_note_on_string:
            self._last_note_on_string[gp_string]["tie_origin"] = True
        if obj["hopo_destination"] and gp_string in self._last_note_on_string:
            self._last_note_on_string[gp_string]["hopo_origin"] = True

        self._last_note_on_string[gp_string] = obj
        self._note_objs.append(obj)
        return nid

    def _note_to_xml(self, obj: dict) -> str:
        lines = [f'<Note id="{obj["id"]}">']
        lines.append(f'  <InstrumentArticulation>{obj.get("articulation", 0)}</InstrumentArticulation>')
        props = []

        is_drums = obj.get("is_drums", False)
        if is_drums:
            # Drum notes: fixed pitch C/-1, float string, no MIDI property
            pitch_xml = '<Pitch><Step>C</Step><Accidental/><Octave>-1</Octave></Pitch>'
            string_val = obj["gp_string"]  # Float for drums
        else:
            pitch_xml = midi_to_pitch_xml(obj["midi_note"])
            string_val = obj["gp_string"]  # Int for regular instruments
        props.append(f'  <Property name="ConcertPitch">{pitch_xml}</Property>')
        props.append(f'  <Property name="Fret"><Fret>{obj["fret"]}</Fret></Property>')
        props.append(f'  <Property name="String"><String>{string_val}</String></Property>')
        props.append(f'  <Property name="TransposedPitch">{pitch_xml}</Property>')

        if obj.get("bend"):
            bend = obj["bend"]
            points = bend.get("points", [])
            if len(points) >= 2:
                props.append('  <Property name="Bended"><Enable/></Property>')
                origin, dest = points[0], points[-1]
                origin_val, dest_val = origin.get("tone", 0), dest.get("tone", 0)
                origin_off = origin.get("position", 0) * BEND_OFFSET_SCALE
                dest_off = dest.get("position", 60) * BEND_OFFSET_SCALE
                props.append(f'  <Property name="BendDestinationOffset"><Float>{dest_off:.6f}</Float></Property>')
                props.append(f'  <Property name="BendDestinationValue"><Float>{dest_val:.6f}</Float></Property>')
                props.append(f'  <Property name="BendOriginOffset"><Float>{origin_off:.6f}</Float></Property>')
                props.append(f'  <Property name="BendOriginValue"><Float>{origin_val:.6f}</Float></Property>')
                if len(points) >= 3:
                    mid = points[1]
                    mid_val = mid.get("tone", 0)
                    mid_off = mid.get("position", 30) * BEND_OFFSET_SCALE
                    props.append(f'  <Property name="BendMiddleValue"><Float>{mid_val:.6f}</Float></Property>')
                    props.append(f'  <Property name="BendMiddleOffset1"><Float>{mid_off:.6f}</Float></Property>')
                    if len(points) >= 4:
                        mid2_off = points[2].get("position", 60) * BEND_OFFSET_SCALE
                        props.append(f'  <Property name="BendMiddleOffset2"><Float>{mid2_off:.6f}</Float></Property>')

        if not is_drums:
            props.append(f'  <Property name="Midi"><Number>{obj["midi_note"]}</Number></Property>')

        if obj.get("hopo_origin"):
            props.append('  <Property name="HopoOrigin"><Enable/></Property>')
        if obj.get("hopo_destination"):
            props.append('  <Property name="HopoDestination"><Enable/></Property>')
        if obj.get("slide"):
            flags = SLIDE_MAP.get(obj["slide"], 0)
            if flags:
                props.append(f'  <Property name="Slide"><Flags>{flags}</Flags></Property>')

        lines.append('  <Properties>')
        lines.extend(props)
        lines.append('  </Properties>')

        if obj.get("tie_origin") and obj.get("tie_destination"):
            lines.append('  <Tie origin="true" destination="true"/>')
        elif obj.get("tie_origin"):
            lines.append('  <Tie origin="true" destination="false"/>')
        elif obj.get("tie_destination"):
            lines.append('  <Tie origin="false" destination="true"/>')

        if obj.get("staccato"):
            lines.append('  <Accent>1</Accent>')
        elif obj.get("accentuated") is not None:
            gp_accent = {1: 1, 2: 4}.get(obj["accentuated"], obj["accentuated"])
            lines.append(f'  <Accent>{gp_accent}</Accent>')

        if obj.get("ghost"):
            lines.append('  <AntiAccent>Normal</AntiAccent>')

        lines.append('</Note>')
        return '\n'.join(lines)

    # --- Beat ---

    def _process_beat(self, beat_data: dict) -> int:
        bid = self._alloc("beat")
        rhythm_id = self._get_rhythm_id(
            beat_data.get("type", 4), beat_data.get("dots", 0), beat_data.get("tuplet"))

        note_ids = []
        is_rest = beat_data.get("rest", False)
        if not is_rest:
            for note in beat_data.get("notes", []):
                nid = self._process_note(note)
                if nid is not None:
                    note_ids.append(nid)
        if not note_ids:
            is_rest = True

        velocity = beat_data.get("velocity")
        dynamic = VELOCITY_MAP.get(velocity, "F") if velocity else "F"

        beat_obj = {
            "id": bid, "rhythm_id": rhythm_id, "note_ids": note_ids,
            "dynamic": dynamic,
        }

        if "gradualVelocity" in beat_data:
            gv = beat_data["gradualVelocity"]
            if gv == "crescendo":
                beat_obj["hairpin"] = "Crescendo"
            elif gv == "decrescendo":
                beat_obj["hairpin"] = "Decrescendo"

        if "text" in beat_data:
            text = beat_data["text"].get("text", "")
            if text:
                beat_obj["free_text"] = text

        if "tremoloBar" in beat_data:
            tb = beat_data["tremoloBar"]
            points = tb.get("points", [])
            if len(points) >= 2:
                origin, dest = points[0], points[-1]
                o_val = origin.get("tone", 0)
                o_off = origin.get("position", 0) * BEND_OFFSET_SCALE
                d_val = dest.get("tone", 0)
                d_off = dest.get("position", 60) * BEND_OFFSET_SCALE

                if len(points) >= 3:
                    mid = points[1]
                    if mid.get("position", 0) == origin.get("position", 0) and mid.get("tone", 0) == origin.get("tone", 0):
                        m_val = round((o_val + d_val) / 2)
                        m_off = round(d_off * 5 / 6)
                    else:
                        m_val = mid.get("tone", 0)
                        m_off = round(mid.get("position", 0) * BEND_OFFSET_SCALE)
                else:
                    m_val = round((o_val + d_val) / 2)
                    m_off = round(d_off * 5 / 6)

                beat_obj["whammy"] = (o_val, m_val, d_val, o_off, m_off, d_off)

        self._beat_objs.append(beat_obj)
        if self._tracking_lyrics_voice:
            self._current_track_beats.append((bid, not is_rest))
        return bid

    # --- Voice / Bar ---

    def _make_empty_beat(self) -> int:
        bid = self._alloc("beat")
        rhythm_id = self._get_rhythm_id(1)
        self._beat_objs.append({
            "id": bid, "rhythm_id": rhythm_id, "note_ids": [],
            "dynamic": "F",
        })
        return bid

    def _process_voice(self, voice_data: dict) -> int:
        vid = self._alloc("voice")
        beat_ids = [self._process_beat(b) for b in voice_data.get("beats", [])]
        if not beat_ids:
            beat_ids.append(self._make_empty_beat())
        self._voice_xmls.append(
            f'<Voice id="{vid}">\n  <Beats>{" ".join(str(b) for b in beat_ids)}</Beats>\n</Voice>')
        return vid

    def _process_bar(self, measure_data: dict) -> int:
        bid = self._alloc("bar")
        voice_ids = []
        for vi, v in enumerate(measure_data.get("voices", [])):
            self._tracking_lyrics_voice = (vi == 0)
            voice_ids.append(self._process_voice(v))
        self._tracking_lyrics_voice = False
        while len(voice_ids) < 4:
            voice_ids.append(-1)
        clef = "Neutral" if self._current_is_drums else "G2"
        self._bar_xmls.append(
            f'<Bar id="{bid}">\n  <Clef>{clef}</Clef>\n'
            f'  <Voices>{" ".join(str(v) for v in voice_ids[:4])}</Voices>\n</Bar>')
        return bid

    def _process_track_measures(self, track_data: dict) -> list[int]:
        """Process all measures for a single track, returning bar IDs."""
        self._current_num_strings = track_data.get("strings", 6)
        tuning = track_data.get("tuning")
        self._current_is_drums = tuning is None or "drum" in track_data.get("instrument", "").lower()
        self._current_tuning = list(reversed(tuning)) if tuning else [0] * self._current_num_strings
        self._last_note_on_string = {}
        self._current_track_beats = []
        bar_ids = [self._process_bar(m) for m in track_data.get("measures", [])]
        self._track_beat_info.append(self._current_track_beats)
        return bar_ids

    # --- Deduplication ---

    def _note_signature(self, obj: dict) -> tuple:
        """Compute a hashable signature for a note object."""
        bend_sig = None
        if obj.get("bend"):
            points = obj["bend"].get("points", [])
            bend_sig = tuple((p.get("tone", 0), p.get("position", 0)) for p in points)
        return (
            obj["fret"], obj["gp_string"], obj["midi_note"], obj.get("articulation", 0),
            obj.get("tie_origin", False), obj.get("tie_destination", False),
            obj.get("hopo_origin", False), obj.get("hopo_destination", False),
            bend_sig, obj.get("slide"), obj.get("ghost", False),
            obj.get("staccato", False), obj.get("accentuated"),
        )

    def _dedup_notes(self):
        """Deduplicate notes by signature, building _note_id_map."""
        sig_to_canonical: dict[tuple, int] = {}
        for obj in self._note_objs:
            sig = self._note_signature(obj)
            if sig in sig_to_canonical:
                self._note_id_map[obj["id"]] = sig_to_canonical[sig]
            else:
                sig_to_canonical[sig] = obj["id"]
                self._note_id_map[obj["id"]] = obj["id"]

    def _beat_signature(self, obj: dict) -> tuple:
        """Compute a hashable signature for a beat object."""
        canonical_notes = tuple(self._note_id_map.get(n, n) for n in obj["note_ids"])
        lyrics_sig = tuple(obj["lyrics"]) if "lyrics" in obj else None
        return (
            obj["rhythm_id"], obj["dynamic"], canonical_notes,
            obj.get("hairpin"), obj.get("free_text"),
            obj.get("whammy"), lyrics_sig,
        )

    def _dedup_beats(self):
        """Deduplicate beats by signature, building _beat_id_map."""
        sig_to_canonical: dict[tuple, int] = {}
        for obj in self._beat_objs:
            sig = self._beat_signature(obj)
            if sig in sig_to_canonical:
                self._beat_id_map[obj["id"]] = sig_to_canonical[sig]
            else:
                sig_to_canonical[sig] = obj["id"]
                self._beat_id_map[obj["id"]] = obj["id"]

    def _beat_to_xml(self, obj: dict) -> str:
        """Convert a beat dict to XML string."""
        canonical_notes = [self._note_id_map.get(n, n) for n in obj["note_ids"]]
        lines = [f'<Beat id="{obj["id"]}">']
        lines.append(f'  <Rhythm ref="{obj["rhythm_id"]}"/>')
        lines.append('  <Properties>')
        lines.append('    <Property name="PrimaryPickupVolume"><Float>0.500000</Float></Property>')
        lines.append('    <Property name="PrimaryPickupTone"><Float>0.500000</Float></Property>')
        lines.append('  </Properties>')
        lines.append(f'  <Dynamic>{obj["dynamic"]}</Dynamic>')

        if "hairpin" in obj:
            lines.append(f'  <Hairpin>{obj["hairpin"]}</Hairpin>')

        if "lyrics" in obj:
            ll = '\n'.join(f'    <Line><![CDATA[{lt}]]></Line>'
                          for lt in obj["lyrics"])
            lines.append(f'  <Lyrics>\n{ll}\n  </Lyrics>')

        if canonical_notes:
            lines.append(f'  <Notes>{" ".join(str(n) for n in canonical_notes)}</Notes>')

        if "free_text" in obj:
            lines.append(f'  <FreeText><![CDATA[{obj["free_text"]}]]></FreeText>')

        if "whammy" in obj:
            o_val, m_val, d_val, o_off, m_off, d_off = obj["whammy"]
            lines.append(
                f'  <Whammy originValue="{o_val:.6f}" middleValue="{m_val:.6f}" '
                f'destinationValue="{d_val:.6f}" originOffset="{o_off:.6f}" '
                f'middleOffset1="{m_off:.6f}" middleOffset2="{m_off:.6f}" '
                f'destinationOffset="{d_off:.6f}"/>')

        lines.append('</Beat>')
        return '\n'.join(lines)

    # --- Track XML ---

    def _build_track_xml(self, track_idx: int, track_data: dict) -> str:
        name = track_data.get("name", "Track")
        frets = track_data.get("frets", 24)
        instrument_name = track_data.get("instrument", "Steel Guitar")
        instrument_id = track_data.get("instrumentId", 25)
        num_strings = track_data.get("strings", 6)
        tuning_raw = track_data.get("tuning")
        is_drums = tuning_raw is None or "drum" in instrument_name.lower()
        tuning = list(reversed(tuning_raw)) if tuning_raw else [0] * num_strings
        tuning_str = " ".join(str(t) for t in tuning)
        inst_type = get_instrument_type(instrument_name, instrument_id)

        # Lyrics
        lyrics_lines = []
        for lyric in track_data.get("newLyrics", []):
            text = lyric.get("text", "")
            offset = lyric.get("offset", 0)
            lyrics_lines.append(f'<Line><Text><![CDATA[{text}]]></Text><Offset>{offset}</Offset></Line>')
        while len(lyrics_lines) < 5:
            lyrics_lines.append('<Line><Text><![CDATA[]]></Text><Offset>0</Offset></Line>')

        # Drum tracks use a full drumKit InstrumentSet from drum_kit.xml
        if is_drums and DRUM_KIT_XML.exists():
            instrument_set_xml = DRUM_KIT_XML.read_text()
        else:
            instrument_set_xml = f'''<InstrumentSet>
<Name>{escape_xml(instrument_name)}</Name>
<Type>{inst_type["set_type"]}</Type>
<LineCount>5</LineCount>
<Elements>
<Element>
<Name>Pitched</Name>
<Type>pitched</Type>
<SoundbankName/>
<Articulations>
<Articulation>
<Name/>
<StaffLine>0</StaffLine>
<Noteheads>noteheadBlack noteheadHalf noteheadWhole</Noteheads>
<TechniquePlacement>outside</TechniquePlacement>
<TechniqueSymbol/>
<InputMidiNumbers/>
<OutputRSESound/>
<OutputMidiNumber>0</OutputMidiNumber>
</Articulation>
</Articulations>
</Element>
</Elements>
</InstrumentSet>'''

        # MIDI connection: drums must be on channel 9
        if is_drums:
            midi_conn = '<MidiConnection>\n<Port>0</Port>\n<PrimaryChannel>9</PrimaryChannel>\n<SecondaryChannel>9</SecondaryChannel>\n<ForeOneChannelPerString>false</ForeOneChannelPerString>\n</MidiConnection>'
        else:
            midi_conn = '<MidiConnection>\n<Port>0</Port>\n<PrimaryChannel/>\n<SecondaryChannel/>\n<ForeOneChannelPerString>false</ForeOneChannelPerString>\n</MidiConnection>'

        # Build Sounds and Automations
        sounds_list = track_data.get("sounds", [])
        track_autos = track_data.get("trackAutomations", {}).get("trackSoundAutomations", [])

        parts = [f'<Track id="{track_idx}">']
        parts.append(f'<Name><![CDATA[{name}]]></Name>')
        parts.append(f'<ShortName><![CDATA[{"drm." if is_drums else "s.guit."}]]></ShortName>')
        parts.append(f'<Color>{inst_type["color"]}</Color>')
        parts.append('<SystemsDefautLayout>3</SystemsDefautLayout>')
        parts.append('<SystemsLayout>2</SystemsLayout>')
        parts.append('<PalmMute>0</PalmMute>')
        parts.append('<PlayingStyle>Default</PlayingStyle>')
        if not is_drums:
            parts.append('<UseOneChannelPerString/>')
        parts.append(f'<IconId>{inst_type["icon"]}</IconId>')
        parts.append(instrument_set_xml)
        parts.append('<Transpose>\n<Chromatic>0</Chromatic>\n<Octave>-1</Octave>\n</Transpose>')
        parts.append('<RSE>\n<ChannelStrip version="E56">\n<Parameters>0.6 0.68 1 0.62 0.75 0.5 0.66 0.18 0.6 0 0.5 0.5 0.80 0.5 0.5 0.5</Parameters>\n</ChannelStrip>\n</RSE>')
        parts.append('<ForcedSound>-1</ForcedSound>')

        # Build <Sounds> block
        if is_drums:
            parts.append('<Sounds>\n<Sound>\n<Name><![CDATA[Drumkit]]></Name>\n<Label><![CDATA[Drumkit]]></Label>\n<Path>Drums/Drums/Drumkit</Path>\n<Role>Factory</Role>\n<MIDI>\n<LSB>0</LSB>\n<MSB>0</MSB>\n<Program>0</Program>\n</MIDI>\n<RSE>\n<SoundbankPatch>Drumkit-Master</SoundbankPatch>\n<ElementsSettings>\n</ElementsSettings>\n<Pickups>\n<OverloudPosition>0</OverloudPosition>\n<Volumes>1 1</Volumes>\n<Tones>1 1</Tones>\n</Pickups>\n<EffectChain>\n<Effect id="M06_DynamicAnalogDynamic">\n<Parameters>0.42 0.14 0.39 0.38 0.7 0.4 0.72 0.5</Parameters>\n</Effect>\n<Effect id="M08_GraphicEQ10Band">\n<Parameters>0 0 0.708333 0.591837 0.591837 0.55102 0.510204 0.408163 0.367347 0.387755 0.530612 0.612245 0.693878</Parameters>\n</Effect>\n<Effect id="M05_StudioReverbPlatePercussive">\n<Parameters>1 0.38 0.3 0.5 0.5</Parameters>\n</Effect>\n</EffectChain>\n</RSE>\n</Sound>\n</Sounds>')
        elif sounds_list and len(sounds_list) > 1:
            # Multi-sound track: build a Sound entry for each alternate instrument
            sound_entries = []
            for snd in sounds_list:
                snd_type = get_instrument_type(snd["label"], snd.get("instrumentId", 25))
                sound_entries.append(self._build_sound_xml(
                    snd["label"], snd.get("instrumentId", instrument_id), snd_type))
            parts.append('<Sounds>\n' + '\n'.join(sound_entries) + '\n</Sounds>')
        else:
            # Single sound
            parts.append('<Sounds>\n' + self._build_sound_xml(
                instrument_name, instrument_id, inst_type) + '\n</Sounds>')

        parts.append(midi_conn)
        parts.append('<PlaybackState>Default</PlaybackState>')
        parts.append('<AudioEngineState>RSE</AudioEngineState>')
        parts.append(f'<Lyrics dispatched="true">\n{chr(10).join(lyrics_lines)}\n</Lyrics>')
        parts.append(self._build_staves_xml(is_drums, frets, num_strings, tuning_str))

        # Build <Automations> block
        if is_drums:
            automations = '<Automations>\n<Automation>\n<Type>Sound</Type>\n<Linear>false</Linear>\n<Bar>0</Bar>\n<Position>0</Position>\n<Visible>true</Visible>\n<Value>Drums/Drums/Drumkit;Drumkit;Factory</Value>\n</Automation>\n</Automations>'
        elif track_autos and sounds_list:
            auto_parts = ['<Automations>']
            for sa in track_autos:
                sid = sa["soundId"]
                snd = sounds_list[sid] if sid < len(sounds_list) else sounds_list[0]
                snd_type = get_instrument_type(snd["label"], snd.get("instrumentId", 25))
                bar = sa["measure"]
                pos = sa.get("position", 0) / 960 if sa.get("position", 0) else 0
                auto_parts.append(
                    f'<Automation>\n<Type>Sound</Type>\n<Linear>false</Linear>\n'
                    f'<Bar>{bar}</Bar>\n<Position>{pos}</Position>\n<Visible>true</Visible>\n'
                    f'<Value>{snd_type["sound_path"]};{escape_xml(snd["label"])};User</Value>\n</Automation>')
            auto_parts.append('</Automations>')
            automations = '\n'.join(auto_parts)
        else:
            # Single-sound: add a default Sound automation at bar 0
            automations = (
                f'<Automations>\n<Automation>\n<Type>Sound</Type>\n<Linear>false</Linear>\n'
                f'<Bar>0</Bar>\n<Position>0</Position>\n<Visible>true</Visible>\n'
                f'<Value>{inst_type["sound_path"]};{escape_xml(instrument_name)};User</Value>\n'
                f'</Automation>\n</Automations>')
        parts.append(automations)
        if is_drums:
            parts.append(DRUM_NOTATION_PATCH)
        parts.append('</Track>')
        return '\n'.join(parts)

    @staticmethod
    def _build_sound_xml(instrument_name: str, instrument_id: int, inst_type: dict) -> str:
        """Build a <Sound> XML block with RSE config for a non-drum instrument."""
        fx_parts = []
        for fx_id, fx_params in inst_type.get("effect_chain", []):
            fx_parts.append(f'<Effect id="{fx_id}">\n<Parameters>{fx_params}</Parameters>\n</Effect>')
        fx_chain = '\n'.join(fx_parts)

        sb_patch = inst_type.get("soundbank_patch")
        sb_xml = f'<SoundbankPatch>{sb_patch}</SoundbankPatch>' if sb_patch else '<SoundbankPatch/>'

        return (
            f'<Sound>\n'
            f'<Name><![CDATA[{escape_xml(instrument_name)}]]></Name>\n'
            f'<Label><![CDATA[{escape_xml(instrument_name)}]]></Label>\n'
            f'<Path>{inst_type["sound_path"]}</Path>\n'
            f'<Role>User</Role>\n'
            f'<MIDI>\n<LSB>0</LSB>\n<MSB>0</MSB>\n<Program>{instrument_id}</Program>\n</MIDI>\n'
            f'<RSE>\n'
            f'{sb_xml}\n'
            f'<ElementsSettings>\n</ElementsSettings>\n'
            f'<Pickups>\n<OverloudPosition>0</OverloudPosition>\n'
            f'<Volumes>1 1</Volumes>\n<Tones>1 1</Tones>\n</Pickups>\n'
            f'<EffectChain>\n{fx_chain}\n</EffectChain>\n'
            f'</RSE>\n'
            f'</Sound>')

    def _build_staves_xml(self, is_drums: bool, frets: int, num_strings: int, tuning_str: str) -> str:
        if is_drums:
            return '''<Staves>
<Staff>
<Properties>
<Property name="CapoFret"><Fret>0</Fret></Property>
<Property name="FretCount"><Number>24</Number></Property>
<Property name="PartialCapoFret"><Fret>0</Fret></Property>
<Property name="PartialCapoStringFlags"><Bitset>000000</Bitset></Property>
<Property name="Tuning">
<Pitches>0 0 0 0 0 0</Pitches>
<Instrument>Undefined</Instrument>
<Label><![CDATA[]]></Label>
<LabelVisible>true</LabelVisible>
<Flat/>
</Property>
<Property name="ChordCollection"><Items/></Property>
<Property name="ChordWorkingSet"><Items/></Property>
<Property name="DiagramCollection"><Items/></Property>
<Property name="DiagramWorkingSet"><Items/></Property>
<Property name="TuningFlat"><Enable/></Property>
<Name><![CDATA[]]></Name>
</Properties>
</Staff>
</Staves>'''
        return f'''<Staves>
<Staff>
<Properties>
<Property name="CapoFret"><Fret>0</Fret></Property>
<Property name="FretCount"><Number>{frets}</Number></Property>
<Property name="PartialCapoFret"><Fret>0</Fret></Property>
<Property name="PartialCapoStringFlags"><Bitset>{"0" * num_strings}</Bitset></Property>
<Property name="Tuning">
<Pitches>{tuning_str}</Pitches>
<Instrument>Guitar</Instrument>
<Label><![CDATA[]]></Label>
<LabelVisible>true</LabelVisible>
</Property>
<Property name="ChordCollection"><Items/></Property>
<Property name="ChordWorkingSet"><Items/></Property>
<Property name="DiagramCollection"><Items/></Property>
<Property name="DiagramWorkingSet"><Items/></Property>
<Name><![CDATA[Standard]]></Name>
</Properties>
</Staff>
</Staves>'''

    # --- Lyrics assignment ---

    def _assign_lyrics(self):
        """Assign beat-level lyrics to tracks that have newLyrics data.

        Walks through each track's beats starting from the lyrics offset measure,
        and assigns lyric syllables to beats that have actual notes (non-rest).
        GP supports 5 lyric lines per track; each newLyrics entry maps to one line.
        """
        # Build a fast lookup: beat_id -> beat_obj
        beat_by_id = {obj["id"]: obj for obj in self._beat_objs}

        for track_idx, track_data in enumerate(self.tracks):
            new_lyrics = track_data.get("newLyrics", [])
            if not new_lyrics or not any(nl.get("text", "").strip() for nl in new_lyrics):
                continue

            # Tokenize each lyric line
            num_lines = 5  # GP supports 5 lyric lines
            line_tokens: list[list[str]] = []
            line_offsets: list[int] = []
            for li in range(num_lines):
                if li < len(new_lyrics) and new_lyrics[li].get("text", "").strip():
                    line_tokens.append(tokenize_lyrics(new_lyrics[li]["text"]))
                    line_offsets.append(new_lyrics[li].get("offset", 0))
                else:
                    line_tokens.append([])
                    line_offsets.append(0)

            if not any(line_tokens):
                continue

            # Get beat info for this track
            beat_info = self._track_beat_info[track_idx]

            # Count beats per measure to compute measure boundaries
            measures = track_data.get("measures", [])
            measure_beat_ranges: list[tuple[int, int]] = []
            beat_pos = 0
            for m in measures:
                voices = m.get("voices", [])
                n_beats = len(voices[0].get("beats", [])) if voices else 1
                measure_beat_ranges.append((beat_pos, beat_pos + n_beats))
                beat_pos += n_beats

            # For each lyric line, assign tokens to note-beats starting from offset
            line_iterators: list[int] = [0] * num_lines  # current token index per line
            # Beats remaining to skip per line (from '\n' sentinels)
            line_skip_remaining: list[int] = [0] * num_lines

            # Walk beats from the earliest offset
            min_offset = min(line_offsets[i] for i in range(num_lines) if line_tokens[i])
            start_beat = measure_beat_ranges[min_offset][0] if min_offset < len(measure_beat_ranges) else 0

            for beat_pos_idx in range(start_beat, len(beat_info)):
                bid, has_notes = beat_info[beat_pos_idx]

                if not has_notes:
                    continue  # rest beats never get lyrics

                # Determine which measure this beat belongs to
                current_measure = 0
                for mi, (s, e) in enumerate(measure_beat_ranges):
                    if s <= beat_pos_idx < e:
                        current_measure = mi
                        break

                # Check each lyric line
                lyrics_for_beat = [''] * num_lines
                has_any = False
                for li in range(num_lines):
                    if not line_tokens[li]:
                        continue
                    if current_measure < line_offsets[li]:
                        continue

                    # Consume '\n' skip sentinels (only when not mid-skip)
                    if line_skip_remaining[li] == 0:
                        count = 0
                        while (line_iterators[li] < len(line_tokens[li]) and
                               line_tokens[li][line_iterators[li]] == '\n'):
                            count += 1
                            line_iterators[li] += 1
                        line_skip_remaining[li] = count

                    # Skip note-beats for phrase breaks
                    if line_skip_remaining[li] > 0:
                        line_skip_remaining[li] -= 1
                        continue

                    if line_iterators[li] < len(line_tokens[li]):
                        lyrics_for_beat[li] = line_tokens[li][line_iterators[li]]
                        line_iterators[li] += 1
                        has_any = True

                if has_any:
                    beat_obj = beat_by_id.get(bid)
                    if beat_obj:
                        beat_obj["lyrics"] = lyrics_for_beat

    # --- Main build ---

    def build(self) -> str:
        num_tracks = len(self.tracks)

        # Parse artist/title from first track or meta
        artist = self.meta.get("artist", "")
        title = self.meta.get("title", "")
        if not artist and not title:
            name = self.tracks[0].get("name", "Track")
            if " - " in name:
                artist, title = name.split(" - ", 1)
            else:
                title = name

        # Get tempo from first track
        tempo = 120
        tempo_list = self.tracks[0].get("automations", {}).get("tempo", [])
        if tempo_list:
            tempo = tempo_list[0].get("bpm", 120)

        # Process all tracks, collecting bar IDs per track per measure
        # track_bar_ids[track_idx] = [bar_id_for_measure_0, bar_id_for_measure_1, ...]
        track_bar_ids: list[list[int]] = []
        for track_data in self.tracks:
            bar_ids = self._process_track_measures(track_data)
            track_bar_ids.append(bar_ids)

        # Assign beat-level lyrics to lyrics tracks
        self._assign_lyrics()

        # Build MasterBars (one per measure, referencing one bar from each track)
        num_measures = max(len(ids) for ids in track_bar_ids) if track_bar_ids else 0
        current_time_sig = "4/4"
        current_triplet_feel = None
        master_bar_xmls = []

        # Use first track for time signatures, markers, and triplet feel
        first_track_measures = self.tracks[0].get("measures", [])

        for i in range(num_measures):
            measure = first_track_measures[i] if i < len(first_track_measures) else {}
            sig = measure.get("signature")
            if sig:
                current_time_sig = f"{sig[0]}/{sig[1]}"

            # Track triplet feel changes (sticky, carries forward until changed)
            if "tripletFeel" in measure:
                current_triplet_feel = TRIPLET_FEEL_MAP.get(measure["tripletFeel"])

            # Collect bar IDs from each track for this measure
            bar_ids_for_measure = []
            for t_idx in range(num_tracks):
                if i < len(track_bar_ids[t_idx]):
                    bar_ids_for_measure.append(track_bar_ids[t_idx][i])
                else:
                    bar_ids_for_measure.append(track_bar_ids[t_idx][-1])

            mb = ['<MasterBar>']
            mb.append('  <Key><AccidentalCount>0</AccidentalCount><Mode>Major</Mode><TransposeAs>Sharps</TransposeAs></Key>')
            mb.append(f'  <Time>{current_time_sig}</Time>')
            mb.append(f'  <Bars>{" ".join(str(b) for b in bar_ids_for_measure)}</Bars>')

            mb.append('  <XProperties>')
            mb.append('    <XProperty id="1124139010"><Int>8</Int></XProperty>')
            mb.append('    <XProperty id="1124139264"><Int>2</Int></XProperty>')
            mb.append('    <XProperty id="1124139265"><Int>2</Int></XProperty>')
            mb.append('    <XProperty id="1124139266"><Int>2</Int></XProperty>')
            mb.append('    <XProperty id="1124139267"><Int>2</Int></XProperty>')
            mb.append('  </XProperties>')

            if "marker" in measure:
                marker_text = measure["marker"].get("text", "")
                mb.append(f'  <Section><Text><![CDATA[{marker_text}]]></Text></Section>')

            if current_triplet_feel:
                mb.append(f'  <TripletFeel>{current_triplet_feel}</TripletFeel>')

            mb.append('</MasterBar>')
            master_bar_xmls.append('\n'.join(mb))

        # Deduplicate notes and beats
        self._dedup_notes()
        self._dedup_beats()

        # Convert unique notes to XML
        canonical_note_ids = set(self._note_id_map.values())
        note_xmls = [self._note_to_xml(obj) for obj in self._note_objs
                      if obj["id"] in canonical_note_ids]

        # Convert unique beats to XML
        canonical_beat_ids = set(self._beat_id_map.values())
        beat_xmls = [self._beat_to_xml(obj) for obj in self._beat_objs
                      if obj["id"] in canonical_beat_ids]

        # Update voice XMLs with canonical beat IDs
        voice_xmls = []
        for vxml in self._voice_xmls:
            def _replace_beat_ids(m):
                ids = m.group(1).split()
                canonical = [str(self._beat_id_map.get(int(i), int(i))) for i in ids]
                return f'<Beats>{" ".join(canonical)}</Beats>'
            voice_xmls.append(re.sub(r'<Beats>([\d\s]+)</Beats>', _replace_beat_ids, vxml))

        # Tempo automations
        tempo_xmls = []
        for ta in tempo_list:
            bar = ta.get("measure", 0)
            pos = ta.get("position", 0)
            bpm = ta.get("bpm", 120)
            tempo_xmls.append(
                f'<Automation>\n  <Type>Tempo</Type>\n  <Linear>false</Linear>\n'
                f'  <Bar>{bar}</Bar>\n  <Position>{pos}</Position>\n'
                f'  <Visible>true</Visible>\n  <Value>{bpm} 2</Value>\n</Automation>')
        if not tempo_xmls:
            tempo_xmls.append(
                f'<Automation>\n  <Type>Tempo</Type>\n  <Linear>false</Linear>\n'
                f'  <Bar>0</Bar>\n  <Position>0</Position>\n'
                f'  <Visible>true</Visible>\n  <Value>{tempo} 2</Value>\n</Automation>')

        # Track IDs and XML
        track_ids_str = " ".join(str(i) for i in range(num_tracks))
        track_xmls = [self._build_track_xml(i, t) for i, t in enumerate(self.tracks)]

        return f'''<?xml version="1.0" encoding="utf-8"?>
<GPIF>
<GPVersion>8.1.4</GPVersion>
<GPRevision required="12024" recommended="13000">13007</GPRevision>
<Encoding>
<EncodingDescription>GP8</EncodingDescription>
</Encoding>
<Score>
<Title><![CDATA[{title}]]></Title>
<SubTitle><![CDATA[]]></SubTitle>
<Artist><![CDATA[{artist}]]></Artist>
<Album><![CDATA[]]></Album>
<Words><![CDATA[]]></Words>
<Music><![CDATA[]]></Music>
<WordsAndMusic><![CDATA[]]></WordsAndMusic>
<Copyright><![CDATA[]]></Copyright>
<Tabber><![CDATA[]]></Tabber>
<Instructions><![CDATA[]]></Instructions>
<Notices><![CDATA[]]></Notices>
<FirstPageHeader><![CDATA[<html><head><meta name="qrichtext" content="1" /><style type="text/css">p, li {{ white-space: pre-wrap; }}</style></head><body style=" font-family:'Times New Roman'; font-size:16pt; font-weight:400; font-style:normal;"><p align="center" style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px; font-family:'Sans Serif'; font-size:10pt;"><span style=" font-family:'Times New Roman'; font-size:35pt;">%TITLE%</span></p><p align="center" style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px; font-family:'Sans Serif'; font-size:10pt;"><span style=" font-family:'Times New Roman'; font-size:16pt;">%SUBTITLE%</span></p><p align="center" style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px; font-family:'Sans Serif'; font-size:10pt;"><span style=" font-family:'Times New Roman'; font-size:16pt;">%ARTIST%</span></p><p align="center" style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px; font-family:'Sans Serif'; font-size:10pt;"><span style=" font-family:'Times New Roman'; font-size:16pt;">%ALBUM%</span></p><p align="center" style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px; font-family:'Sans Serif'; font-size:10pt;"><span style=" font-family:'Times New Roman'; font-size:12pt;">%WORDS&amp;MUSIC%</span></p></body></html>]]></FirstPageHeader>
<FirstPageFooter><![CDATA[<html><head><meta name="qrichtext" content="1" /><style type="text/css">p, li {{ white-space: pre-wrap; }}</style></head><body style=" font-family:'Lucida Grande'; font-size:13pt; font-weight:400; font-style:normal;"><p align="right" style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px; font-family:'Times'; font-size:14pt;">Page %page%/%pages%</p></body></html>]]></FirstPageFooter>
<PageHeader><![CDATA[]]></PageHeader>
<PageFooter><![CDATA[<html><head><meta name="qrichtext" content="1" /><style type="text/css">p, li {{ white-space: pre-wrap; }}</style></head><body style=" font-family:'Lucida Grande'; font-size:13pt; font-weight:400; font-style:normal;"><p align="right" style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px; font-family:'Times'; font-size:14pt;">Page %page%/%pages%</p></body></html>]]></PageFooter>
<ScoreSystemsDefaultLayout>4</ScoreSystemsDefaultLayout>
<ScoreSystemsLayout>4</ScoreSystemsLayout>
<ScoreZoomPolicy>Value</ScoreZoomPolicy>
<ScoreZoom>1</ScoreZoom>
<MultiVoice>0></MultiVoice>
</Score>
<MasterTrack>
<Tracks>{track_ids_str}</Tracks>
<Automations>
{chr(10).join(tempo_xmls)}
</Automations>
</MasterTrack>
<Tracks>
{chr(10).join(track_xmls)}
</Tracks>
<MasterBars>
<!-- order is important here -->
{chr(10).join(master_bar_xmls)}
</MasterBars>
<Bars>
{chr(10).join(self._bar_xmls)}
</Bars>
<Voices>
{chr(10).join(voice_xmls)}
</Voices>
<Beats>
{chr(10).join(beat_xmls)}
</Beats>
<Notes>
{chr(10).join(note_xmls)}
</Notes>
<Rhythms>
{chr(10).join(self._rhythm_xmls)}
</Rhythms>
<ScoreViews>
<ScoreView id="0" />
<ScoreView id="1" />
</ScoreViews>
</GPIF>'''


# ---------------------------------------------------------------------------
# GP file generation
# ---------------------------------------------------------------------------

def generate_gp(tracks: list[dict], output_path: Path, meta: dict | None = None,
                blank_gp: Path = BLANK_GP):
    """Generate a .gp file from Songsterr track data, using blank.gp as template."""
    if not blank_gp.exists():
        print(f"Error: blank.gp template not found at {blank_gp}", file=sys.stderr)
        sys.exit(1)

    builder = GPIFBuilder(tracks, meta)
    gpif = builder.build()

    # Build new ZIP from blank.gp template, replacing score.gpif
    tmp_path = output_path.with_suffix(".gp.tmp")
    with zipfile.ZipFile(str(blank_gp), "r") as src, \
         zipfile.ZipFile(str(tmp_path), "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            if item.filename == "Content/score.gpif":
                dst.writestr(item, gpif.encode("utf-8"))
            else:
                dst.writestr(item, src.read(item.filename))
    tmp_path.replace(output_path)

    # Print summary
    num_measures = len(tracks[0].get("measures", []))
    tempo_list = tracks[0].get("automations", {}).get("tempo", [])
    tempo = tempo_list[0]["bpm"] if tempo_list else 120

    print(f"\n  Tracks: {len(tracks)}")
    for i, t in enumerate(tracks):
        print(f"    {i}: {t.get('name', 'Track')} ({t.get('instrument', '?')})")
    print(f"  Measures: {num_measures}")
    print(f"  Tempo: {tempo} BPM")
    unique_notes = len(set(builder._note_id_map.values()))
    unique_beats = len(set(builder._beat_id_map.values()))
    print(f"  Notes: {builder._counters['note']} total, {unique_notes} unique")
    print(f"  Beats: {builder._counters['beat']} total, {unique_beats} unique")
    print(f"\nGenerated: {output_path}")


def parse_song_id(value: str) -> int:
    """Parse song ID from a Songsterr URL or raw number."""
    value = value.strip()
    m = re.search(r'-s(\d+)', value)
    if m:
        return int(m.group(1))
    if value.isdigit():
        return int(value)
    raise ValueError(f"Could not parse song ID from: {value}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate a Guitar Pro (.gp) file from Songsterr tab data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python gen_gp.py --song 61178
  python gen_gp.py --song https://www.songsterr.com/a/wsa/ozzy-osbourne-crazy-train-tab-s61178
  python gen_gp.py --song 61178 -o crazy_train.gp
  python gen_gp.py input.json -o output.gp
        """,
    )
    parser.add_argument("input", nargs="?", help="JSON file path or '-' for stdin (single track mode)")
    parser.add_argument("--song", type=str, help="Songsterr song ID or URL (fetches all tracks)")
    parser.add_argument("-o", "--output", help="Output GP file path")

    args = parser.parse_args()

    if not args.song and not args.input:
        parser.error("Provide --song <id/url> or a JSON file path")

    if args.song:
        # Fetch from Songsterr
        song_id = parse_song_id(args.song)
        print(f"Fetching song {song_id} from Songsterr...")
        meta, tracks = fetch_all_tracks(song_id)

        if args.output:
            output_path = Path(args.output)
        else:
            safe = "".join(c if c.isalnum() or c in " -_" else "" for c in
                           f"{meta['artist']} - {meta['title']}").strip()
            output_path = Path(f"{safe or 'output'}.gp")

        generate_gp(tracks, output_path, meta)
    else:
        # Local JSON file (single track)
        if args.input == "-":
            data = json.load(sys.stdin)
        else:
            with open(args.input) as f:
                data = json.load(f)

        if args.output:
            output_path = Path(args.output)
        else:
            name = data.get("name", "output")
            safe = "".join(c if c.isalnum() or c in " -_" else "" for c in name).strip()
            output_path = Path(f"{safe or 'output'}.gp")

        generate_gp([data], output_path)


if __name__ == "__main__":
    main()
