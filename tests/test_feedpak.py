from feedpak import _length
import pytest

@pytest.mark.parametrize('beat,expected', [
 ({'type':4,'dots':1,'duration':[3,8]},3/8),
 ({'type':8,'tuplet':3,'duration':[1,12]},1/12),
 ({'type':4,'dots':1},3/8),
 ({'type':8,'tuplet':3},1/12),
])
def test_songsterr_duration_is_authoritative(beat,expected):
 assert _length(beat) == pytest.approx(expected)
from feedpak_effects import playback_order, apply_techniques


def test_repeat_endings_and_nested_repeats():
 assert playback_order([{'repeatStart':True},{'alternateEnding':1,'repeat':2},{'alternateEnding':2},{}]) == [0,1,0,2,3]
 assert playback_order([{'repeatStart':True},{'repeatStart':True},{'repeat':2},{'repeat':2}]) == [0,1,2,1,2,3,0,1,2,1,2,3]


def event(t, fret, source=None, sustain=1, beat=None):
 return ({'t':t,'s':0,'f':fret,'sus':sustain},source or {},beat or {})


def test_ties_merge_without_repeated_attack_and_preserve_bend_curve():
 notes=apply_techniques([event(0,7,{'bend':{'points':[{'position':0,'tone':0},{'position':60,'tone':100}]}}),event(1,7,{'tie':True}),event(2,9,{'hp':True})])
 assert len(notes)==2
 assert notes[0]['sus']==2
 assert notes[0]['bn']==2
 assert notes[0]['bnv']==[{'t':0,'v':0},{'t':1,'v':2}]
 assert notes[1]['ho'] is True


def test_slide_pull_off_harmonics_vibrato_and_palm_mute():
 notes=apply_techniques([event(0,9,{'slide':'legato','leftHandVibrato':'slight'}),event(1,7,{'hp':True,'harmonic':'natural'},beat={'palmMute':True})])
 assert notes[0]['sl']==7
 assert notes[0]['vb'] is True
 assert notes[1]['po'] is True
 assert notes[1]['hm'] is True
 assert notes[1]['pm'] is True


def test_tie_after_rest_is_not_joined():
 notes=apply_techniques([event(0,7),event(2,7,{'tie':True})])
 assert len(notes)==2
