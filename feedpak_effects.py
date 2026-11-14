"""Playback order and fretted-note technique conversion."""
import logging

log = logging.getLogger('feedpak')


def playback_order(measures):
    """Flatten repeat sections, nested repeats, and ending bitmasks."""
    order, stack = [], []
    index, last_pass, steps = 0, 1, 0
    while index < len(measures):
        steps += 1
        if steps > max(10000, len(measures) * 100):
            raise ValueError('Repeat structure exceeds the playback safety limit.')
        bar = measures[index]
        if bar.get('repeatStart') and (not stack or stack[-1]['start'] != index):
            stack.append({'start': index, 'pass': 1})
        ending = bar.get('alternateEnding', 0) or 0
        turn = stack[-1]['pass'] if stack else last_pass
        if not ending or ending & (1 << (turn - 1)):
            order.append(index)
        count = bar.get('repeat', bar.get('repeatCount', 0)) or 0
        if isinstance(count, bool):
            count = 2 if count else 0
        if count >= 2:
            if not stack:
                stack.append({'start': 0, 'pass': 1})
            frame = stack[-1]
            if frame['pass'] < count:
                frame['pass'] += 1
                index = frame['start']
                continue
            last_pass = frame['pass']
            stack.pop()
        elif not ending and not stack:
            last_pass = 1
        index += 1
    return order


def apply_techniques(events):
    """Merge ties and translate source effects; events are (output, source, beat)."""
    events.sort(key=lambda e: (e[0]['t'], e[0]['s']))
    notes, previous, slides, rings = [], {}, [], []
    for n, source, beat in events:
        prev = previous.get(n['s'])
        if source.get('tie'):
            if prev and prev['f'] == n['f']:
                old_end = prev['t'] + prev['sus']
                if abs(n['t'] - old_end) < 0.002:
                    if source.get('bend', {}).get('points'):
                        curve = prev.setdefault('bnv', [{'t': 0, 'v': prev.get('bn', 0)}])
                        for p in source['bend']['points']:
                            curve.append({'t': round(n['t'] - prev['t'] + n['sus'] * p.get('position', 0) / 60, 6), 'v': p.get('tone', 0) / 50})
                        prev['bn'] = max(p['v'] for p in curve)
                    prev['sus'] = round(n['t'] + n['sus'] - prev['t'], 6)
                    continue
            log.warning('Unmatched tie at %.6fs on string %s', n['t'], n['s'])
        if source.get('hp') and prev:
            if n['f'] > prev['f']: n['ho'] = True
            elif n['f'] < prev['f']: n['po'] = True
        for out, keys in {'mt': ('dead',), 'pm': ('palmMute',), 'vb': ('vibrato', 'wideVibrato', 'leftHandVibrato'), 'ac': ('accentuated',), 'tp': ('tapping',), 'tr': ('tremoloPicking',), 'slp': ('slap',), 'plk': ('pop',)}.items():
            if any(source.get(k) or beat.get(k) for k in keys): n[out] = True
        harmonic = source.get('harmonic')
        if harmonic:
            key = {'natural': 'hm', 'pinch': 'hp', 'tapped': 'tp', 'tap': 'tp'}.get(harmonic)
            if key: n[key] = True
            else: log.warning('Unsupported harmonic %r at %.6fs', harmonic, n['t'])
        stroke = beat.get('stroke') or beat.get('pickStroke')
        if stroke in ('down', 'up'): n['pkd'] = 0 if stroke == 'down' else 1
        points = source.get('bend', {}).get('points', [])
        if points:
            n['bnv'] = [{'t': round(n['sus'] * p.get('position', 0) / 60, 6), 'v': p.get('tone', 0) / 50} for p in sorted(points, key=lambda p: p.get('position', 0))]
            n['bn'] = max(p['v'] for p in n['bnv'])
            first, last = n['bnv'][0]['v'], n['bnv'][-1]['v']
            n['bt'] = (3 if last < first else 2) if first else (4 if last < n['bn'] else 0)
        slide = source.get('slide')
        if slide in ('shift', 'legato', 'toNext', 'belowshift'): slides.append((n, slide))
        elif slide in ('downwards', 'upwards'):
            n['slu'] = max(0, n['f'] - 3) if slide == 'downwards' else n['f'] + 3
            log.info('Unpitched slide endpoint inferred at %.6fs', n['t'])
        elif slide:
            log.info('Slide-in %r at %.6fs has no feedpak equivalent', slide, n['t'])
        if source.get('staccato'): n['sus'] = round(n['sus'] * 0.5, 6)
        if beat.get('letRing'): rings.append(n)
        previous[n['s']] = n
        notes.append(n)
    for n, kind in slides:
        following = next((x for x in notes if x['s'] == n['s'] and x['t'] > n['t']), None)
        if following:
            n['sl'] = following['f']
            if kind == 'legato': n['ln'] = True
        else: log.warning('Slide has no following note at %.6fs', n['t'])
    for n in rings:
        following = next((x for x in notes if x['s'] == n['s'] and x['t'] > n['t']), None)
        if following: n['sus'] = max(n['sus'], round(following['t'] - n['t'], 6))
    return notes
