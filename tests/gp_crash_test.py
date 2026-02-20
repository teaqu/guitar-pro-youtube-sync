#!/usr/bin/env python3
"""Generate a GP file that exercises every feature of gen_gp.py."""

import json
from pathlib import Path
from gen_gp import generate_gp

# Standard guitar tuning (low to high): E2 A2 D3 G3 B3 E4
STD_TUNING = [40, 45, 50, 55, 59, 64]
BASS_TUNING = [28, 33, 38, 43]


def make_beat(notes=None, **kwargs):
    """Make a beat dict with defaults."""
    beat = {"type": kwargs.get("type", 4), "notes": notes or []}
    if kwargs.get("rest"):
        beat["rest"] = True
    if kwargs.get("dots"):
        beat["dots"] = kwargs["dots"]
    if kwargs.get("tuplet"):
        beat["tuplet"] = kwargs["tuplet"]
    if kwargs.get("velocity"):
        beat["velocity"] = kwargs["velocity"]
    if kwargs.get("gradualVelocity"):
        beat["gradualVelocity"] = kwargs["gradualVelocity"]
    if kwargs.get("text"):
        beat["text"] = {"text": kwargs["text"]}
    if kwargs.get("graceNote"):
        beat["graceNote"] = kwargs["graceNote"]
    if kwargs.get("chord"):
        beat["chord"] = kwargs["chord"]
    if kwargs.get("tremoloBar"):
        beat["tremoloBar"] = kwargs["tremoloBar"]
    if kwargs.get("letRing"):
        beat["letRing"] = True
    return beat


def make_note(string, fret, **kwargs):
    """Make a note dict."""
    note = {"string": string, "fret": fret}
    for k in ("tie", "hp", "ghost", "staccato", "accentuated", "bend", "slide"):
        if k in kwargs:
            note[k] = kwargs[k]
    return note


def make_measure(beats, sig=None, marker=None, tripletFeel=None, voices=None):
    """Make a measure dict. If voices provided, use directly. Otherwise wrap beats in voice 0."""
    m = {}
    if voices:
        m["voices"] = voices
    else:
        m["voices"] = [{"beats": beats}]
    if sig:
        m["signature"] = sig
    if marker:
        m["marker"] = {"text": marker}
    if tripletFeel:
        m["tripletFeel"] = tripletFeel
    return m


