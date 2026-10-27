"""Measure fresh offline CLI Runs and independent status processes without paid calls."""
import argparse
import json
import os
import statistics
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--samples', type=int, default=3)
    args = parser.parse_args()
    if args.samples < 1:
        parser.error('samples must be positive')
    rows = []
    env = {**os.environ, 'RUN_LIVE_LLM_TESTS': '0', 'PYTHONDONTWRITEBYTECODE': '1'}
    for _ in range(args.samples):
        started = time.perf_counter()
        run = subprocess.run([sys.executable, '-B', '-m', 'lqcd_agent', 'start', '--key', 'measure'],
            env=env, capture_output=True, text=True, check=True, timeout=450)
        start_seconds = time.perf_counter()-started
        result = json.loads(run.stdout)
        started = time.perf_counter()
        status = subprocess.run([sys.executable, '-B', '-m', 'lqcd_agent', 'status', '--host', result['host'],
            '--case', result['run_locator']['case_id'], '--run', result['run_locator']['run_id']],
            env=env, capture_output=True, text=True, check=True, timeout=60)
        status_seconds = time.perf_counter()-started
        if json.loads(status.stdout) != result or result['run_status'] != 'completed':
            raise RuntimeError('Measured Run did not complete consistently')
        rows.append({'host':result['host'], 'start_seconds':start_seconds, 'status_seconds':status_seconds})
    from lqcd_agent.control.pause import runtime_fingerprint
    summary = {key: {'median':statistics.median(row[key] for row in rows), 'max':max(row[key] for row in rows)}
               for key in ('start_seconds','status_seconds')}
    print(json.dumps({'samples':rows,'summary':summary,'fingerprint':runtime_fingerprint(),
        'live_api_called':False,'note':'Fresh Hosts are retained; local timings include durability checks and process startup.'},indent=2))


if __name__ == '__main__':
    main()
