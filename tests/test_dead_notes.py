"""Dead strings stay note-local through GP generation and deduplication."""

import json
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest

from gen_gp import generate_gp


def export_score(tmp_path, beats):
    track = {
        "name": "Dead note regression", "instrument": "Distortion Guitar",
        "instrumentId": 30, "strings": 6, "tuning": [64, 59, 55, 50, 45, 40],
        "measures": [{"voices": [{"beats": beats}]}],
    }
    output = tmp_path / "dead.gp"
    generate_gp([track], output)
    with ZipFile(output) as archive:
        assert archive.testzip() is None
        root = ET.fromstring(archive.read("Content/score.gpif"))
    notes = {n.attrib["id"]: n for n in root.findall("Notes/Note")}
    rhythms = {r.attrib["id"]: r for r in root.findall("Rhythms/Rhythm")}
    beats_by_id = {b.attrib["id"]: b for b in root.findall("Beats/Beat")}
    ordered = [beats_by_id[i] for i in root.findtext("Voices/Voice/Beats").split()]
    return root, [[notes[i] for i in b.findtext("Notes", "").split()] for b in ordered], [
        rhythms[b.find("Rhythm").attrib["ref"]] for b in ordered]


def prop(note, name):
    return note.find(f"Properties/Property[@name='{name}']")


def test_single_dead_note_keeps_string_fret_and_dotted_duration(tmp_path):
    root, beats, rhythms = export_score(tmp_path, [
        {"type": 8, "dots": 1, "notes": [{"fret": 7, "string": 3, "dead": True}]},
    ])
    note, = beats[0]
    assert prop(note, "Muted").find("Enable") is not None
    assert prop(note, "Fret").findtext("Fret") == "7"
    assert prop(note, "String").findtext("String") == "2"
    assert rhythms[0].findtext("NoteValue") == "Eighth"
    assert rhythms[0].find("AugmentationDot").attrib["count"] == "1"
    assert note.find("AntiAccent") is None
    assert prop(note, "PalmMuted") is None


def test_faint_mixed_chord_and_identical_normal_note_do_not_deduplicate(tmp_path):
    # Unmodified beat from Faint, song 502, revision 9803522, part 2,
    # measure 9, beat 2. Only its middle string has dead=true.
    beat = json.loads((Path(__file__).parent / "fixtures/faint-dead-beat.json").read_text())
    normal = {"type": 8, "notes": [{"fret": 7, "string": 3}]}
    _, beats, rhythms = export_score(tmp_path, [normal, beat, normal, beat])
    assert len(beats) == 4
    assert [len(b) for b in beats] == [1, 3, 1, 3]
    for chord in (beats[1], beats[3]):
        assert [prop(n, "Muted") is not None for n in chord] == [False, True, False]
        assert [prop(n, "String").findtext("String") for n in chord] == ["3", "2", "1"]
        assert [prop(n, "Fret").findtext("Fret") for n in chord] == ["7", "7", "5"]
        assert chord[1].attrib["id"] != beats[0][0].attrib["id"]
    assert beats[0][0].attrib["id"] == beats[2][0].attrib["id"]
    assert all(r.findtext("NoteValue") == "Eighth" for r in rhythms)


@pytest.mark.parametrize("marking", [{}, {"dead": False}, {"palmMute": True}, {"ghost": True}])
def test_ordinary_palm_and_ghost_notes_are_not_dead(tmp_path, marking):
    _, beats, _ = export_score(tmp_path, [
        {"type": 4, "palmMute": True, "notes": [{"fret": 5, "string": 1, **marking}]},
        {"type": 4, "rest": True, "notes": [{"rest": True}]},
        {"type": 4, "notes": [{"fret": 5, "string": 1, "dead": True}]},
    ])
    note, = beats[0]
    assert prop(note, "Muted") is None
    assert prop(note, "Fret").findtext("Fret") == "5"
    assert prop(note, "String").findtext("String") == "4"
    assert (note.find("AntiAccent") is not None) == marking.get("ghost", False)
    assert beats[1] == []
    assert prop(beats[2][0], "Muted").find("Enable") is not None
