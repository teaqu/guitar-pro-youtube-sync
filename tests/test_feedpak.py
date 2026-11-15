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

def test_export_without_vorbis_encoder_uses_readable_wav(tmp_path, monkeypatch):
 import json
 import shutil
 import subprocess
 import wave
 import zipfile
 import feedpak
 if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
  pytest.skip('FFmpeg tools are covered by the packaged self-test')
 source=tmp_path/'source.wav'
 with wave.open(str(source),'wb') as audio:
  audio.setparams((1,2,8000,0,'NONE','not compressed'))
  audio.writeframes(b'\0\0'*8000)
 original=subprocess.run
 def without_vorbis(args, **kwargs):
  if '-encoders' in args:
   return subprocess.CompletedProcess(args,0,stdout='pcm_s16le',stderr='')
  return original(args,**kwargs)
 monkeypatch.setattr(feedpak.subprocess,'run',without_vorbis)
 track={'instrument':'Steel Guitar','tuning':[64,59,55,50,45,40], 'measures':[{'voices':[{'beats':[{'duration':[1,4], 'notes':[{'string':0,'fret':3}]}]}]}]}
 output=feedpak.export_feedpak({'artist':'Test','title':'WAV fallback'},[track],[0,1],source,tmp_path/'test.feedpak')
 with zipfile.ZipFile(output) as archive:
  manifest=json.loads(archive.read('manifest.yaml'))
  stem=manifest['stems'][0]['file']
  assert stem=='stems/full.wav'
  import io
  with wave.open(io.BytesIO(archive.read(stem))) as audio:
   assert audio.getnframes()/audio.getframerate()==pytest.approx(1)


def test_export_preserves_dead_strings_and_separate_palm_mutes(tmp_path):
 import json
 import shutil
 import wave
 import zipfile
 from pathlib import Path
 from feedpak import export_feedpak
 if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
  pytest.skip('FFmpeg tools are covered by the packaged self-test')
 source=tmp_path/'source.wav'
 with wave.open(str(source),'wb') as audio:
  audio.setparams((1,2,8000,0,'NONE','not compressed'))
  audio.writeframes(b'\0\0'*16000)
 faint=json.loads((Path(__file__).parent/'fixtures/faint-dead-beat.json').read_text())
 beats=[
  {'type':8,'duration':[1,8],'notes':[{'fret':7,'string':3,'dead':True}]},
  faint,
  {'type':4,'duration':[1,4],'notes':[{'fret':7,'string':3}]},
  {'type':4,'duration':[1,4],'palmMute':True,'notes':[{'fret':7,'string':3}]},
  {'type':8,'duration':[1,8],'notes':[{'fret':7,'string':3,'ghost':True}]},
  {'type':8,'duration':[1,8],'rest':True,'notes':[{'rest':True}]},
 ]
 track={'name':'Faint regression','instrument':'Distortion Guitar','tuning':[64,59,55,50,45,40],
        'measures':[{'signature':[4,4],'voices':[{'beats':beats}]}]}
 output=export_feedpak({'artist':'Test','title':'Dead strings'},[track],[0,2],source,tmp_path/'test.feedpak')
 with zipfile.ZipFile(output) as archive:
  manifest=json.loads(archive.read('manifest.yaml'))
  notes=json.loads(archive.read(manifest['arrangements'][0]['file']))['notes']
 assert [(n['t'],n['s'],n['f'],n['sus'],n.get('mt',False),n.get('pm',False)) for n in notes]==[
  (0,2,7,0.25,True,False),
  (0.25,1,5,0.25,False,False),
  (0.25,2,7,0.25,True,False),
  (0.25,3,7,0.25,False,False),
  (0.5,2,7,0.5,False,False),
  (1,2,7,0.5,False,True),
  (1.5,2,7,0.25,False,False),
 ]