# ---- Track 1: Electric Guitar - Core features ----
guitar_measures = [
    # Measure 1: Time sig 4/4, section marker, basic notes + dynamics
    make_measure(
        [
            make_beat([make_note(0, 5), make_note(1, 7)], velocity="ff"),  # chord
            make_beat([make_note(0, 3)], velocity="mf"),
            make_beat([make_note(0, 5)], velocity="p"),
            make_beat([make_note(0, 7)], velocity="ppp"),
        ],
        sig=[4, 4], marker="Intro"
    ),
    # Measure 2: Dotted notes, ties
    make_measure([
        make_beat([make_note(0, 5)], type=4, dots=1),  # dotted quarter
        make_beat([make_note(0, 5, tie=True)], type=8),  # tied 8th
        make_beat([make_note(1, 7)], type=2),  # half note
    ]),
    # Measure 3: Bends (2-point, 3-point, 4-point)
    make_measure([
        make_beat([make_note(0, 7, bend={"points": [
            {"tone": 0, "position": 0}, {"tone": 100, "position": 60}
        ]})]),
        make_beat([make_note(0, 7, bend={"points": [
            {"tone": 0, "position": 0}, {"tone": 100, "position": 30}, {"tone": 0, "position": 60}
        ]})]),
        make_beat([make_note(0, 7, bend={"points": [
            {"tone": 0, "position": 0}, {"tone": 100, "position": 20},
            {"tone": 100, "position": 40}, {"tone": 0, "position": 60}
        ]})]),
        make_beat(rest=True),
    ]),
    # Measure 4: Slides
    make_measure([
        make_beat([make_note(0, 5, slide="toNext")]),
        make_beat([make_note(0, 7, slide="legato")]),
        make_beat([make_note(0, 9, slide="below")]),
        make_beat([make_note(0, 12, slide="above")]),
    ]),
    # Measure 5: Ghost notes, staccato, accents
    make_measure([
        make_beat([make_note(0, 5, ghost=True)]),
        make_beat([make_note(0, 7, staccato=True)]),
        make_beat([make_note(0, 9, accentuated=1)]),
        make_beat([make_note(0, 12, accentuated=2)]),
    ]),
    # Measure 6: Hammer-on/pull-off (hopo)
    make_measure([
        make_beat([make_note(0, 5)]),
        make_beat([make_note(0, 7, hp=True)]),
        make_beat([make_note(0, 5, hp=True)]),
        make_beat(rest=True),
    ]),
    # Measure 7: Let ring
    make_measure([
        make_beat([make_note(0, 0), make_note(1, 2), make_note(2, 2),
                   make_note(3, 1), make_note(4, 0), make_note(5, 0)], letRing=True),
        make_beat(rest=True),
        make_beat(rest=True),
        make_beat(rest=True),
    ]),
    # Measure 8: Grace notes + chords
    make_measure([
        make_beat([make_note(0, 5)], graceNote="beforeBeat"),
        make_beat([make_note(0, 7)]),
        make_beat([make_note(0, 9)], graceNote="onBeat"),
        make_beat([make_note(0, 12)], chord={"text": "Am"}),
    ]),
    # Measure 9: Free text, crescendo/decrescendo
    make_measure([
        make_beat([make_note(0, 5)], text="let ring", gradualVelocity="crescendo"),
        make_beat([make_note(0, 7)]),
        make_beat([make_note(0, 9)], gradualVelocity="decrescendo"),
        make_beat([make_note(0, 5)]),
    ]),
    # Measure 10: Whammy bar (tremolo bar)
    make_measure([
        make_beat([make_note(0, 5)], tremoloBar={"points": [
            {"tone": 0, "position": 0}, {"tone": -100, "position": 60}
        ]}),
        make_beat([make_note(0, 7)], tremoloBar={"points": [
            {"tone": 0, "position": 0}, {"tone": -50, "position": 30}, {"tone": 0, "position": 60}
        ]}),
        make_beat(rest=True),
        make_beat(rest=True),
    ]),
    # Measure 11: Tuplets (triplet)
    make_measure([
        make_beat([make_note(0, 5)], type=8, tuplet=3),
        make_beat([make_note(0, 7)], type=8, tuplet=3),
        make_beat([make_note(0, 9)], type=8, tuplet=3),
        make_beat(rest=True, type=2),
    ]),
    # Measure 12: Various note durations
    make_measure([
        make_beat([make_note(0, 5)], type=1),  # whole note
    ]),
    # Measure 13: 16th notes
    make_measure([
        make_beat([make_note(0, 5)], type=16),
        make_beat([make_note(0, 7)], type=16),
        make_beat([make_note(0, 9)], type=16),
        make_beat([make_note(0, 12)], type=16),
        make_beat([make_note(0, 5)], type=16),
        make_beat([make_note(0, 7)], type=16),
        make_beat([make_note(0, 9)], type=16),
        make_beat([make_note(0, 12)], type=16),
        make_beat(rest=True, type=2),
    ]),
    # Measure 14: Multiple voices
    make_measure(
        beats=None,
        voices=[
            {"beats": [
                make_beat([make_note(0, 5)], type=2),
                make_beat([make_note(0, 7)], type=2),
            ]},
            {"beats": [
                make_beat([make_note(2, 5)], type=4),
                make_beat([make_note(2, 7)], type=4),
                make_beat([make_note(2, 9)], type=4),
                make_beat([make_note(2, 12)], type=4),
            ]},
        ],
    ),
    # Measure 15: Multiple chords
    make_measure([
        make_beat([make_note(0, 0), make_note(1, 2), make_note(2, 2)], chord={"text": "Em"}),
        make_beat([make_note(0, 3), make_note(1, 2), make_note(2, 0)], chord={"text": "G"}),
        make_beat([make_note(0, 0), make_note(1, 0), make_note(2, 2)], chord={"text": "D"}),
        make_beat([make_note(0, 0), make_note(1, 2), make_note(2, 2)], chord={"text": "Em"}),  # reuse
    ]),
    # Measure 16: Time signature change to 3/4
    make_measure(
        [
            make_beat([make_note(0, 5)]),
            make_beat([make_note(0, 7)]),
            make_beat([make_note(0, 9)]),
        ],
        sig=[3, 4], marker="Bridge"
    ),
    # Measure 17: Triplet feel
    make_measure(
        [
            make_beat([make_note(0, 5)]),
            make_beat([make_note(0, 7)]),
            make_beat([make_note(0, 9)]),
        ],
        tripletFeel="8th"
    ),
    # Measure 18: Back to 4/4
    make_measure(
        [
            make_beat([make_note(0, 5)]),
            make_beat([make_note(0, 7)]),
            make_beat([make_note(0, 9)]),
            make_beat([make_note(0, 12)]),
        ],
        sig=[4, 4], tripletFeel="16th"
    ),
    # Measure 19: 32nd notes
    make_measure([
        make_beat([make_note(0, 5)], type=32),
        make_beat([make_note(0, 7)], type=32),
        make_beat([make_note(0, 9)], type=32),
        make_beat([make_note(0, 12)], type=32),
        make_beat([make_note(0, 5)], type=32),
        make_beat([make_note(0, 7)], type=32),
        make_beat([make_note(0, 9)], type=32),
        make_beat([make_note(0, 12)], type=32),
        make_beat(rest=True, type=2),
    ]),
    # Measure 20: Full rest measure
    make_measure([
        make_beat(rest=True, type=1),
    ]),
]

