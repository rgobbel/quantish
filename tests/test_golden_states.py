"""Golden-snapshot regression test for the quantish engine.

For each maintained model, the exact final classical states (canonical
(particle, wire, sign) triples -> complex weight) are recorded in
golden_states.json. Any engine change that alters a final weight — including
a phase or sign flip that preserves every probability — shows up as a diff.

This replaces the retired reference-parity suite (which compared against the
external quantish_gld repo): the snapshots were taken from an engine state
whose per-world amplitudes matched the reference implementation exactly, and
whose EPR statistics match the revised chapter's analytical laws.

To re-record after a deliberate behavior change:

    python tests/test_golden_states.py --regen

then review the diff of golden_states.json before committing it.
"""
import json
import logging
import sys
import unittest
from pathlib import Path

import yaml
from addict import Addict

REPO_DIR = Path(__file__).resolve().parents[1]
MODELS_DIR = REPO_DIR / 'models'
GOLDEN_PATH = Path(__file__).parent / 'golden_states.json'

sys.path.insert(0, str(REPO_DIR))

import quantish.qnumber as qn
from quantish.qnumber import CalcMode

WEIGHT_TOLERANCE = 1e-9

GOLDEN_MODELS = [
    'gr2026/fig4.05',
    'gr2026/fig4.07',
    'gr2026/fig4.08',
    'gr2006/fig4.08',
    'gr2026/fig4.09',
    'gr2026/fig4.10',
    'gr2026/fig4.12',
    'extras/fig4.13_full',
    'gr2026/fig4.15',
    'extras/fig4.15x',
    'gr2026/fig4.16',
    'extras/fig4.16x',
    'gr2026/fig4.17',
    'gr2006/fig4.16',
    'extras/zero_control',
]


def run_model(name):
    """Final classical states as {canonical key: complex weight}. The key is
    the sorted (particle, resting wire, sign) triples, serialized for JSON as
    'p1@g7.upper:+1|p2@g8.lower:-1|...'."""
    from quantish.simulation import Simulation
    with open(MODELS_DIR / 'defaults.yaml') as f:
        config = yaml.safe_load(f)
    with open(MODELS_DIR / f'{name}.yaml') as f:
        config.update(yaml.safe_load(f))
    config['loglevel'] = 'warning'
    sim = Simulation(Addict(config))
    result_space, _ = sim.run()
    finals = {}
    for point in result_space.index.values():
        canon = '|'.join(sorted(
            f'{pname}@{coord.position.endpoint}:{int(coord.sign):+d}'
            for pname, coord in point.coords.items()))
        finals[canon] = complex(point.weight)
    return finals


def snapshot(finals):
    return {canon: [w.real, w.imag] for canon, w in sorted(finals.items())}


class TestGoldenStates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        logging.getLogger('quantish').setLevel(logging.WARNING)
        CalcMode.default('Float')
        with open(GOLDEN_PATH) as f:
            cls.golden = json.load(f)

    def test_models_match_golden_states(self):
        self.assertEqual(sorted(self.golden), sorted(GOLDEN_MODELS),
                         'golden_states.json is out of step with GOLDEN_MODELS '
                         '— re-record with: python tests/test_golden_states.py --regen')
        for name in GOLDEN_MODELS:
            with self.subTest(model=name):
                finals = run_model(name)
                golden = self.golden[name]
                for canon in sorted(set(finals) | set(golden)):
                    self.assertIn(canon, finals,
                                  f'{name}: world missing from engine output: {canon}')
                    self.assertIn(canon, golden,
                                  f'{name}: world absent from snapshot: {canon}')
                    got, (re_g, im_g) = finals[canon], golden[canon]
                    self.assertLessEqual(
                        abs(got - complex(re_g, im_g)), WEIGHT_TOLERANCE,
                        f'{name}: weight mismatch at {canon}: '
                        f'got {got:.9f}, snapshot {complex(re_g, im_g):.9f}')
                total = sum(abs(w) ** 2 for w in finals.values())
                self.assertLessEqual(abs(total - 1), 1e-6,
                                     f'{name}: total probability is {total}')


def regen():
    logging.getLogger('quantish').setLevel(logging.WARNING)
    CalcMode.default('Float')
    data = {name: snapshot(run_model(name)) for name in GOLDEN_MODELS}
    with open(GOLDEN_PATH, 'w') as f:
        json.dump(data, f, indent=1, sort_keys=True)
        f.write('\n')
    print(f'recorded {len(data)} models -> {GOLDEN_PATH}')


if __name__ == '__main__':
    if '--regen' in sys.argv:
        regen()
    else:
        unittest.main()
