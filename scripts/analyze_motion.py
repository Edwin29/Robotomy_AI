"""Offline engineering verification; OpenCV is never called by the player or live producer."""
import argparse
import json
from datetime import datetime
from pathlib import Path
import statistics

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / '.robotomy/live/verification/motion'


def dist(values):
    values = sorted(float(v) for v in values)
    return {} if not values else {'n': len(values), 'p50': round(statistics.median(values), 4),
                                 'p95': round(values[min(len(values)-1, int(len(values)*.95))], 4),
                                 'max': round(values[-1], 4)}


def point(track):
    return np.array([track['position']['x'], track['position']['y']], np.float32)


def analyze(label):
    data = json.loads((FOLDER / (label + '.json')).read_text(encoding='utf-8'))
    records, frames = data['samples'], data['frames']
    accepted = [s for s in records if s['console']['motion']['tracks']]
    costs = [m['motion_ms'] for m in data['metrics']]
    tracks = [t for s in records for t in s['console']['motion']['tracks']]
    tracked = [t for t in tracks if t['state'] == 'tracking']
    numeric_error, pixel_checks, skipped = [], [], 0
    previous = {}
    for sample in records:
        current = {t['track_id']: t for t in sample['console']['motion']['tracks']}
        for identity, t in current.items():
            if identity in previous and t['state'] == 'tracking':
                old, seq = previous[identity]
                if sample['sequence'] != seq+1:
                    continue
                delta = (point(t) - point(old)) / (t['interval_ms']/1000)
                reported = np.array([t['screen_velocity']['x'], t['screen_velocity']['y']])
                numeric_error.append(float(np.linalg.norm(delta-reported)))
        previous = {k: (v, sample['sequence']) for k, v in current.items()}
    for first, second in zip(frames, frames[1:]):
        a, b = first['snapshot'], second['snapshot']
        if a['scene'] != b['scene'] or a['console']['session'] != b['console']['session']:
            continue
        aa = {t['track_id']: t for t in a['console']['motion']['tracks']}
        bb = {t['track_id']: t for t in b['console']['motion']['tracks']}
        im1 = cv2.imread(str(FOLDER / first['file']), cv2.IMREAD_GRAYSCALE)
        im2 = cv2.imread(str(FOLDER / second['file']), cv2.IMREAD_GRAYSCALE)
        for identity in aa.keys() & bb.keys():
            p, q = point(aa[identity]), point(bb[identity])
            mask = np.zeros_like(im1)
            x, y = map(int, p)
            mask[max(0,y-10):y+11, max(0,x-10):x+11] = 255
            features = cv2.goodFeaturesToTrack(im1, 12, .03, 2, mask=mask)
            if features is None:
                skipped += 1
                continue
            found, status, _ = cv2.calcOpticalFlowPyrLK(im1, im2, features, None, winSize=(15,15), maxLevel=3)
            back, reverse, _ = cv2.calcOpticalFlowPyrLK(im2, im1, found, None, winSize=(15,15), maxLevel=3)
            good = ((status[:,0] == 1) & (reverse[:,0] == 1)
                    & (np.linalg.norm(back[:,0]-features[:,0], axis=1) < .75))
            if np.count_nonzero(good) < 2:
                skipped += 1
                continue
            delta = np.median(found[good,0]-features[good,0], axis=0)
            error = float(np.linalg.norm(delta-(q-p)))
            seconds = (datetime.fromisoformat(b['captured_at_utc'].replace('Z','+00:00')) -
                       datetime.fromisoformat(a['captured_at_utc'].replace('Z','+00:00'))).total_seconds()
            pixel_checks.append({'from': first['file'], 'to': second['file'], 'track': identity,
                                 'predicted_px': (q-p).tolist(), 'image_px': delta.tolist(),
                                 'error_px': error, 'average_velocity_error_px_s': error/seconds,
                                 'image_features': int(np.count_nonzero(good))})
    return {'label': label, 'snapshots': len(records), 'snapshots_with_tracks': len(accepted),
            'tracks_per_snapshot': dist(len(s['console']['motion']['tracks']) for s in records),
            'sample_interval_ms': dist(t['interval_ms'] for t in tracked),
            'velocity_magnitude_px_s': {
                name: dist(np.hypot(t[name]['x'], t[name]['y']) for t in tracked)
                for name in ('screen_velocity', 'object_velocity', 'camera_velocity')},
            'track_states': {k: sum(t['state']==k for t in tracks) for k in ('acquiring','tracking','discontinuity')},
            'motion_ms': dist(costs), 'ui_ms': dist(m['ui_ms'] for m in data['metrics']),
            'png_ms': dist(m['capture_ms'] for m in data['metrics'] if m['capture_ms']>0),
            'numeric_velocity_rounding_error_px_s': dist(numeric_error),
            'image_displacement_error_px': dist(c['error_px'] for c in pixel_checks),
            'image_average_velocity_error_px_s': dist(c['average_velocity_error_px_s'] for c in pixel_checks),
            'moving_image_displacement_error_px': dist(c['error_px'] for c in pixel_checks
                                                      if np.linalg.norm(c['predicted_px']) >= 1),
            'pixel_checks_skipped': skipped, 'pixel_checks': pixel_checks,
            'failures': data['failures'],
            'boundary': 'Offline local pixel-feature correspondence, not labeled ground truth or all-object recall; numeric identity is separate from visual evidence.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('labels', nargs='+')
    args = parser.parse_args()
    result = [analyze(label) for label in args.labels]
    (FOLDER / 'analysis.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps([{k:v for k,v in r.items() if k!='pixel_checks'} for r in result], indent=2))