track_guitar = {
    "name": "Lead Guitar",
    "instrument": "Distortion Guitar",
    "instrumentId": 30,
    "strings": 6,
    "frets": 24,
    "tuning": list(reversed(STD_TUNING)),
    "measures": guitar_measures,
    "automations": {"tempo": [
        {"measure": 0, "position": 0, "bpm": 120},
        {"measure": 8, "position": 0, "bpm": 140},
        {"measure": 16, "position": 0, "bpm": 100},
    ]},
    "newLyrics": [
        {"text": "Hel-lo  world this is a test\n Song-sterr   gen-er-a-tor", "offset": 0},
    ],
}

# ---- Track 2: Bass ----
bass_measures = []
for _ in range(len(guitar_measures)):
    bass_measures.append(make_measure([
        make_beat([make_note(0, 0)]),
        make_beat([make_note(0, 3)]),
        make_beat([make_note(0, 5)]),
        make_beat(rest=True),
    ]))
# Fix time sig measures to match guitar
bass_measures[0] = make_measure(bass_measures[0]["voices"][0]["beats"], sig=[4, 4])
bass_measures[15] = make_measure(
    [make_beat([make_note(0, 0)]), make_beat([make_note(0, 3)]), make_beat([make_note(0, 5)])],
    sig=[3, 4])
bass_measures[16] = make_measure(
    [make_beat([make_note(0, 0)]), make_beat([make_note(0, 3)]), make_beat([make_note(0, 5)])])
bass_measures[17] = make_measure(
    [make_beat([make_note(0, 0)]), make_beat([make_note(0, 3)]),
     make_beat([make_note(0, 5)]), make_beat([make_note(0, 7)])],
    sig=[4, 4])

track_bass = {
    "name": "Bass",
    "instrument": "Electric Bass",
    "instrumentId": 33,
    "strings": 4,
    "frets": 24,
    "tuning": list(reversed(BASS_TUNING)),
    "measures": bass_measures,
    "automations": {},
    "newLyrics": [],
}

