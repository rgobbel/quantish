"""Regression suite: the multiworld engine must agree with the reference
implementation in the quantish_gld repo.

Two layers of comparison:

1. TestEngineParity — for each model YAML, build the *same* circuit for both
   engines (reference gates constructed programmatically from the model's
   links/angles) and diff the final states. Validates the state-evolution
   algorithm given identical inputs.

2. TestCrossRepoCircuits — run a model through multiworld while the reference
   repo loads its *own* circuit file through its own loader (circuits_yaml)
   in its own venv. Validates that paired circuit definitions in the two
   repos describe the same experiment, with no shared conversion code.

The reference repo is located via the QUANTISH_GLD_DIR environment variable,
defaulting to a 'quantish_gld' directory next to this repo. All tests skip
cleanly when it isn't present.

Canonical form for one world: sorted (particle, wire, sign) triples -> complex
weight. Weights must match to 1e-9 and total probability must be 1.
"""
import json
import logging
import os
import subprocess
import sys
import unittest
from pathlib import Path

import yaml
from addict import Addict

REPO_DIR = Path(__file__).resolve().parents[1]
GLD_DIR = Path(os.environ.get('QUANTISH_GLD_DIR', REPO_DIR.parent / 'quantish_gld'))
GLD_PYTHON = GLD_DIR / 'venv' / 'bin' / 'python'
MODELS_DIR = REPO_DIR / 'models'

sys.path.insert(0, str(GLD_DIR))

import multiworld.qnumber as qn
from multiworld.qnumber import CalcMode

WEIGHT_TOLERANCE = 1e-9

# Models exercised by the same-circuit parity sweep. All are maintained for
# the multiworld implementation (fig411 is grandfathered in: it exercises
# sequential splits whose products recombine, i.e. real interference).
PARITY_MODELS = [
    'fig45_multi',
    'fig47_multi',
    'fig47plus_multi',
    'fig49_multi',
    'fig411',
    'fig412x_multi',
    'fig414_multi',
    'fig414x_multi',
    'fig415_multi',
    'fig415x_multi',
    'fig416plus_multi',
    'fig417',
]

# model YAML in this repo -> circuit YAML loaded by the reference repo's own
# loader. Both files must describe the same experiment (topology AND angles).
CROSS_REPO_CIRCUITS = {
    'fig417': 'fig_4_17.yaml',
}


def load_model_config(name):
    with open(MODELS_DIR / 'defaults.yaml') as f:
        config = yaml.safe_load(f)
    with open((MODELS_DIR / name).with_suffix('.yaml')) as f:
        config.update(yaml.safe_load(f))
    config['loglevel'] = 'warning'
    return Addict(config)


def run_multiworld(name, canonical_wire=None):
    """Run a model through the multiworld engine. Returns (finals, sim) where
    finals maps canonical world keys to complex weights. canonical_wire maps a
    final PCoordinate to the wire name used in the comparison key; the default
    is the position endpoint (the wire the particle came to rest on)."""
    from multiworld.simulation import Simulation
    if canonical_wire is None:
        canonical_wire = lambda coord: str(coord.position.endpoint)
    sim = Simulation(load_model_config(name))
    result_space, _ = sim.run()
    finals = {}
    for point in result_space.index.values():
        canon = tuple(sorted(
            (pname, canonical_wire(coord), int(coord.sign))
            for pname, coord in point.coords.items()))
        finals[canon] = complex(point.weight)
    return finals, sim


class ReferenceComparisonMixin:
    def assert_states_match(self, mw, ref, context):
        for key in sorted(set(mw) | set(ref)):
            w_mw, w_ref = mw.get(key), ref.get(key)
            self.assertIsNotNone(w_mw, f'{context}: world missing in multiworld: {key}')
            self.assertIsNotNone(w_ref, f'{context}: world missing in reference: {key}')
            self.assertLessEqual(
                abs(w_mw - w_ref), WEIGHT_TOLERANCE,
                f'{context}: weight mismatch at {key}: mw={w_mw:.9f} ref={w_ref:.9f}')
        for label, finals in (('multiworld', mw), ('reference', ref)):
            total = sum(abs(w) ** 2 for w in finals.values())
            self.assertLessEqual(
                abs(total - 1), 1e-6,
                f'{context}: {label} total probability is {total}, expected 1')


