"""Summarize what the console actually offered to the player in recorded attempts.

Engineering analysis only: reads the experience ledger JSONL, never the game.
Usage: python scripts/analyze_player_perception.py [--logs DIR] [--days 4-8]
"""
import argparse
import collections
import datetime as dt
import glob
import json
import os
import statistics


def events(path):
    with open(path, encoding='utf-8') as handle:
        for line in handle:
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def when(text):
    text = text.replace('Z', '')
    base, _, rest = text.partition('+')
    if '.' in base:
        head, frac = base.split('.')
        base = head + '.' + frac[:6]
    return dt.datetime.fromisoformat(base).replace(tzinfo=dt.timezone.utc)


def quantile(values, q):
    values = sorted(values)
    return round(values[min(len(values) - 1, int(len(values) * q))], 2) if values else None


def attempt_files(logs, first, last):
    for path in sorted(glob.glob(os.path.join(logs, 'Day-*-Attempt-??.jsonl'))):
        day = int(os.path.basename(path)[4:6])
        if first <= day <= last:
            yield path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--logs', default='vault/Lobotomy-Experience/Playthroughs/Run-001/Logs')
    parser.add_argument('--days', default='1-8')
    args = parser.parse_args()
    first, last = (int(x) for x in args.days.split('-'))

    kinds = collections.Counter()
    image_age, structured_age, view_to_decision = [], [], []
    main_views = empty_main = gauges = tracks = 0
    motion_status = collections.Counter()
    panels = collections.Counter()
    command_views = command_hp = 0
    audio_seen, audio_category, audio_ids = set(), collections.Counter(), collections.defaultdict(set)
    views_with_audio = 0
    obs_with_audio = 0

    for path in attempt_files(args.logs, first, last):
        last_image = last_structured = None
        views = {}
        for event in events(path):
            kind = event.get('kind')
            kinds[kind] += 1
            data = event.get('data', {})
            at = when(event['at']) if 'at' in event else None
            if kind in ('frame_offered', 'hover_frame_offered'):
                last_image = at
            if kind == 'observation_offered':
                last_structured = at
                if (data.get('audio_delivery') or {}).get('events'):
                    obs_with_audio += 1
            if kind == 'control_view_offered':
                last_structured = at
                response = data.get('response', {})
                snapshot = response.get('snapshot', {})
                view_id = os.path.basename(response.get('frame_path', '')).rsplit('.', 1)[0]
                views[view_id] = snapshot.get('captured_at_utc')
                console = snapshot.get('console') or {}
                audio = console.get('audio_events') or []
                if audio:
                    views_with_audio += 1
                session = console.get('session')
                for item in audio:
                    # event_id restarts with each producer session.
                    key = (session, item.get('event_id'))
                    if key in audio_seen:
                        continue
                    audio_seen.add(key)
                    if item.get('category'):
                        audio_category[item['category']] += 1
                        audio_ids[item['category']].add(item.get('sound_id'))
                if snapshot.get('scene') != 'Main':
                    continue
                main_views += 1
                texts = snapshot.get('ui_texts') or []
                empty_main += not texts
                for text in texts:
                    panels[text.get('panel')] += 1
                command = [t for t in texts if t.get('panel') == 'command']
                if command:
                    command_views += 1
                    command_hp += any(t.get('role') == 'hp' for t in command)
                gauges += len(console.get('gauges') or [])
                motion = console.get('motion') or {}
                motion_status[motion.get('status')] += 1
                tracks += len(motion.get('tracks') or [])
            if kind == 'control_decision':
                decision = data.get('decision', {})
                decided = when(data['at'])
                if last_image:
                    image_age.append((decided - last_image).total_seconds())
                if last_structured:
                    structured_age.append((decided - last_structured).total_seconds())
                captured = views.get(decision.get('view_id'))
                if captured:
                    view_to_decision.append((decided - when(captured)).total_seconds())

    report = {
        'days': args.days,
        'event_counts': {k: kinds[k] for k in (
            'control_decision', 'control_view_offered', 'frame_offered', 'hover_frame_offered',
            'observation_offered', 'audio_events_offered', 'history_offered', 'input_sequence_submitted')},
        'seconds_since_last_image_at_decision': {
            'n': len(image_age), 'median': quantile(image_age, .5), 'p90': quantile(image_age, .9),
            'share_over_10s': round(sum(a > 10 for a in image_age) / len(image_age), 2) if image_age else None},
        'seconds_since_last_structured_at_decision': {
            'n': len(structured_age), 'median': quantile(structured_age, .5), 'p90': quantile(structured_age, .9)},
        'view_capture_to_decision_seconds_median': quantile(view_to_decision, .5),
        'main_control_views': main_views, 'main_views_without_text': empty_main,
        'main_text_by_panel': dict(panels.most_common()),
        'main_views_with_command_text': command_views, 'of_which_with_hp': command_hp,
        'main_gauges_total': gauges, 'main_motion_tracks_total': tracks,
        'main_motion_status': dict(motion_status),
        'control_views_carrying_audio': views_with_audio, 'observations_carrying_audio': obs_with_audio,
        'unique_audio_events': len(audio_seen),
        'audio_category_starts_and_distinct_sounds': {k: [v, len(audio_ids[k])] for k, v in audio_category.items()},
    }
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