# ---- Track 3: Drums ----
drum_measures = []
for _ in range(len(guitar_measures)):
    drum_measures.append(make_measure([
        make_beat([make_note(0, 36), make_note(1, 42)]),   # kick + hi-hat
        make_beat([make_note(0, 38), make_note(1, 42)]),   # snare + hi-hat
        make_beat([make_note(0, 36), make_note(1, 42)]),   # kick + hi-hat
        make_beat([make_note(0, 38), make_note(1, 46)]),   # snare + open hi-hat
    ]))
drum_measures[0] = make_measure(drum_measures[0]["voices"][0]["beats"], sig=[4, 4])
drum_measures[15] = make_measure(
    [make_beat([make_note(0, 36)]), make_beat([make_note(0, 38)]), make_beat([make_note(0, 36)])],
    sig=[3, 4])
drum_measures[16] = make_measure(
    [make_beat([make_note(0, 36)]), make_beat([make_note(0, 38)]), make_beat([make_note(0, 36)])])
drum_measures[17] = make_measure(
    [make_beat([make_note(0, 36)]), make_beat([make_note(0, 38)]),
     make_beat([make_note(0, 36)]), make_beat([make_note(0, 38)])],
    sig=[4, 4])

track_drums = {
    "name": "Drums",
    "instrument": "Drums",
    "instrumentId": 1024,
    "strings": 6,
    "frets": 24,
    "measures": drum_measures,
    "automations": {},
    "newLyrics": [],
}

# ---- Track 4: Acoustic Guitar (clean features) ----
acoustic_measures = []
for _ in range(len(guitar_measures)):
    acoustic_measures.append(make_measure([
        make_beat([make_note(0, 0), make_note(1, 0), make_note(2, 0),
                   make_note(3, 2), make_note(4, 3), make_note(5, 0)], letRing=True),
        make_beat(rest=True),
        make_beat(rest=True),
        make_beat(rest=True),
    ]))
acoustic_measures[0] = make_measure(acoustic_measures[0]["voices"][0]["beats"], sig=[4, 4])
acoustic_measures[15] = make_measure(
    [make_beat([make_note(0, 0), make_note(1, 0), make_note(2, 0)], letRing=True),
     make_beat(rest=True), make_beat(rest=True)],
    sig=[3, 4])
acoustic_measures[16] = make_measure(
    [make_beat([make_note(0, 0)], letRing=True), make_beat(rest=True), make_beat(rest=True)])
acoustic_measures[17] = make_measure(
    [make_beat([make_note(0, 0)], letRing=True), make_beat(rest=True),
     make_beat(rest=True), make_beat(rest=True)], sig=[4, 4])

track_acoustic = {
    "name": "Acoustic Guitar",
    "instrument": "Acoustic Guitar",
    "instrumentId": 25,
    "strings": 6,
    "frets": 24,
    "tuning": list(reversed(STD_TUNING)),
    "measures": acoustic_measures,
    "automations": {},
    "newLyrics": [],
}

# ---- Track 5: Piano ----
piano_tuning = [21, 23, 24, 26, 28, 29]  # dummy tuning for piano

piano_measures = []
for _ in range(len(guitar_measures)):
    piano_measures.append(make_measure([
        make_beat([make_note(0, 40)]),  # C4
        make_beat([make_note(0, 44)]),  # E4
        make_beat([make_note(0, 47)]),  # G4
        make_beat(rest=True),
    ]))
piano_measures[0] = make_measure(piano_measures[0]["voices"][0]["beats"], sig=[4, 4])
piano_measures[15] = make_measure(
    [make_beat([make_note(0, 40)]), make_beat([make_note(0, 44)]), make_beat([make_note(0, 47)])],
    sig=[3, 4])
piano_measures[16] = make_measure(
    [make_beat([make_note(0, 40)]), make_beat([make_note(0, 44)]), make_beat([make_note(0, 47)])])
piano_measures[17] = make_measure(
    [make_beat([make_note(0, 40)]), make_beat([make_note(0, 44)]),
     make_beat([make_note(0, 47)]), make_beat([make_note(0, 40)])], sig=[4, 4])

