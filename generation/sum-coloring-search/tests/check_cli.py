#!/usr/bin/env python3
"""Bounded interface checks; invoked explicitly by CTest, never during build."""
from pathlib import Path
import subprocess
import sys
import tempfile

exe = str(Path(sys.argv[1]).resolve())
with tempfile.TemporaryDirectory(prefix='sum-coloring-tests-') as folder:
    root = Path(folder)
    graph = root / 'path.col'
    graph.write_text('p edge 5 4\ne 1 2\ne 2 3\ne 3 4\ne 4 5\n')
    start = root / 'start.coloring'
    start.write_text('1 1\n2 2\n3 1\n4 2\n5 1\n')
    def invoke(args, success=True):
        p = subprocess.run([exe, *map(str, args)], capture_output=True, text=True, timeout=10)
        if (p.returncode == 0) != success:
            raise RuntimeError(f'Unexpected exit {p.returncode}: {p.stdout}\n{p.stderr}')
        return p.stdout
    common = ['--graph', graph, '--initial-coloring', start, '--sweeps', 4,
              '--size-factor', 2, '--threads', 1, '--replicas', 3, '--verify', 1,
              '--temperature', 1, '--gamma', 0.7, '--seed', 781]
    checked = 0
    for plain in (0, 1):
        for trigger in (None, 'collapse', 'empty', 'stagnation'):
            extra = [] if trigger is None else ['--runway-slots', 2, '--kick-operator', 'runway',
                                                '--kick-' + trigger, 1, '--kick-max-size', 2]
            records = []
            for backend in ('scalar', 'bitset'):
                out = root / f'{plain}-{trigger}-{backend}.coloring'
                stdout = invoke(common + ['--plain-sa', plain, '--legal-repair', backend,
                                           '--save-best', out, *extra])
                records.append(([l for l in out.read_text().splitlines() if not l.startswith('c')],
                                [l for l in stdout.splitlines() if not l.startswith(('run_start ', 'wall_seconds='))]))
                colors = dict(map(int, l.split()) for l in out.read_text().splitlines() if not l.startswith('c'))
                assert set(colors) == set(range(1, 6))
                assert all(colors[u] != colors[u + 1] for u in range(1, 5))
                assert sum(colors.values()) == 7
                checked += 1
            assert records[0] == records[1], 'scalar/bitset trajectories differ'
    for values in (['--sweeps', 0], ['--sweeps', -1], ['--sweeps', '9223372036854775808'],
                   ['--temperature', 'nan'], ['--threads', 0], ['--plain-sa', 2],
                   ['--kick-operator', 'runway']):
        invoke(common + ['--save-best', root / 'bad.coloring', *values], False)
    for content in ('1 1\n', '1 1\n1 2\n2 2\n3 1\n4 2\n5 1\n',
                    '1 1\n2 1\n3 1\n4 2\n5 1\n'):
        bad = root / 'bad-start.coloring'; bad.write_text(content)
        invoke(common + ['--save-best', root / 'bad.coloring', '--initial-coloring', bad], False)
    for content in ('p edge 2 1\n', 'p edge 2 2\ne 1 2\ne 2 1\n', 'p edge 2 1\ne 1 1\n'):
        bad = root / 'bad.col'; bad.write_text(content)
        invoke(common + ['--save-best', root / 'bad.coloring', '--graph', bad], False)
    invoke(common + ['--save-best', start], False)
    incidence_graph = root / 'incidences.col'
    incidence_graph.write_text('p edge 5 8\ne 1 2\ne 2 3\ne 3 4\ne 4 5\n')
    invoke(common + ['--graph', incidence_graph, '--save-best', root / 'incidence-rejected.coloring'], False)
    invoke(common + ['--graph', incidence_graph, '--edge-count', 'incidences', '--save-best', root / 'incidence-ok.coloring'])
    invoke(common + ['--edge-count', 'incidences', '--save-best', root / 'wrong-incidence.coloring'], False)
    invoke(common + ['--edge-count', 'guess', '--save-best', root / 'unknown-convention.coloring'], False)
    print(f'bounded_runs={checked}; invalid-input and output-preservation checks passed')
