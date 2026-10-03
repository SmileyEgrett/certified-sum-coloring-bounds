#!/usr/bin/env python3
"""Recheck all reference lower bounds against the authenticated DIMACS graphs."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from run import resources, need, hashes, save, canonical, digest_file


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--graphs', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    limits = resources()
    package = Path(__file__).resolve().parent
    out = a.out.resolve()
    need(not out.is_relative_to(package), 'put verification output outside the software directory')
    out.mkdir(parents=True, exist_ok=False)
    source = out / 'source_snapshot'
    shutil.copytree(package / 'source', source)
    shutil.copyfile(__file__, out / 'verify_reference.py')
    cfg = json.loads((source / 'config/STAGES.json').read_text())
    for g in cfg['graphs'].values():
        src = a.graphs / Path(g['run_input']).name
        need(digest_file(src) == g['sha256'], 'graph hash mismatch: ' + src.name)
        dest = source / g['run_input']
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
    files = hashes(source)
    save(out / 'manifest.json', {'files': files, 'snapshot_id': hashlib.sha256(canonical(files)).hexdigest()})
    ref = out / 'reference'
    shutil.copytree(package / 'reference', ref)
    expected = {}
    for line in (ref / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ', 1)
        rel = Path(name)
        need(not rel.is_absolute() and '..' not in rel.parts and name not in expected, 'bad reference manifest')
        expected[name] = digest
    actual = hashes(ref)
    actual.pop('SHA256SUMS')
    need(actual == expected, 'reference manifest mismatch')
    sys.path.insert(0, str(source / 'new'))
    import core
    import verify_lower
    core.guard_snapshot()
    index = core.readj(ref / 'index.json')
    need(index['schema'] == 'conditioned_reference_v1', 'unsupported reference index')
    records = index['stages']
    for r in records.values():
        for entry in r['artifacts'].values():
            rel = Path(entry['path'])
            need(not rel.is_absolute() and '..' not in rel.parts, 'unsafe artifact path')
            path = (ref / rel).resolve(strict=True)
            need(path.is_relative_to(ref), 'artifact outside reference tree')
            entry['path'] = str(path)
    verified = {}
    for case, fn in [('dsjc250', verify_lower.verify250), ('dsjc500', verify_lower.verify500),
                     ('dsjc1000', verify_lower.verify1000)]:
        resources()
        core.guard_snapshot()
        dest = out / case
        dest.mkdir()
        receipt = fn({k: r for k, r in records.items() if k.startswith(case + '.')}, dest)
        need(receipt['status'] == 'verified' and not receipt.get('invalid_available_certificates'),
             'reference verification incomplete')
        need(receipt['lower_bound'] == cfg['targets'][case], 'incorrect reference conclusion')
        save(dest / 'verification.json', receipt)
        verified[case] = receipt['lower_bound']
        print(case, receipt['lower_bound'], flush=True)
    dest = out / 'c2000'
    dest.mkdir()
    binary = dest / 'census'
    subprocess.run(['g++', '-std=c++20', '-O2', str(source / 'checkers/c2000/census_stable_sets.cpp'),
                    '-o', str(binary)], check=True)
    with (dest / 'census.stdout').open('xb') as stdout, (dest / 'census.stderr').open('xb') as stderr:
        subprocess.run([str(binary), str(core.graph('c2000')), '7', str(dest / 'sets6.tsv')],
                       stdout=stdout, stderr=stderr, check=True)
    records['c2000.independent_census'] = {'artifacts': {
        'six_sets': {'path': str(dest / 'sets6.tsv')}, 'census_stdout': {'path': str(dest / 'census.stdout')}}}
    binding = verify_lower.verify_census2000(records)
    save(dest / 'binding.json', binding)
    records['c2000.bind_census'] = {'artifacts': {'receipt': {'path': str(dest / 'binding.json')}}}
    receipt = verify_lower.verify2000(records, dest)
    need(receipt['lower_bound'] == cfg['targets']['c2000'], 'incorrect C2000 reference conclusion')
    save(dest / 'verification.json', receipt)
    verified['c2000'] = receipt['lower_bound']
    core.guard_snapshot()
    save(out / 'VERIFIED.json', {'verified_lower_bounds': verified, 'resources': limits,
                                'source_snapshot_id': core.guard_snapshot()['snapshot_id'],
                                'reference_manifest_sha256': digest_file(ref / 'SHA256SUMS')})
    print(json.dumps(verified, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
