"""Export Songsterr guitar and bass tracks as a fee[dB]ack feedpak."""
import json
import logging
import math
import shutil
from itertools import groupby
import subprocess
import tempfile
import zipfile
from pathlib import Path

from sync import _ffmpeg_bin
from feedpak_effects import playback_order, apply_techniques

STANDARD = {4: [28, 33, 38, 43], 5: [23, 28, 33, 38, 43],
            6: [40, 45, 50, 55, 59, 64], 7: [35, 40, 45, 50, 55, 59, 64]}


def _length(beat):
    """Beat length in whole notes, accounting for dots and tuplets."""
    if beat.get('duration'):
        numerator, denominator = beat['duration']
        return numerator / denominator
    tuplet = beat.get('tuplet')
    if tuplet:
        length = 1 / (beat.get('type') or 4)
        normal = {3: 2, 5: 4, 6: 4, 7: 4, 9: 8, 10: 8, 12: 8}.get(tuplet, 2 ** int(math.log2(tuplet)))
        length *= normal / tuplet
    else:
        duration = beat.get('duration')
        length = duration[0] / duration[1] if duration else 1 / (beat.get('type') or 4)
    return length * (2 - 2 ** -(beat.get('dots') or 0))


def configure_logging():
    logger = logging.getLogger('feedpak')
    if not logger.handlers:
        handler = logging.FileHandler('feedpak-export.log', encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False


def export_feedpak(meta, tracks, points, audio, output, audio_offset=0):
    """Write an archive, decoding audio before applying any requested offset."""
    configure_logging()
    logger = logging.getLogger('feedpak')
    logger.info('Exporting %s - %s', meta.get('artist'), meta.get('title'))
    if len(points) < 2 or any(b <= a for a, b in zip(points, points[1:])):
        raise ValueError('At least two strictly increasing video sync points are required.')
    if not Path(audio).is_file():
        raise ValueError('A downloaded audio file is required for a feedpak.')
    playable = [(i, t) for i, t in enumerate(tracks) if t.get('tuning') and len(t['tuning']) in STANDARD and any(kind in (t.get('instrument') or '').lower() for kind in ('guitar', 'bass'))]
    if not playable:
        raise ValueError('No supported 4–7 string guitar or bass tracks were found.')
    master = max((t for _, t in playable), key=lambda t: len(t.get('measures', [])))
    written_signatures, signature = [], [4, 4]
    for measure in master.get('measures', []):
        signature = measure.get('signature') or signature
        written_signatures.append(signature)
    order = playback_order(master['measures'])
    count = len(order)
    if len(points) not in (count, count + 1):
        logger.error('Sync-point mismatch: %s points, %s played bars', len(points), count)
        raise ValueError('Video timing does not match the chart playback order; export cancelled.')
    signatures = [written_signatures[i] for i in order]
    starts = [p - points[0] for p in points]
    if len(starts) == count:
        starts.append(starts[-1] + starts[-1] - starts[-2])
        logger.info('Last bar end estimated from preceding bar duration')
    logger.info('Playback: %s written bars, %s played bars', len(master['measures']), count)
    output = Path(output)
    if output.exists():
        raise FileExistsError(f'Output already exists: {output}')
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / 'arrangements').mkdir()
        (root / 'stems').mkdir()
        keep_ogg = Path(audio).suffix.lower() == '.ogg' and not audio_offset
        encoders = subprocess.run([_ffmpeg_bin(), '-hide_banner', '-encoders'], capture_output=True, text=True, check=True).stdout
        vorbis = keep_ogg or 'libvorbis' in encoders
        stem_file = 'stems/full.ogg' if vorbis else 'stems/full.wav'
        ogg = root / stem_file
        if keep_ogg:
            shutil.copyfile(audio, ogg)
        else:
            codec = ['-c:a', 'libvorbis', '-q:a', '5'] if vorbis else ['-c:a', 'pcm_s16le']
            if not vorbis:
                logger.info('Vorbis encoder unavailable; using baseline PCM WAV audio')
            subprocess.run([_ffmpeg_bin(), '-v', 'error', '-y', '-i', str(audio), '-ss', str(audio_offset), *codec, str(ogg)], check=True)
        # Read the exact duration of the packaged audio.
        ffmpeg = Path(_ffmpeg_bin())
        probe = str(ffmpeg.with_name('ffprobe.exe' if ffmpeg.name.lower().endswith('.exe') else 'ffprobe')) if ffmpeg.parent != Path('.') else 'ffprobe'
        result = subprocess.run([probe, '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nw=1:nk=1', str(ogg)], capture_output=True, text=True, check=True)
        duration = float(result.stdout.strip())
        arrangements = []
        for index, track in playable:
            tuning = track['tuning']
            offsets = [int(a - b) for a, b in zip(reversed(tuning), STANDARD[len(tuning)])]
            name = track.get('name') or f'Track {index + 1}'
            events = []
            for bar, written_bar in enumerate(order):
                if written_bar >= len(track.get('measures', [])):
                    continue
                measure = track['measures'][written_bar]
                span = starts[bar + 1] - starts[bar]
                # Use the time signature as the denominator for each beat's position.
                ts = signatures[bar]
                if isinstance(ts, str):
                    ts = [int(v) for v in ts.split('/')]
                if not isinstance(ts, (list, tuple)) or len(ts) != 2 or not ts[0] or not ts[1]:
                    ts = [4, 4]
                bar_length = ts[0] / ts[1]
                for voice in measure.get('voices', []):
                    pos = 0.0
                    for beat in voice.get('beats', []):
                        length = _length(beat)
                        when = starts[bar] + span * pos / bar_length
                        for note in beat.get('notes', []):
                            string, fret = note.get('string'), note.get('fret')
                            if not isinstance(string, int) or not isinstance(fret, int) or not 0 <= string < len(tuning):
                                continue
                            n = {'t': round(when, 6), 's': len(tuning) - string - 1, 'f': fret,
                                 'sus': round(span * length / bar_length, 6)}
                            events.append((n, note, beat))
                        pos += length
            notes = apply_techniques(events)
            logger.info('%s: %s attacks, %s tied segments merged', name, len(notes), len(events) - len(notes))
            anchors = [{'time': 0.0, 'fret': 1, 'width': 4}]
            for when, simultaneous in groupby(notes, key=lambda n: n['t']):
                frets = [n['f'] for n in simultaneous if n['f'] > 0]
                if not frets:
                    continue
                low, high = min(frets), max(frets)
                current = anchors[-1]
                if low < current['fret'] or high >= current['fret'] + current['width']:
                    anchor = {'time': when, 'fret': low, 'width': max(4, high - low + 1)}
                    if when == anchors[-1]['time']:
                        anchors[-1] = anchor
                    else:
                        anchors.append(anchor)
            ident = f'track-{index + 1}'
            file = f'arrangements/{ident}.json'
            arrangement = {'name': name, 'tuning': offsets, 'capo': int(track.get('capo') or 0), 'notes': notes, 'chords': [], 'anchors': anchors, 'handshapes': [], 'templates': []}
            (root / file).write_text(json.dumps(arrangement, ensure_ascii=False, indent=2), encoding='utf-8')
            arrangements.append({'id': ident, 'name': name, 'file': file, 'tuning': offsets, 'capo': arrangement['capo'], 'type': 'bass' if len(tuning) <= 5 else 'guitar'})
        timeline = {'version': 1, 'tempos': [], 'time_signatures': [], 'beats': [], 'sections': []}
        for bar, ts in enumerate(signatures):
            start, end = starts[bar:bar + 2]
            timeline['tempos'].append({'time': start, 'bpm': 60 * ts[0] * 4 / ts[1] / (end - start)})
            if bar == 0 or ts != signatures[bar - 1]:
                timeline['time_signatures'].append({'time': start, 'ts': ts})
            for beat in range(ts[0]):
                timeline['beats'].append({'time': start + (end - start) * beat / ts[0], 'measure': bar + 1 if beat == 0 else -1})
            marker = master['measures'][order[bar]].get('marker')
            if marker:
                timeline['sections'].append({'time': start, 'name': marker.get('text', '') if isinstance(marker, dict) else str(marker)})
        (root / 'song_timeline.json').write_text(json.dumps(timeline, indent=2), encoding='utf-8')
        manifest = {'feedpak_version': '1.19.0', 'title': meta.get('title') or 'Unknown', 'artist': meta.get('artist') or 'Unknown', 'duration': duration, 'song_timeline': 'song_timeline.json', 'arrangements': arrangements, 'stems': [{'id': 'full', 'file': stem_file, 'default': True}]}
        # JSON is valid YAML 1.2 and avoids a new runtime dependency.
        (root / 'manifest.yaml').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        with zipfile.ZipFile(output, 'x', zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(root.rglob('*')):
                if path.is_file(): archive.write(path, path.relative_to(root).as_posix())
    logger.info('Saved %s', output)
    return output
