"""Automated fuzzing test runner — all samples × all schedules.

Runs every combination, collects coverage/crash data from both the
Result pickle and the persist directory, then writes a structured
summary to _result/FULL_TEST_SUMMARY.txt.
"""

import os
import shutil
import subprocess
import sys
import time
from collections import defaultdict

SAMPLES = [1, 2, 3, 4, 5, 6]
SCHEDULES = ['path', 'prob_weight', 'rare_line', 'size']
RUN_TIME = 10
OUTPUT_DIR = '_result'
PERSIST_DIR = os.path.join(OUTPUT_DIR, 'persist')
CRASH_SNAPSHOT_DIR = os.path.join(OUTPUT_DIR, 'crash_snapshots')

# Ensure we can import project modules
sys.path.insert(0, '.')


def load_pickle(path):
    """Load a pickle file safely, handling the Result class."""
    import pickle
    # Pickle saves Result as __main__.Result; ensure it's visible
    from main import Result
    import __main__
    __main__.Result = Result
    try:
        with open(path, 'rb') as f:
            return pickle.load(f)
    except Exception:
        return None


def run_one(sample, schedule):
    """Run fuzzer for one sample/schedule, return (ok, stdout, stderr).
    After a successful run, snapshot the crash_map so it isn't overwritten
    by the next run."""
    cmd = [
        sys.executable, 'main.py',
        '--sample', str(sample),
        '--run-time', str(RUN_TIME),
        '--schedule', schedule,
        '--quiet',
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True,
                                timeout=RUN_TIME + 25)
        rc = result.returncode
        ok = (rc == 0)
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        # Snapshot crash_map before next run overwrites it
        if ok:
            os.makedirs(CRASH_SNAPSHOT_DIR, exist_ok=True)
            src = os.path.join(PERSIST_DIR, 'crashes', 'crash_map.pkl')
            dst = os.path.join(CRASH_SNAPSHOT_DIR,
                               f'Sample-{sample}-{schedule}_crash_map.pkl')
            if os.path.exists(src):
                shutil.copy2(src, dst)

        return ok, rc, stdout, stderr
    except subprocess.TimeoutExpired:
        return False, -1, '', 'TIMEOUT'
    except Exception as e:
        return False, -1, '', str(e)


def collect_results():
    """Parse all result and persist files into a structured dict."""
    import main
    data = {}
    for sample in SAMPLES:
        for schedule in SCHEDULES:
            key = (sample, schedule)
            pkl_path = os.path.join(OUTPUT_DIR, f'Sample-{sample}-{schedule}.pkl')

            res = load_pickle(pkl_path)
            if res is None:
                data[key] = {'error': 'result file missing'}
                continue

            covered_lines = len(res.covered_line) if hasattr(res, 'covered_line') else 0
            crash_hashes = res.crashes if hasattr(res, 'crashes') else set()
            duration = res.end_time - res.start_time if hasattr(res, 'end_time') else 0

            # Load crash_map from per-run snapshot (not shared persist)
            crash_map_path = os.path.join(
                CRASH_SNAPSHOT_DIR,
                f'Sample-{sample}-{schedule}_crash_map.pkl')
            crash_map = load_pickle(crash_map_path) or {}

            # Group crash inputs by hash
            crashes_by_hash = defaultdict(list)
            for inp, h in crash_map.items():
                crashes_by_hash[h].append(inp)

            data[key] = {
                'covered_lines': covered_lines,
                'unique_crashes': len(crash_hashes),
                'duration': duration,
                'crashes': {
                    h: crashes_by_hash.get(h, []) for h in crash_hashes
                },
            }
    return data