@unittest.skipUnless((GLD_DIR / 'engine.py').is_file(),
                     f'reference repo not found at {GLD_DIR}')
class TestEngineParity(ReferenceComparisonMixin, unittest.TestCase):
    """Both engines, given the identical circuit, must produce identical
    final states."""

    @classmethod
    def setUpClass(cls):
        logging.getLogger('multiworld').setLevel(logging.WARNING)
        CalcMode.default('Float')
        qn.ZERO_THRESHOLD = qn.zero_threshold_fn()
        import qnumber as gqn  # the reference repo's top-level qnumber
        gqn.set_calc_mode('Float')
        gqn.CalcMode.default('Float')
        cls.gqn = gqn

    def run_reference(self, name, sim):
        """Build the reference circuit from the same YAML, reusing multiworld's
        parsed angles/weights/signs so both engines see identical numbers."""
        from engine import Gate, WeightedPoint, Sign, Coord, simulate_circuit
        gqn = self.gqn
        config = load_model_config(name)
        links = config.links
        gates = {}
        for gname in config.gates.keys():
            def out(port):
                src = f'{gname}.{port}'
                return links.get(src, f'{src}>END')
            gates[gname] = Gate(name=gname, angle=gqn.Real(float(sim.gates[gname].theta)),
                                ctrl_in=f'{gname}.control', ctrl_out=out('control'),
                                upper_in=f'{gname}.upper', upper_out=out('upper'),
                                lower_in=f'{gname}.lower', lower_out=out('lower'))
        initial_config = {}
        weight = complex(1)
        for pname in config.particles.keys():
            particle = sim.particles[pname]
            sign = Sign.PLUS if int(particle.sign) > 0 else Sign.MINUS
            initial_config[pname] = Coord(links[pname], sign)
            weight *= complex(particle.weight)
        initial = [WeightedPoint(config=initial_config, weight=gqn.Complex(weight))]
        steps = [[gates[g] for g in stage] for stage in sim.run_stages]
        history = simulate_circuit(initial, steps)
        finals = {}
        for wp in history[-1]:
            canon = tuple(sorted(
                (pname, wire.removesuffix('>END'), int(sign))
                for pname, (wire, sign) in wp.config.items()))
            finals[canon] = complex(wp.weight)
        return finals

    def test_models_match_reference_engine(self):
        for name in PARITY_MODELS:
            with self.subTest(model=name):
                mw, sim = run_multiworld(name)
                ref = self.run_reference(name, sim)
                self.assert_states_match(mw, ref, name)


@unittest.skipUnless(GLD_PYTHON.is_file(),
                     f'reference repo venv not found at {GLD_PYTHON}')
class TestCrossRepoCircuits(ReferenceComparisonMixin, unittest.TestCase):
    """A model in this repo and its paired circuit file in the reference repo
    must describe the same experiment, each loaded by its own code."""

    @classmethod
    def setUpClass(cls):
        logging.getLogger('multiworld').setLevel(logging.WARNING)
        CalcMode.default('Float')
        qn.ZERO_THRESHOLD = qn.zero_threshold_fn()

    def run_reference_circuit(self, circuit_file):
        result = subprocess.run(
            [str(GLD_PYTHON), str(Path(__file__).parent / 'gld_runner.py'),
             str(GLD_DIR), str(GLD_DIR / 'circuits' / circuit_file)],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0,
                         f'gld_runner failed for {circuit_file}:\n{result.stderr}')
        data = json.loads(result.stdout.splitlines()[-1])
        finals = {}
        for canon, (re, im) in zip(data['worlds'], data['weights']):
            finals[tuple(tuple(entry) for entry in canon)] = complex(re, im)
        return finals

    @staticmethod
    def emitting_wire(coord):
        """The reference loader names every wire after the gate port that
        emits onto it: '<gate>_<port>_out'."""
        origin = coord.position.origin
        return f'{origin.gate}_{origin.port}_out'

    def test_circuits_match_across_repos(self):
        for model_name, circuit_file in CROSS_REPO_CIRCUITS.items():
            with self.subTest(model=model_name, circuit=circuit_file):
                mw, _ = run_multiworld(model_name, canonical_wire=self.emitting_wire)
                ref = self.run_reference_circuit(circuit_file)
                self.assert_states_match(mw, ref, model_name)


if __name__ == '__main__':
    unittest.main()