track_piano = {
    "name": "Piano",
    "instrument": "Piano",
    "instrumentId": 0,
    "strings": 6,
    "frets": 24,
    "tuning": list(reversed(piano_tuning)),
    "measures": piano_measures,
    "automations": {},
    "newLyrics": [],
}

# ---- Track 6: Multi-sound track (overdrive -> clean switch) ----
multi_measures = []
for _ in range(len(guitar_measures)):
    multi_measures.append(make_measure([
        make_beat([make_note(0, 5)]),
        make_beat([make_note(0, 7)]),
        make_beat([make_note(0, 9)]),
        make_beat([make_note(0, 12)]),
    ]))
multi_measures[0] = make_measure(multi_measures[0]["voices"][0]["beats"], sig=[4, 4])
multi_measures[15] = make_measure(
    [make_beat([make_note(0, 5)]), make_beat([make_note(0, 7)]), make_beat([make_note(0, 9)])],
    sig=[3, 4])
multi_measures[16] = make_measure(
    [make_beat([make_note(0, 5)]), make_beat([make_note(0, 7)]), make_beat([make_note(0, 9)])])
multi_measures[17] = make_measure(
    [make_beat([make_note(0, 5)]), make_beat([make_note(0, 7)]),
     make_beat([make_note(0, 9)]), make_beat([make_note(0, 12)])], sig=[4, 4])

track_multi_sound = {
    "name": "Rhythm Guitar",
    "instrument": "Overdrive Guitar",
    "instrumentId": 29,
    "strings": 6,
    "frets": 24,
    "tuning": list(reversed(STD_TUNING)),
    "measures": multi_measures,
    "automations": {},
    "sounds": [
        {"label": "Overdrive Guitar", "instrumentId": 29},
        {"label": "Clean Guitar", "instrumentId": 27},
    ],
    "trackAutomations": {
        "trackSoundAutomations": [
            {"soundId": 0, "measure": 0, "position": 0},
            {"soundId": 1, "measure": 10, "position": 0},
        ]
    },
    "newLyrics": [],
}

# ---- Track 7: Violin ----
violin_tuning = [55, 62, 69, 76]  # G3, D4, A4, E5

violin_measures = []
for _ in range(len(guitar_measures)):
    violin_measures.append(make_measure([
        make_beat([make_note(0, 0)]),
        make_beat([make_note(0, 2)]),
        make_beat([make_note(0, 4)]),
        make_beat([make_note(0, 5)]),
    ]))
violin_measures[0] = make_measure(violin_measures[0]["voices"][0]["beats"], sig=[4, 4])
violin_measures[15] = make_measure(
    [make_beat([make_note(0, 0)]), make_beat([make_note(0, 2)]), make_beat([make_note(0, 4)])],
    sig=[3, 4])
violin_measures[16] = make_measure(
    [make_beat([make_note(0, 0)]), make_beat([make_note(0, 2)]), make_beat([make_note(0, 4)])])
violin_measures[17] = make_measure(
    [make_beat([make_note(0, 0)]), make_beat([make_note(0, 2)]),
     make_beat([make_note(0, 4)]), make_beat([make_note(0, 5)])], sig=[4, 4])

track_violin = {
    "name": "Violin",
    "instrument": "Violin",
    "instrumentId": 40,
    "strings": 4,
    "frets": 24,
    "tuning": list(reversed(violin_tuning)),
    "measures": violin_measures,
    "automations": {},
    "newLyrics": [],
}


# Assemble all tracks
all_tracks = [
    track_guitar,       # Distortion guitar with all features
    track_bass,         # Bass
    track_drums,        # Drums
    track_acoustic,     # Acoustic guitar with let ring
    track_piano,        # Piano (the previously-broken instrument)
    track_multi_sound,  # Multi-sound track with sound automation
    track_violin,       # Orchestral string
]

meta = {"artist": "Test", "title": "All Features"}

generate_gp(all_tracks, Path("test_everything.gp"), meta)