def write_summary(data, filepath):
    """Write organized results to a readable file."""
    lines = []
    sep = '=' * 78
    sep2 = '-' * 78

    lines.append(sep)
    lines.append('  FUZZING TEST RESULTS — FULL SUMMARY')
    lines.append(f'  Generated: {time.strftime("%Y-%m-%d %H:%M:%S")}')
    lines.append(f'  Run time per test: {RUN_TIME}s')
    lines.append(sep)
    lines.append('')

    # ── Overall Summary Table ──
    lines.append('OVERALL SUMMARY TABLE')
    lines.append(sep2)
    header = f"{'Sample':<8} {'Schedule':<13} {'Covered Lines':<16} {'Uniq Crashes':<14} {'Duration':<10}"
    lines.append(header)
    lines.append('-' * 65)

    sample_totals = defaultdict(lambda: {'max_lines': 0, 'max_crashes': 0})
    for (sample, schedule), info in sorted(data.items()):
        if 'error' in info:
            lines.append(f'{sample:<8} {schedule:<13} {"ERROR: " + info["error"]:<16} {"-":<14} {"-":<10}')
            continue
        lines.append(
            f'{sample:<8} {schedule:<13} {info["covered_lines"]:<16} '
            f'{info["unique_crashes"]:<14} {info["duration"]:<10.1f}'
        )
        sample_totals[sample]['max_lines'] = max(sample_totals[sample]['max_lines'], info['covered_lines'])
        sample_totals[sample]['max_crashes'] = max(sample_totals[sample]['max_crashes'], info['unique_crashes'])

    lines.append('')

    # ── Per-Sample Detail ──
    for sample in SAMPLES:
        lines.append(sep)
        lines.append(f'  SAMPLE {sample}')
        lines.append(sep2)
        best_lines = sample_totals[sample]['max_lines']
        best_crashes = sample_totals[sample]['max_crashes']
        lines.append(f'  Best coverage: {best_lines} lines  |  Best crashes: {best_crashes} unique')
        lines.append('')

        for schedule in SCHEDULES:
            key = (sample, schedule)
            info = data.get(key, {})
            lines.append(f'  --- {schedule} ---')

            if 'error' in info:
                lines.append(f'    ERROR: {info["error"]}')
                lines.append('')
                continue

            lines.append(f'    Covered lines : {info["covered_lines"]}')
            lines.append(f'    Unique crashes: {info["unique_crashes"]}')
            lines.append(f'    Duration      : {info["duration"]:.1f}s')

            # Show crash details: hash + up to 3 example inputs
            if info.get('crashes'):
                lines.append(f'    Crash details:')
                for h, inputs in sorted(info['crashes'].items(), key=lambda x: -len(x[1])):
                    short_hash = h[:16]
                    sample_inputs = inputs[:3]
                    lines.append(f'      [{short_hash}...] ({len(inputs)} inputs)')
                    for inp in sample_inputs:
                        # Truncate long inputs for readability
                        display = inp if len(inp) <= 80 else inp[:77] + '...'
                        lines.append(f'        -> {display!r}')
            else:
                lines.append(f'    No crashes found.')
            lines.append('')

    # ── Cross-Sample Analysis ──
    lines.append(sep)
    lines.append('  CROSS-SAMPLE ANALYSIS')
    lines.append(sep2)
    lines.append('')

    # Best schedule per sample
    lines.append('  Best schedule by unique crashes:')
    for sample in SAMPLES:
        best_sched = None
        best_count = -1
        for sched in SCHEDULES:
            info = data.get((sample, sched), {})
            if 'error' not in info and info.get('unique_crashes', 0) > best_count:
                best_count = info['unique_crashes']
                best_sched = sched
        lines.append(f'    Sample {sample}: {best_sched} ({best_count} crashes)')

    lines.append('')
    lines.append('  Coverage comparison across schedules:')
    for sample in SAMPLES:
        covs = []
        for sched in SCHEDULES:
            info = data.get((sample, sched), {})
            covs.append(str(info.get('covered_lines', '?')))
        lines.append(f'    Sample {sample}: path={covs[0]}, prob_weight={covs[1]}, rare_line={covs[2]}')

    lines.append('')
    lines.append(sep)
    lines.append('  END OF REPORT')
    lines.append(sep)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    return '\n'.join(lines)


def main():
    start_time = time.time()
    print(f'Starting {len(SAMPLES) * len(SCHEDULES)} test runs...')
    print(f'Output will be saved to: {os.path.abspath(os.path.join(OUTPUT_DIR, "FULL_TEST_SUMMARY.txt"))}')
    print()

    total = len(SAMPLES) * len(SCHEDULES)
    completed = 0

    for sample in SAMPLES:
        for schedule in SCHEDULES:
            completed += 1
            label = f'[{completed}/{total}] sample={sample} schedule={schedule}'
            print(f'{label} ...', end=' ', flush=True)
            ok, rc, stdout, stderr = run_one(sample, schedule)
            if ok:
                print('OK')
            else:
                print('FAILED')
                # Write full failure output (both streams) to a file
                fail_path = os.path.join(OUTPUT_DIR, 'FAILURE_LOG.txt')
                with open(fail_path, 'w', encoding='utf-8') as f:
                    f.write(f'Failed run: {label}\n')
                    f.write(f'Time: {time.strftime("%Y-%m-%d %H:%M:%S")}\n')
                    f.write(f'Exit code: {rc}\n')
                    f.write(f'{"=" * 60}\n')
                    if stdout:
                        f.write('--- STDOUT ---\n')
                        f.write(stdout)
                        f.write('\n')
                    if stderr:
                        f.write('--- STDERR ---\n')
                        f.write(stderr)
                        f.write('\n')
                print(f'  Full output written to: {os.path.abspath(fail_path)}')
                sys.exit(1)

    elapsed = time.time() - start_time
    print(f'\nAll runs completed in {elapsed:.0f}s (no errors)')

    # Collect results
    print('Collecting results...')
    data = collect_results()

    # Write summary
    out_path = os.path.join(OUTPUT_DIR, 'FULL_TEST_SUMMARY.txt')
    summary = write_summary(data, out_path)
    print(f'\nSummary written to: {os.path.abspath(out_path)}')
    print(f'File size: {os.path.getsize(out_path)} bytes')


if __name__ == '__main__':
    main()