from xml.etree import ElementTree as ET
from zipfile import ZipFile

from sync import sync_gp_file


def test_existing_score_with_multibar_ending(tmp_path):
    source = tmp_path / "edited.gp"
    markers = [
        '<Repeat start="true"/>', '', '<AlternateEndings>1</AlternateEndings>',
        '<Repeat end="true" count="2"/>', '<AlternateEndings>2</AlternateEndings>', '',
    ]
    bars = ''.join(f'<MasterBar><Time>4/4</Time>{marker}</MasterBar>' for marker in markers)
    with ZipFile(source, 'w') as archive:
        archive.writestr('Content/score.gpif', '<GPIF><MasterTrack><Automations></Automations>'
                         f'</MasterTrack><MasterBars>{bars}</MasterBars></GPIF>')
    audio = tmp_path / 'audio.mp3'
    audio.write_bytes(b'test asset')
    target = tmp_path / 'synced.gp'
    bpms = sync_gp_file(source, list(range(2, 10)), target, audio)
    assert bpms == [240] * 8
    with ZipFile(target) as archive:
        score = ET.fromstring(archive.read('Content/score.gpif'))
    anchors = score.findall(".//Automation[Type='SyncPoint']")
    assert [int(anchor.findtext('Bar')) for anchor in anchors] == list(range(8))
    values = [anchor.find('Value') for anchor in anchors]
    visits = [(int(v.findtext('BarIndex')), int(v.findtext('BarOccurrence'))) for v in values]
    assert visits == [(0, 0), (1, 0), (2, 0), (3, 0), (0, 1), (1, 1), (4, 0), (5, 0)]
    assert [int(v.findtext('FrameOffset')) for v in values] == [i * 44100 for i in range(8)]
