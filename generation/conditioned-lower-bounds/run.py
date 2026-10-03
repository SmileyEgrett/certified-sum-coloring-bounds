#!/usr/bin/env python3
"""Generate conditioned lower-bound certificates from authenticated graphs.

This entry point freezes its source and inputs before starting a serial run.
Numerical output becomes a lower bound only after the exact verification stage.
"""
import argparse
import datetime
import fcntl
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import time


def need(ok, message):
    if not ok:
        raise ValueError(message)


def digest_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def hashes(root):
    result = {}
    for p in sorted(root.rglob('*')):
        need(not p.is_symlink(), 'symlink in source/input tree')
        if p.is_file():
            result[p.relative_to(root).as_posix()] = digest_file(p)
    return result


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def save(path, value):
    with path.open('xb') as f:
        f.write(canonical(value))
        f.flush()
        os.fsync(f.fileno())


def resources():
    need(sys.flags.optimize == 0 and 'PYTHONOPTIMIZE' not in os.environ,
         'run with Python assertions enabled')
    need(len(os.sched_getaffinity(0)) == 1, 'use launch.sh with one selected CPU')
    rows = Path('/proc/self/cgroup').read_text().splitlines()
    cg = next((Path('/sys/fs/cgroup') / r[3:].lstrip('/') for r in rows if r.startswith('0::')), None)
    need(cg is not None, 'a cgroup v2 memory limit is required; use launch.sh')
    memory = (cg / 'memory.max').read_text().strip()
    swap = (cg / 'memory.swap.max').read_text().strip()
    need(memory.isdigit() and 0 < int(memory) <= 4294967296 and swap == '0',
         'use an aggregate memory limit of at most 4 GiB and no swap')
    return {'affinity': sorted(os.sched_getaffinity(0)), 'memory_max_bytes': int(memory),
            'swap_max_bytes': int(swap), 'cgroup': cg.as_posix()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--graphs', type=Path, help='directory containing the four DIMACS .col files')
    parser.add_argument('--out', type=Path, help='new run directory, or an existing run with --resume')
    parser.add_argument('--case', choices=('all', 'dsjc250', 'dsjc500', 'dsjc1000', 'c2000'), default='all')
    parser.add_argument('--stage', help='run one named stage and its full dependency closure')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--list', action='store_true', help='list stages without computation')
    args = parser.parse_args()
    package = Path(__file__).resolve().parent
    source = package / 'source'
    cfg = json.loads((source / 'config/STAGES.json').read_text())
    if args.list:
        for s in cfg['stages']:
            print(s['id'], s['category'], '; dependencies:', ', '.join(s['depends_on']))
        return
    need(args.out is not None, '--out is required')
    limits = resources()
    for key, value in cfg['environment'].items():
        need(os.environ.get(key) == value, 'use launch.sh: missing environment setting ' + key)
    run = args.out.resolve()
    need(not run.is_relative_to(package), 'put run outputs outside the software directory')
    stages = {s['id']: s for s in cfg['stages']}
    requested = [args.stage] if args.stage else [c + '.verify' for c in cfg['order']
                                                 if args.case in ('all', c)]
    selected_ids = set()
    def include(sid):
        need(sid in stages, 'unknown stage ' + sid)
        if sid in selected_ids:
            return
        selected_ids.add(sid)
        for dep in stages[sid]['depends_on']:
            include(dep)
    for sid in requested:
        include(sid)
    if args.resume:
        need((run / 'manifest.json').is_file(), 'no frozen run to resume')
        need(hashes(source) == json.loads((run / 'package-source.json').read_text()),
             'package source changed: start a new run')
        need(digest_file(__file__) == (run / 'entrypoint.sha256').read_text().strip(),
             'entry point changed: start a new run')
        env = json.loads((run / 'environment.json').read_text())
        need(env['executable_sha256'] == digest_file(sys.executable) and env['python'] == sys.version,
             'Python environment changed: start a new run')
        need(env['versions'] == {n: importlib.metadata.version(n) for n in ('numpy', 'scipy', 'networkx')},
             'numerical library versions changed: start a new run')
    else:
        need(args.graphs is not None, '--graphs is required for a new run')
        run.mkdir(parents=True, exist_ok=False)
        snapshot = run / 'source_snapshot'
        shutil.copytree(source, snapshot)
        save(run / 'package-source.json', hashes(source))
        (run / 'entrypoint.sha256').write_text(digest_file(__file__) + '\n')
        shutil.copyfile(__file__, run / 'run.py')
        for g in cfg['graphs'].values():
            src = args.graphs / Path(g['run_input']).name
            need(digest_file(src) == g['sha256'], 'graph hash mismatch: ' + src.name)
            dest = snapshot / g['run_input']
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest)
        files = hashes(snapshot)
        save(run / 'manifest.json', {'files': files,
             'snapshot_id': hashlib.sha256(canonical(files)).hexdigest()})
        save(run / 'environment.json', {'python': sys.version, 'executable': sys.executable,
             'executable_sha256': digest_file(sys.executable),
             'versions': {n: importlib.metadata.version(n) for n in ('numpy', 'scipy', 'networkx')},
             'resources': limits, 'environment': cfg['environment']})
    snapshot = run / 'source_snapshot'
    sys.path.insert(0, str(snapshot / 'new'))
    import core
    from stage_io import outputs, sealed
    manifest = core.guard_snapshot()
    config_hash = core.sha(snapshot / 'config/STAGES.json')
    with (run / 'run.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        selected = {}
        for stage in cfg['stages']:
            sid = stage['id']
            if sid not in selected_ids:
                continue
            core.guard_snapshot()
            old = sorted((run / 'jobs' / sid).glob('attempt-*/record.json'))
            successful = [p for p in old if core.readj(p)['status'] == 'success']
            if successful:
                p = successful[-1]
                r = core.validate_record(run, p, manifest['snapshot_id'], config_hash)
                selected[sid] = (p, r)
                print('REUSE', sid, flush=True)
                continue
            resources()
            need(all(dep in selected for dep in stage['depends_on']), 'missing stage dependency')
            attempts = list((run / 'jobs' / sid).glob('attempt-*'))
            attempt = 'attempt-' + str(max([int(p.name[8:]) for p in attempts] + [0]) + 1).zfill(3)
            job = run / 'jobs' / sid / attempt
            out = job / 'out'
            out.mkdir(parents=True, exist_ok=False)
            inp = job / 'inputs.json'
            core.writej(inp, sealed(stage, selected, {}, manifest['snapshot_id'], config_hash))
            argv = [core.expand(v, run, out, {k: v[1] for k, v in selected.items()}, inp)
                    for v in stage['argv']]
            jobid = core.digest(core.canonical([manifest['snapshot_id'], config_hash,
                                               sid, attempt, core.sha(inp)]))
            start = time.monotonic()
            before = resource.getrusage(resource.RUSAGE_CHILDREN)
            record = {'schema': 'attempt_v2', 'stage': sid, 'attempt': attempt,
                      'snapshot_id': manifest['snapshot_id'], 'config_hash': config_hash,
                      'job_id': jobid, 'inputs_sha256': core.sha(inp), 'argv': argv,
                      'case': stage['case'], 'category': stage['category'],
                      'started': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                      'resources': limits, 'status': 'running'}
            core.writej(job / 'start.json', record)
            print('START', sid, flush=True)
            try:
                with (job / 'stdout.log').open('xb') as stdout, (job / 'stderr.log').open('xb') as stderr:
                    p = subprocess.run(argv, cwd=snapshot, stdout=stdout, stderr=stderr, check=False)
                record['exit_code'] = p.returncode
                need(p.returncode == 0, 'stage failed; inspect ' + str(job / 'stderr.log'))
                core.guard_snapshot()
                record['artifacts'] = outputs(stage, run, out, {k: v[1] for k, v in selected.items()}, inp)
                if 'receipt' in record['artifacts']:
                    receipt = core.readj(record['artifacts']['receipt']['path'])
                    need(not receipt.get('invalid_available_certificates'), 'invalid supplied certificate')
                record['status'] = 'success'
            except BaseException as exc:
                record['status'] = 'failed'
                record['error'] = str(exc)
                raise
            finally:
                after = resource.getrusage(resource.RUSAGE_CHILDREN)
                record.update(inclusive_wall_seconds=time.monotonic() - start,
                              child_user_seconds=after.ru_utime - before.ru_utime,
                              child_system_seconds=after.ru_stime - before.ru_stime,
                              finished=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                              logs={n: core.sha(job / n) for n in ('stdout.log', 'stderr.log') if (job / n).exists()})
                core.writej(job / 'record.json', record)
            selected[sid] = (job / 'record.json', record)
            print('DONE', sid, record['inclusive_wall_seconds'], flush=True)
        claims = {}
        for case in cfg['order']:
            sid = case + '.verify'
            if sid in selected:
                p, r = selected[sid]
                core.validate_record(run, p, manifest['snapshot_id'], config_hash)
                receipt = core.readj(r['artifacts']['receipt']['path'])
                need(receipt['lower_bound'] == cfg['targets'][case], 'unexpected lower-bound conclusion')
                claims[case] = receipt['lower_bound']
        final = run / ('results-' + str(time.time_ns()) + '.json')
        core.writej(final, {'snapshot_id': manifest['snapshot_id'], 'requested_stages': requested,
                           'completed_stages': sorted(selected), 'verified_lower_bounds': claims})
        print('RESULT', final, json.dumps(claims), flush=True)


if __name__ == '__main__':
    main()
