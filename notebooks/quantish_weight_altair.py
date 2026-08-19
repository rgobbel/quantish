import marimo

__generated_with = "0.23.14"
app = marimo.App(width="full")

with app.setup:
    # Initialization code that runs before all other cells
    import marimo as mo
    from marimo import md
    import altair as alt
    import numpy as np
    # import mpmath as mpm
    import sympy as sym
    from sympy import sympify, I, N, re, im, oo
    from numpy import array, r_
    import pandas as pd
    import cmath as cm
    import math as m
    import yaml
    # from cmath import cos, sin, pi, phase, exp
    # from math import degrees, radians
    from dataclasses import dataclass
    from enum import Enum
    from graphlib import TopologicalSorter
    from collections import defaultdict
    from typing import List, Dict, Tuple
    from abc import ABC
    from importlib import import_module
    # try:
    #     from yaml_util import load_yaml
    # except ImportError:
    #     from src.yaml_util import load_yaml
    from pathlib import Path


@app.cell
def _():
    import importlib.util
    qn_spec = importlib.util.spec_from_file_location('qn', '/Users/gobbel/src/quantish/multiworld/qnumber.py')
    qn = importlib.util.module_from_spec(qn_spec)
    qn_spec.loader.exec_module(qn)
    return (qn,)


@app.cell
def _(qn):
    qn.CalcMode.mode = 'Symbolic'
    return


@app.cell(hide_code=True)
def sim_mode_constant():
    # SimMode = Enum('SimMode', ['float', 'symbolic'])
    SEP = '.'
    eval_mode = 'Symbolic'
    md('#### Enums and constants')
    return (SEP,)


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    # Simulation
    """)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Simulation run
    """)
    return


@app.cell(hide_code=True)
def load_run_configuration():
    def load_config(filename):
        with open(Path(filename).with_suffix('.yaml'), 'r') as f:
            return yaml.safe_load(f)
    md('### load run configuration')
    return


@app.cell(hide_code=True)
def show_config():
    sccb = mo.ui.checkbox(label='show_config', value=False)
    sccb
    return (sccb,)


@app.cell
def config_file_browser():
    config_file = mo.ui.file_browser(label='config file', 
                                     multiple=False, filetypes=['.yaml', '.yml'],
                                    initial_path=Path('../models'))
    config_file
    return


@app.cell
def _(sccb):
    with open(Path('../models/fig45.yaml')) as f:
        cf = yaml.safe_load(f)
    # print(f'LOADED {config_file.value[0].path}')
    if sccb.value:
        for k, v in cf.items():
            if type(v) is dict:
                print(f'  {k}:')
                for k2, v2 in v.items():
                    print(f'    {k2}: {v2}')
            print(f'  {k}: {v}')
    md('### set cf (config)')
    return (cf,)


@app.cell(disabled=True, hide_code=True)
def _(SymSimulation, cf):
    cf['symbolic'] = False
    sym_sim = SymSimulation(cf)
    md(f'### sim=SymSimulation(cf)')
    return (sym_sim,)


@app.cell(disabled=True, hide_code=True)
def _(Simulation, cf):
    cf['symbolic'] = False
    num_sim = Simulation(cf)
    md('### nsim = Simulation(cf)')
    return (num_sim,)


@app.cell(hide_code=True)
def _(num_sim):
    md(f'num_sim.gates = {num_sim.gates}')
    return


@app.cell(hide_code=True)
def _(num_sim):
    num_sim.run()
    return


@app.cell(hide_code=True)
def _(Simulation, SymSimulation):
    def run_sim(config):
        if config['symbolic']:
            sim = SymSimulation(config)
        else:
            sim = Simulation(config)
        return sim.run()
    md('### run_sim')
    return


@app.cell(hide_code=True)
def _(sym_sim):
    md(f'sym_sim.gates = {sym_sim.gates}')
    return


@app.cell(hide_code=True)
def _(sym_sim):
    md(f'sym_sim.config_space={sym_sim.config_dict}')
    return


@app.cell(hide_code=True)
def _(sym_sim):
    md(f'sym_sim.particles={sym_sim.particles}')
    return


@app.cell(disabled=True, hide_code=True)
def _(sym_sim):
    sym_result = sym_sim.run()
    md('sym_result = sym_sim.run')
    return


@app.cell
def _(ttsr):
    ttsr
    return


@app.cell
def _(ttsr):
    sym.exp(I * ttsr), sym.re(sym.exp(I * ttsr)), sym.im(sym.exp(I * (ttsr-sym.pi/2)))
    return


@app.cell(hide_code=True)
def cpair_algorithm_select(cpair_alg):
    md(f'## CPAIR ALGORITHM SELECT {cpair_alg}')
    return


@app.cell(hide_code=True)
def _(sym_cquad, ttsr):
    cps = sym_cquad(sympify(1), ttsr, sympify(1))
    return (cps,)


@app.cell
def _(cps):
    cps
    return


@app.cell
def _(cps, sym_cquad, ttsr):
    cps0 = sym_cquad(cps['straight'], ttsr, 1)
    return


@app.cell
def _(cps, sym_cquad, ttsr):
    cps1 = sym_cquad(cps['cross'], ttsr, 1)
    return


@app.cell
def _(cpair_sym, cps, ttsr):
    cpair_sym(cps['straight'], ttsr)
    return


@app.cell
def _(cpair_sym, cps, ttsr):
    cpair_sym(cps['cross'], ttsr)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Simulation classes
    """)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ### Simulation
    """)
    return


@app.cell(disabled=True, hide_code=True)
def _(
    SEP,
    SymGate,
    SymParticle,
    SymSink,
    cpair_alg,
    lo_perb_b,
    parse_position,
    sym_prob,
    topo_sort,
):
    class SymSimulation:
        def __init__(self, config):
            if not config['symbolic']:
                raise RuntimeError('Calling SymSimulation with symbolic == False')
            self.config = config
            self.particles = {}
            self.gates = {}
            self.sinks = {}
            self.links = config['links']
            self.order = topo_sort(self.links)
            self.config_space = defaultdict(list)
            # create domain object from config
            self.qvars = {vname: sympify(vval) for vname, vval in config['variables'].items()}
            for pname, pval in config['particles'].items():
                if type(pval['weight']) is str:
                    wval = sympify(pval['weight'])
                else:
                    wval = pval['weight']
                self.particles[pname] = SymParticle(pname, wval, pval['sign'])
                if pname in self.links.keys():
                    self.config_space[self.links[pname]] = self.particles[pname]
            for gname, gval in config['gates'].items():
                if type(gval['angle']) is str:
                    aval = sym.deg(sympify(gval['angle']))
                else:
                    aval = gval['angle']
                self.gates[gname] = SymGate(gname, aval)
            for sname in config['sinks']:
                self.sinks[sname] = SymSink(sname)

        def run(self):
            print('')
            print("SYMBOLIC run")
            print(f'CPAIR ALGORITHM = {cpair_alg.value[0].upper()}')
            for obname in self.order:
                if obname in self.particles.keys():
                    particle = self.particles[obname]
                    destination = parse_position(self.links[obname])
                    self.config_space[obname] = particle
                elif obname in self.gates.keys():
                    gate = self.gates[obname]
                    ctrl_pos = f'{obname}{SEP}control'
                    upper_pos = f'{obname}{SEP}upper'
                    lower_pos = f'{obname}{SEP}lower'
                    control = self.config_space.get(ctrl_pos)
                    swap = control is not None and control.prob > 0
                    # inputs
                    upper = self.config_space[upper_pos]
                    lower = self.config_space[lower_pos]
                    # output destinations
                    udest = self.links[upper_pos]
                    ldest = self.links[lower_pos]
                    if swap:
                        udest, ldest = ldest, udest
                    new_upper_trace = f'{gate.name}{SEP}upper->{udest}'
                    new_lower_trace = f'{gate.name}{SEP}lower->{ldest}'
                    print('')
                    print(f'MEASURE {gate}:c={control}, up={upper}, lo={lower}')
                    m_up, m_lo = gate.measure(control)
                    # print(f'type(m_up)={type(m_up)}, type(m_lo)={type(m_lo)}')
                    print(f'{m_up=}, {m_lo=}')
                    if control is not None and self.links.get(ctrl_pos) is not None:
                        cdest = self.links[ctrl_pos]
                        print(f'STORING: config_space[{cdest}] = {control}')
                        self.config_space[cdest] = control
                    sym_zero = sympify(0)
                    sym_one = sympify(1)
                    up_up_weight = up_lo_weight = sym_zero
                    lo_up_weight = lo_lo_weight = sym_zero
                    up_up_sign = up_lo_sign = sym_one
                    lo_up_sign = lo_lo_sign = sym_one
                    if m_up is not None and self.links.get(upper_pos) is not None:
                        up_par_a, up_par_b, up_perp_a, up_perp_b = m_up
                        up_up_sign = upper.sign if sym_prob(up_par_a) > sym_prob(up_par_b) else -upper.sign
                        up_up_weight = up_par_a + up_par_b
                        up_lo_sign = upper.sign if sym_prob(up_perp_a) > sym_prob(up_perp_b) else -upper.sign
                        up_lo_weight = up_perp_a + up_perp_b
                    if m_lo is not None and self.links.get(lower_pos) is not None:
                        lo_par_a, lo_par_b, lo_perp_a, lo_perp_b = m_lo
                        lo_up_sign = lower.sign if sym_prob(lo_par_a) > sym_prob(lo_par_b) else -lower.sign
                        lo_up_weight = lo_par_a + lo_par_b
                        lo_lo_sign = lower.sign if sym_prob(lo_perp_a) > sym_prob(lo_perp_b) else -lower.sign
                        lo_lo_weight = lo_perp_a + lo_perb_b
                    if abs(up_up_weight) >= abs(lo_up_weight):
                        new_upper_sign = up_up_sign
                    else:
                        new_upper_sign = lo_up_sign
                    new_upper_weight = up_up_weight + lo_up_weight
                    if abs(up_lo_weight) > abs(lo_lo_weight):
                        new_lower_sign = up_lo_sign
                    else:
                        new_lower_sign = lo_lo_sign
                    if m_up is not None and self.links.get(upper_pos) is not None:
                        next_up = SymParticle(upper.name, new_upper_weight,
                                              new_upper_sign, new_upper_trace)
                        print(f'STORING: config_space[{udest}] = {next_up}')
                        self.config_space[udest] = next_up
                    new_lower_weight = up_lo_weight + lo_lo_weight
                    if m_lo is not None and self.links.get(lower_pos) is not None:
                        next_lo = SymParticle(lower.name, new_lower_weight, 
                                              new_lower_sign, new_lower_trace)
                        print(f'STORING: config_space[{ldest}] = {next_lo}')
                        self.config_space[ldest] = next_lo
            print(f'RUN RESULT:')
            for k, v in self.config_space.items():
                r = re(v.weight)
                i = im(v.weight)
                print(f'    {k}: {N(r):.1f}{N(i):+.1f}j ({v})')
            return self.config_space
    md('#### SymSimulation class')
    return (SymSimulation,)


@app.cell(hide_code=True)
def simulation_class(
    Gate,
    Particle,
    SEP,
    Sink,
    cpair_alg,
    parse_position,
    prob,
    topo_sort,
):
    class Simulation:
        def __init__(self, config):
            if config['symbolic']:
                raise RuntimeError('Calling non-symbolic Simulation with symbolic == True')
            self.config = config
            self.particles = {}
            self.gates = {}
            self.sinks = {}
            self.links = config['links']
            self.order = topo_sort(self.links)
            self.config_space = {}
            self.qvars = {vname: vval for vname, vval in config['variables'].items()}
            for pname, pval in config['particles'].items():
                wval = complex(pval['weight'])
                assert type(wval) is complex, f'weight {pval["weight"]} is not complex'
                self.particles[pname] = Particle(pname, wval, pval['sign'])
                if pname in self.links.keys():
                    self.config_space[self.links[pname]] = self.particles[pname]
            for gname, gval in config['gates'].items():
                if type(gval['angle']) is str:
                    aval = float(N(sym.deg(sympify(gval['angle']))))
                else:
                    aval = gval['angle']
                self.gates[gname] = Gate(gname, aval)
            for sname in config['sinks']:
                self.sinks[sname] = Sink(sname)

        def run(self):
            print('')
            print("NUMERIC run")
            print(f'CPAIR ALGORITHM = {cpair_alg.value[0].upper()}')
            for obname in self.order:
                if obname in self.particles.keys():
                    particle = self.particles[obname]
                    destination = parse_position(self.links[obname])
                    self.config_space[obname] = particle
                elif obname in self.gates.keys():
                    gate = self.gates[obname]
                    ctrl_pos = f'{obname}{SEP}control'
                    upper_pos = f'{obname}{SEP}upper'
                    lower_pos = f'{obname}{SEP}lower'
                    control = self.config_space.get(ctrl_pos)
                    swap = control is not None and control.prob > 0
                    # inputs
                    upper = self.config_space.get(upper_pos)
                    lower = self.config_space.get(lower_pos)
                    # output destinations
                    udest = self.links[upper_pos]
                    ldest = self.links[lower_pos]
                    if swap:
                        udest, ldest = ldest, udest
                    new_upper_trace = f'{gate.name}{SEP}upper->{udest}'
                    new_lower_trace = f'{gate.name}{SEP}lower->{ldest}'
                    print('')
                    print(f'MEASURE {gate}:c={control},up={upper},lo={lower}')
                    m_up, m_lo = gate.measure(control)
                    if swap: upper, lower = lower, upper
                    print(f'{m_up=}, {m_lo=}')
                    if control is not None and self.links.get(ctrl_pos) is not None:
                        cdest = self.links[ctrl_pos]
                        print(f'STORING: config_space[{cdest}] = {control}')
                        self.config_space[cdest] = control
                    up_up_weight = up_lo_weight = 0
                    lo_up_weight = lo_lo_weight = 0
                    up_up_sign = up_lo_sign = 0
                    lo_up_sign = lo_lo_sign = 0
                    if m_up is not None and self.links.get(upper_pos) is not None:
                        up_par_a, up_par_b, up_perp_a, up_perp_b = m_up
                        up_up_sign = upper.sign if prob(up_par_a) > prob(up_par_b) else -upper.sign
                        up_up_weight = up_par_a + up_par_b
                        up_lo_sign = upper.sign if prob(up_perp_a) > prob(up_perp_b) else -upper.sign
                        up_lo_weight = up_perp_a + up_perp_b
                    if m_lo is not None and self.links.get(lower_pos) is not None:
                        lo_par_a, lo_par_b, lo_perp_a, lo_perp_b = m_lo
                        lo_up_sign = lower.sign if prob(lo_par_a) > prob(lo_par_b) else -lower.sign
                        lo_up_weight = lo_par_a + lo_par_b
                        lo_lo_sign = lower.sign if prob(lo_perp_a) > prob(lo_perp_b) else -lower.sign
                        lo_lo_weight = lo_perp_a + lo_perp_b
                    if prob(up_up_weight) >= prob(lo_up_weight):
                        new_upper_sign = up_up_sign
                    else:
                        new_upper_sign = lo_up_sign
                    new_upper_weight = up_up_weight + lo_up_weight
                    if prob(up_lo_weight) > prob(lo_lo_weight):
                        new_lower_sign = up_lo_sign
                    else:
                        new_lower_sign = lo_lo_sign
                    if m_up is not None and self.links.get(upper_pos) is not None:
                        next_up = Particle(upper.name, new_upper_weight,
                                              new_upper_sign, new_upper_trace)
                        print(f'STORING: config_space[{udest}] = {next_up}')
                        self.config_space[udest] = next_up
                    new_lower_weight = up_lo_weight + lo_lo_weight
                    if m_lo is not None and self.links.get(lower_pos) is not None:
                        next_lo = Particle(lower.name, new_lower_weight,
                                              new_lower_sign, new_lower_trace)
                        print(f'STORING: config_space[{ldest}] = {next_lo}')
                        self.config_space[ldest] = next_lo
            print(f'RUN RESULT:')
            for k, v in self.config_space.items():
                print(f'    {k}: {v}')
            return self.config_space
    md('#### Simulation class')
    return (Simulation,)


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ### Sink
    """)
    return


@app.cell(disabled=True, hide_code=True)
def _(Sink):
    class SymSink(Sink):
        """For storing final output values. Obsolete?"""
        def __init__(self, name):
            self.name = name
            self.value = {}
    md('#### SymSink class')
    return (SymSink,)


@app.cell(hide_code=True)
def sink_class():
    class Sink:
        "A place to put final outputs"
        def __init__(self, name):
            self.name = name
            self.value = None
    md('#### Sink class')
    return (Sink,)


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ### Angle
    """)
    return


@app.cell(hide_code=True)
def symangle(Angle):
    class SymAngle(Angle):
        def __init__(self, theta, units='degrees'):
            stheta = sym.sympify(theta)
            if units == 'degrees':
                self.theta = sym.rad(stheta)
            else:
                self.theta = stheta
            self.theta = self.theta % (2 * sym.pi)
        def __repr__(self):
            # return f'{self.__class__.__name__}:{self.degrees:.0f}º'
            return f':{self.degrees:.1f}º'
        @property
        def degrees(self):
            return sym.deg(self.theta)
        @property
        def radians(self):
            return self.theta
    md('#### SymAngle class')
    return (SymAngle,)


@app.cell
def _(qn):
    qn.qify(30).radians
    return


@app.cell
def angle_class(qn):
    @dataclass
    class Angle:
        theta: qn.Real
        def __init__(self, theta, units='degrees'):
            theta = qn.qify(theta)
            if units == 'degrees':
                self.theta = theta.radians
            else:
                self.theta = theta
            self.theta %= 2 * qn.PI_fn()
        def __hash__(self):
            return hash(self.theta)
        def __call__(self):
            return self.theta
        def __repr__(self):
            return f'{self.degrees:.1f}º'
        def __add__(self, other):
            if type(other) is type(self):
                value = other.radians
            else:
                value = other
            return self.__class__(self.radians + value, units='radians')
        def __mul__(self, other):
            if type(other) is type(self):
                value = other.radians
            else:
                value = other
            return self.__class__(self.radians * value, units='radians')
        @property
        def degrees(self):
            return self.theta.degrees
        @property
        def radians(self):
            return self.theta
    md('#### Angle class')
    return (Angle,)


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ### Particle
    """)
    return


@app.cell(disabled=True, hide_code=True)
def symparticle(sym_prob):
    class SymParticle:
        def __init__(self, name, weight, sign, trace=''):
            self.name = name
            self.weight = sym.sympify(weight)
            self.sign = sym.sympify(sign)
            if trace:
                self.trace = trace
            else:
                self.trace = self.name
        def __repr__(self):
            ss = f"{'+' if self.sign > 0 else '-'}"
            if self.weight == 0:
                return '0'
            x = self.weight
            if im(x) == 0:
                ws = f'{N(re(x)):.1f}'
            elif re(x) == 0:
                ws = f'{N(im(x)):.1f}j'
            else:
                ws = f'{N(re(x)):.1f}{N(im(x)):+.1f}j'
            return f'{self.__class__.__name__}:{self.name}{ss}({ws}:{angstr_sym(self.weight)})({self.weight})({self.trace})'
        def __add__(self, other):
            if self.prob >= other.prob:
                new_sign = self.sign
            else:
                new_sign = other.sign
            new_weight = self.weight + other.weight
            return self.__class__(self.name, new_weight, new_sign, f'->{self.trace}+{other.trace}')
        @property
        def prob(self):
            return sym_prob(self.weight)
    md('#### SymParticle class')
    return (SymParticle,)


@app.cell
def _():
    return


@app.cell
def particle_class():
    class Particle:
        def __init__(self, name, weight, sign, trace=''):
            self.name = name
            self.weight = weight
            self.sign = sign
            if trace:
                self.trace = trace
            else:
                self.trace = self.name
        def __repr__(self):
            ss = f"{'+' if self.sign > 0 else '-'}"
            ws = f'{self.weight.real:.2f}{self.weight.imag:+.2f}'
            return f'{self.__class__.__name__}{ss}({ws}:{angstr(self.weight)}'
        def __add__(self, other):
            if self.prob >= other.prob:
                new_sign = self.sign
            else:
                new_sign = other.sign
            new_weight = self.weight + other.weight
            return self.__class__(self.name, new_weight, new_sign, f'->{self.trace}+{other.trace}')
        @property
        def prob(self):
            return abs(self.weight)**2
    md('#### Particle class')
    return (Particle,)


@app.cell
def _(Particle, qn):
    p = Particle('p', weight=qn.Complex(1), sign=1)
    return (p,)


@app.cell
def _(p):
    p.weight
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ### Gate
    """)
    return


@app.cell(hide_code=True)
def symgate(SymAngle, sym_cquad):
    class SymGate:
        def __init__(self, name, theta):
            self.name = name
            self.theta = SymAngle(theta)
        def __repr__(self):
            return f'{self.__class__.__name__}({self.theta})'
        def measure(self, control, upper=None, lower=None):
            swap = control is not None and control.prob > 0
            print(f'{self.name}:{"NOT" if not swap else ""} SWAPPING')
            if upper is not None:
                m_up_dict = sym_cquad(upper.weight, self.theta.radians, upper.sign)
                # m_up_dict['c2b'] = -m_up_dict['c2b']
                # m_up_dict['c3b'] = -m_up_dict['c3b']
                m_up = [m_up_dict[c] for c in ['c2a', 'c2b', 'c3a', 'c3b']]
            else: m_up = None
            if lower is not None:
                m_lo_dict = sym_cquad(lower.weight, self.theta.radians, lower.sign)
                # m_lo_dict['c2b'] = -m_lo_dict['c2b']
                # m_lo_dict['c3b'] = -m_lo_dict['c3b']
                m_lo = [m_lo_dict[c] for c in ['c2a', 'c2b', 'c3a', 'c3b']]
            else: m_lo = None
            return m_up, m_lo
    md('#### SymGate class')
    return (SymGate,)


@app.cell
def gate_class(Angle, cquad, qn):
    class Gate:
        def __init__(self, name, theta:qn.Real):
            self.name = name
            self.theta = Angle(theta)
        def __repr__(self):
            return f'{self.__class__.__name__}({self.theta})'
        def measure(self, control, upper=None, lower=None):
            out_keys = ['c2a', 'c2b', 'c3a', 'c3b']
            swap = control is not None and control.prob > 0
            print(f'{self.name}: {"NOT" if not swap else ""} SWAPPING')
            if upper is not None:
                up_res = cquad(upper.weight, self.theta.radians, upper.sign)
                # m_up_dict['c2b'] *= -1
                # m_up_dict['c3b'] *= -1
                # m_ = [m_in_up_dict[c] for c in ['c2a', 'c2b', 'c3a', 'c3b']]
            else: up_res = {k: 0 for k in out_keys}
            if lower is not None:
                lo_res = cquad(lower.weight, self.theta.radians, lower.sign)
                # m_lo_dict['c2b'] *= -1
                # m_lo_dict['c3b'] *= -1
                # m_in_lo = [m_in_lo_dict[c] for c in ['c2a', 'c2b', 'c3a', 'c3b']]
            else: lo_res = {k: 0 for k in out_keys}
            m_up = [up_res['c2a'] + lo_res['c3a'], up_res['c2b'] + lo_res['c3b']]
            m_lo = [up_res['c3a'] + lo_res['c2a'], up_res['c3b'] + lo_res['c2b']]
            if swap:
                m_up, m_lo = m_lo, m_up
            return m_up + m_lo
    md('#### Gate class')
    return (Gate,)


@app.cell
def _(Particle, qn):
    p1x = Particle('p1x', weight=qn.Complex(1), sign=1)
    return (p1x,)


@app.cell
def _(Particle, qn):
    p2x = Particle('p2x', weight=qn.Complex(1), sign=1)
    return (p2x,)


@app.cell
def _(p1x, p2x):
    p1x, p2x
    return


@app.cell
def _(Angle, Gate, qn):
    g1x = Gate('g1x', Angle(qn.qify(30)).degrees)
    return (g1x,)


@app.cell
def _(Angle, Gate, qn):
    g2x = Gate('g2x', Angle(qn.qify(30)).degrees)
    return (g2x,)


@app.cell
def _(g1x, g2x):
    g1x, g2x
    return


@app.cell
def _(g1x, p1x):
    g1res = g1x.measure(control=None, upper=p1x)
    return (g1res,)


@app.cell
def _(g1res):
    g1res
    return


@app.cell
def _(Particle, g1res):
    p1x2a = Particle('p1x2a', weight=g1res[0], sign=1)
    return (p1x2a,)


@app.cell
def _(Particle, g1res):
    p1x2b = Particle('p1x2b', weight=g1res[1], sign=-1)
    return (p1x2b,)


@app.cell
def _(Particle, g1res):
    p1x3a = Particle('p1x3a', weight=g1res[2], sign=1)
    return (p1x3a,)


@app.cell
def _(Particle, g1res):
    p1x3b = Particle('p1x3b', weight=g1res[3], sign=-1)
    return (p1x3b,)


@app.cell
def _(p1x2a, p1x2b):
    p1xup = p1x2a + p1x2b
    return (p1xup,)


@app.cell
def _(p1x3a, p1x3b):
    p1xlo = p1x3a + p1x3b
    return (p1xlo,)


@app.cell
def _(p1x2a, p1x2b, p1x3a, p1x3b, p1xlo, p1xup):
    p1x2a, p1x2b, p1x3a, p1x3b, p1xup, p1xlo
    return


@app.cell
def _(p1x2a, p1x2b, p1x3a, p1x3b, p1xlo, p1xup):
    p1x2a.prob, p1x2b.prob, p1x3a.prob, p1x3b.prob, p1xup.prob, p1xlo.prob
    return


@app.cell
def _():
    return


@app.cell
def _(p1x2a, p1x2b, p1x3a, p1x3b, p1xlo, p1xup):
    p1x2a.prob + p1x2b.prob, p1x3a.prob + p1x3b.prob, p1xup.prob + p1xlo.prob
    return


@app.cell
def _(g1res):
    g1res
    return


@app.cell
def _(g2x, p1xlo, p1xup):
    g2res = g2x.measure(control=None, upper=p1xup, lower=p1xlo)
    return (g2res,)


@app.cell
def _(g2res):
    g2res
    return


@app.cell
def _(g2res):
    g2sum0 = g2res[0] + g2res[1]
    g2sum1 = g2res[2] + g2res[3]
    complex(g2sum0), complex(g2sum1)
    return


@app.cell
def _(g2res):
    g2up = g2res[0][0] + g2res[0][1] + g2res[1][2] + g2res[1][3]
    g2lo = g2res[0][2] + g2res[0][3] + g2res[1][0] + g2res[1][1]
    complex(g2up.v), complex(g2lo.v)
    return


@app.cell
def _(g2res):
    g2sum = sum(g2res[0])
    return (g2sum,)


@app.cell
def _(g2sum):
    g2sum, abs(g2sum)**2
    return


@app.cell(hide_code=True)
def sym_integer_constants():
    four = sympify(4)
    three = sympify(3)
    one = sympify(1)
    six = sympify(6)
    md('### Symbolic integer constants')
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    # Experiments
    """)
    return


@app.cell
def _():
    mo.left(md(rf"""

    $$
    \begin{{align*}}
    (p_{{1_{{c2a}}}}+p_{{1_{{c2b}}}} + p_{{1_{{c3a}}}}+p_{{1_{{c3b}}}})(p_{{2_{{c2a}}}}+p_{{2_{{c2b}}}} + p_{{2_{{c3a}}}}+p_{{2_{{c3b}}}}) ... (p_{{n_{{c2a}}}}+p_{{n_{{c2b}}}} + p_{{n_{{c3a}}}}+p_{{n_{{c3b}}}})
    \end{{align*}}
    $$
    """))
    return


@app.cell
def _():
    vx1 = [1,2,3,4]
    vx2 = [1,2,3,4]
    return vx1, vx2


@app.cell
def _(g1res):
    outer1 = np.outer(g1res, g1res)
    outer1
    return (outer1,)


@app.cell
def _(outer1):
    sum(outer1)
    return


@app.cell
def _(vx1, vx2):
    outer2 = np.outer(vx2, vx1)
    outer2
    return (outer2,)


@app.cell
def _(outer1, outer2):
    outdiff1 = outer1 - outer2
    outdiff1
    return


@app.cell
def _(outer1, outer2):
    outdiff2 = outer2 - outer1
    outdiff2
    return


@app.cell
def _():
    np.array([[1,2,3]]).T
    return


@app.cell
def _():
    mo.left(md(rf"""
    $$
    \begin{{align*}}
    (p_1^{{c2a}} + p_1^{{c2b}}+p_1^{{c3a}}+p_1^{{c3b}}) (p_2^{{c3a}}+p_2^{{c2b}}+p_2^{{c3a}}+p_2^{{c3b}})...(p_n^{{c3a}}+p_n^{{c3b}}+p_n^{{c3a}}+p_n^{{c3b}})
    \end{{align*}}
    $$
    """))
    return


@app.cell
def _(qn):
    ttsr = sym.acos(sympify(4)/sympify(5))
    tts = sym.deg(ttsr)
    tt = qn.to_native(tts)
    ttr = m.radians(tt)
    mo.left(md(rf"""
    $$
    \begin{{align*}}
    ttsr&=&{ttsr}\\
    tts&=&{tts}\\
    tt&=&{tt}\\
    ttr&=&{ttr}
    \end{{align*}}
    $$
    """))
    return tt, tts, ttsr


@app.cell(hide_code=True)
def gate_particle_vars(SymGate, SymParticle, tts):
    g_30 = SymGate('g_30', tts)
    g_0 = SymGate('g_0', 0)
    p_ctrl0 = SymParticle('p_ctrl0', sympify(0)*I, 1)
    mo.left(md(rf"""### Gate and Particle variables
    $$
    \begin{{align*}}
    &g_{{30}} = SymGate('{{g_{{30}}}}', {tts})\\
    &g_0 = SymGate('{{g_0}}', 0)\\
    &p_{{ctrl0}} = SymParticle('{{p_{{ctrl0}}}}', 0i, 1)\\
    \end{{align*}}
    $$
    """))
    return (g_30,)


@app.cell
def _(cpair_sym, tts):
    cpair_sym(sym.rad(tts), 1)
    return


@app.cell(hide_code=True)
def g_30_measure_p1(g_30):
    m_sym_30 = g_30.measure(None)
    md('### m_sym_30 = g_30.measure(None, upper=p1)')
    return (m_sym_30,)


@app.cell
def m300(m300):
    m300
    return


@app.cell
def _(m_p1_up, m_sym_30):
    [m_sym_30[0][i] - m_p1_up[0][i] for i in range(4)]
    return


@app.cell
def _(m_p1_up_a, m_sym_30):
    [m_sym_30[0][i] - m_p1_up_a[0][i] for i in range(4)]
    return


@app.cell
def _(m_p1_up_b, m_sym_30):
    [m_sym_30[0][i] - m_p1_up_b[0][i] for i in range(4)]
    return


@app.cell
def _(m300):
    abs(m300[2])**2, abs(m300[3])**2, abs(m300[2])**2 + abs(m300[2])**2
    return


@app.cell
def p1_up(SymParticle, m_sym_30):
    p1_up = SymParticle('p1_up', m_sym_30[0][2] + m_sym_30[0][3], 1)
    return (p1_up,)


@app.cell
def p1_up_a(SymParticle, m_sym_30):
    p1_up_a = SymParticle('p1_up_a', m_sym_30[0][2], 1)
    return


@app.cell
def p1_up_b(SymParticle, m_sym_30):
    p1_up_b = SymParticle('p1_up_b', m_sym_30[0][3], -1)
    return


@app.cell
def p1_up_val(p1_up):
    p1_up
    return


@app.cell
def m_p1_up(g_30):
    m_p1_up = g_30.measure(None)
    return (m_p1_up,)


@app.cell
def m_p1_up_a(g_30):
    m_p1_up_a = g_30.measure(None)
    return (m_p1_up_a,)


@app.cell
def m_p1_up_b(g_30):
    m_p1_up_b = g_30.measure(None)
    return (m_p1_up_b,)


@app.cell
def p1outs(m_sym_30):
    p1outs = np.array([N(m_sym_30[0][i]) for i in range(4)])
    return (p1outs,)


@app.cell
def particles_from_p1(SymParticle, m_sym_30):
    p1_c2a = SymParticle('p1_c2a', m_sym_30[0][0], 1)
    p1_c2b = SymParticle('p1_c2b', m_sym_30[0][1], -1)
    p1_c3a = SymParticle('p1_c3a', m_sym_30[0][2], 1)
    p1_c3b = SymParticle('p1_c3b', m_sym_30[0][3], -1)
    return p1_c2a, p1_c2b


@app.cell
def fancy_latex_psum(p1_c2a, p1_c2b):
    md(rf'${sym.latex(p1_c2a.weight + p1_c2b.weight)}$')
    return


@app.cell
def _():
    return


@app.cell
def m_p1_c2a(g_30):
    m_p1_c2a = g_30.measure(None)
    return (m_p1_c2a,)


@app.cell
def m_p1_c2b(g_30):
    m_p1_c2b = g_30.measure(None)
    return (m_p1_c2b,)


@app.cell
def p2outs(m_p1_c2a, m_p1_c2b):
    p2outs = np.array([N(m_p1_c2a[0][i]+m_p1_c2b[0][i]) for i in range(4)])
    return (p2outs,)


@app.cell
def p1outs_minus_p2outs(p1outs, p2outs):
    p1outs - p2outs
    return


@app.cell
def measure_for_latex_1(g_30):
    g_30.measure(None)
    return


@app.cell
def p1_particle_def(SymParticle):
    p1 = SymParticle('p1', (sym.sympify(1)+(sym.I * sym.sympify(0))), 1)
    return


@app.cell
def _(m_sym_30):
    m_sym_30[0]
    return


@app.cell
def _(m_sym_30):
    m300 = m_sym_30[0]
    return (m300,)


@app.cell
def _():
    abs((3/5)+(4j/5))
    return


@app.cell
def _(m300):
    m300[0]**2 + m300[1]**2 + m300[2]**2 + m300[3]**2
    return


@app.cell
def _():
    mya, myb = sympify(3)/sympify(5), (I * sympify(4)/sympify(5))
    return mya, myb


@app.cell
def _(mya, myb):
    mya, myb
    return


@app.cell
def _():
    sym.exp(sym.rad(30) * I) * sym.cos(sym.rad(30))
    return


@app.cell
def _(m300):
    m300[0]**2 + m300[1]**2 + m300[2]**2 + m300[3]**2
    return


@app.cell
def _(m300):
    N(m300[0]**2 + m300[1]**2 + m300[2]**2 + m300[3]**2)
    return


@app.cell
def measure(cpair, qn, w):
    def cquad(weight:qn.Complex, theta:qn.Real, sign):
        """measure a particle through a gate

        weight -- complex-valued weight
        theta -- rotation angle
        sign -- plus or minus one
        """
        def spw(x):
            return f'{x.real:.2f}{x.imag:+.2f}j'
        # following figure 4.4 in Good and Real
        twist = theta - qn.PI_fn()/2
        c1 = weight
        if sign > 0: # straightforward rotation by theta
            c2, c3 = cpair(c1, theta)
        else:
            c2, c3 = cpair(c1, twist)
        c2a, c2b = cpair(c2, -theta)
        c3a, c3b = cpair(c3, -theta)
        straight = qn.Complex(c2.real+c2.imag*qn.I_fn())
        cross = qn.Complex(c3.real+c3.imag*qn.I_fn())
        print(f'MEASURE {weight=}, theta={angstr(theta)}, {sign=}')
        print(f'RESULT  straight={spw(straight)}:{angstr(straight)} ({straight})')
        print(f'        cross={spw(cross)}:{angstr(cross)} ({cross})')
        print(f'        c2={spw(c2)}:{angstr(c2)} ({c2}')
        print(f'        c3={spw(c3)}:{angstr(c3)} ({c3}')
        print(f'        c2a={spw(c2a)}:{angstr(c2a)} ({c2a})')
        print(f'        c2b={spw(c2b)}:{angstr(c2b)} ({c2b})')
        print(f'        c3a={spw(c3a)}:{angstr(c3a)} ({c3a})')
        print(f'        c3b={spw(c3b)}:{angstr(c3b)} ({c3b})')
        result = {'straight': straight,
                  'cross': cross,
                  'c2': c2,
                  'c3': c3,
                  'c2a': c2a,
                  'c2b': c2b,
                  'c3a': c3a,
                  'c3b': c3b,
                  'w': w}
        return result

    mo.md("""
    ### cquad
    """)
    return (cquad,)


@app.cell(disabled=True, hide_code=True)
def sym_measure(cpair_sym):
    def sym_cquad(weight, theta, sign):
        """measure a particle through a gate, using symbolic math

        weight -- complex-valued weight
        theta -- rotation angle
        sign -- plus or minus one
        """
        def sp(x):
            if im(x) <= 1e-15:
                return f'{N(re(x)):.1f}º'
            elif re(x) <= 1e-15:
                return '90º'
            else:
                print(f'XXXX {x}')
                return f'{N(sym.deg(sym.arg(x)))}º'
        def spw(x):
            return f'{N(re(x)):.2f}{N(im(x)):+.2f}j'
        # following figure 4.4 in Good and Real
        sym_w = sym.sympify(weight)
        sym_theta = sym.sympify(theta)
        sym_sign = sym.sympify(sign)
        twist = sym_theta - sym.pi/2
        c1 = sym_w
        if sign > 0: # straightforward rotation by theta
            c2, c3 = cpair_sym(c1, sym_theta)
        else:
            c2, c3 = cpair_sym(c1, twist)
        c2a, c2b = cpair_sym(c2, -sym_theta)
        c3a, c3b = cpair_sym(c3, -sym_theta)
        straight = sym.re(c2) + sym.im(c2) * sym.I
        cross = sym.re(c3) + sym.im(c3) * sym.I
        print(f'MEASURE {weight=}, theta={angstr_sym(theta)}, {sign=}')
        # print(f'RESULT  straight={spw(straight)}:{angstr_sym(straight)} ({straight})')
        # print(f'        cross={spw(cross)}:{angstr_sym(cross)} ({cross})')
        # print(f'        c2={spw(c2)}:{angstr_sym(c2)} ({c2}')
        # print(f'        c3={spw(c3)}:{angstr_sym(c3)} ({c3}')
        print(f'RESULT  c2a={spw(c2a)}:{angstr_sym(c2a)} ({c2a})')
        print(f'        c2b={spw(c2b)}:{angstr_sym(c2b)} ({c2b})')
        print(f'        c3a={spw(c3a)}:{angstr_sym(c3a)} ({c3a})')
        print(f'        c3b={spw(c3b)}:{angstr_sym(c3b)} ({c3b})')
        result = {'straight': straight,
                  'cross': cross,
                  'c2': c2,
                  'c3': c3,
                  'c2a': c2a,
                  'c2b': c2b,
                  'c3a': c3a,
                  'c3b': c3b,
                  'w': sym_w}
        return result
    mo.md("""
    ### sym_cquad
    This is where most of the interesting stuff happens
    """)
    return (sym_cquad,)


@app.cell(hide_code=True)
def plot_fw_md():
    mo.md(r"""
    # Plotting framework
    """)
    return


@app.cell(hide_code=True)
def setup_md():
    md("## Setup")
    return


@app.cell(hide_code=True)
def measurement(cquad, sign, theta, w):
    measurement = cquad(w, theta, sign)
    return (measurement,)


@app.cell(hide_code=True)
def measurement_params_md():
    mo.md(r"""
    ## Measurement parameters
    """)
    return


@app.cell(hide_code=True)
def ui_widget_creation(tt):
    def _():
        comp_list = ['straight', 'cross', 'c2', 'c3', 'c2a', 'c2b', 'c3a', 'c3b', 'w']
        # comp_i = {comp: i for i, comp in enumerate(comp_list)}
        # comp_s = {i: comp for i, comp in enumerate(comp_list)}
        wr_slide = mo.ui.slider(-1, 1, step=0.05, value=1, 
                                debounce=True, label=r'$w_{real}$')
        wi_slide = mo.ui.slider(-1, 1, step=0.05, value=0,
                                debounce=True, label=r'$w_{imag}$')
        theta_slide = mo.ui.slider(start=0, stop=90, value=tt)
        # theta_slide = mo.ui.slider(0, 360, step=0.01, value=30, debounce=False, label=rf'${{\theta}}$')
        sign_check = mo.ui.checkbox(label='sign', value=True)
        comp_select = mo.ui.multiselect(comp_list, label='Components to plot:')
        return wr_slide, wi_slide, theta_slide, sign_check, comp_select
    wr_slide, wi_slide, theta_slide, sign_check, comp_select = _()
    md('### UI widget creation')
    return comp_select, sign_check, theta_slide, wi_slide, wr_slide


@app.cell(hide_code=True)
def values_from_ui(
    comp_select,
    qn,
    sign_check,
    theta_slide,
    wi_slide,
    wr_slide,
):
    wr = wr_slide.value
    wi = wi_slide.value
    w = qn.Complex(wr, wi)
    theta = m.radians(theta_slide.value)
    sign = 1 if sign_check.value else -1
    selected_compoments = comp_select.value
    md('### UI widget values')
    return selected_compoments, sign, theta, w


@app.cell(hide_code=True)
def display_sel_md():
    mo.md(r"""
    ## Display selection
    """)
    return


@app.cell(hide_code=True)
def component_select(comp_select):
    comp_select
    return


@app.cell
def plot_input_ui(sign_check, theta_slide, wi_slide, wr_slide):
    md(f"""
    {wr_slide}
    {wi_slide}

    {theta_slide}

    {sign_check}
    """)
    return


@app.cell(hide_code=True)
def measurement_plot_md():
    mo.md(r"""
    # Measurement plot
    """)
    return


@app.cell(hide_code=True)
def _(cpair_alg):
    cpair_alg
    return


@app.cell
def weight_plot(measurement, plot_weights, selected_compoments):
    plot_weights(data=measurement, selections=tuple(selected_compoments))
    return


@app.cell
def _():
    mvals = ('straight', 'cross', 'c2', 'c3', 'c2a', 'c2b', 'c3a', 'c3b', 'w')
    return


@app.cell
def _(measurement):
    print(f'{measurement=}')
    #', '.join([f'{c}={x:.1f}' for c, x in zip(mvals, measurement)])
    return


@app.cell
def _(qn):
    qn.Complex(qn.qify(1)/2).cos
    return


@app.cell(hide_code=True)
def support_fns_md():
    mo.md(r"""
    # Support functions
    """)
    return


@app.cell
def cpair_float(cpair_alg, qn):
    def cpair(w:qn.Complex, theta:qn.Real, sign=1):
        "basic weight rotation"
        assert type(w) is qn.Complex, f'weight {w} is not complex'
        twist = theta - qn.PI_fn()/2
        cpa = cpair_alg.value[0]
        if cpa == 'rotate & scale':
            print(qn.I_fn() * theta)
            wplus = w * theta.cos * (qn.I_fn() * theta).exp
            wminus = w * theta.sin * (qn.I_fn() * twist).exp
        elif cpa == 'rotate only':
            wplus = w * (qn.I_fn() * theta).exp
            wminus = w * (qn.I_fn() * twist).exp
        elif cpa == 'scale only':
            wrotp = w * (qn.I_fn() * theta).exp
            wrotm = w * (qn.I_fn() * twist).exp
            wplus_r = wrotp.real
            wplus_i = wrotp.imag
            wplus = qn.Complex(wplus_r, wplus_i)
            wminus_r = wrotm.real
            wminus_i = wrotm.imag
            wminus = qn.Complex(wminus_r, wminus_i)
        elif cpa == 'official':
            if sign == 1: 
                c2a = w * theta.cos**2
                c2b = w * theta.cos * theta.sin * qn.I_fn()
                c3a = w * theta.sin**2
                c3b = w * theta.cos * theta.sin * -qn.I_fn()
            else:
                c2a = w * twist.cos**2
                c2b = w * twist.cos * twist.sin * qn.I_fn()
                c3a = w * twist.sin**2
                c3b = w * twist.cos * twist.sin * -qn.I_fn()
            wplus = c2a + c2b
            wminus = c3a + c3b
        else:
            raise ValueError(f'{cpair_alg.value} is not a valid value for cpair_alg')
        return wplus, wminus
    md(f"### cpair: {cpair.__doc__}")
    return (cpair,)


@app.cell
def _(qn):
    qn.I_fn() * qn.qify(30).radians
    return


@app.cell
def _(cpair, qn):
    cpair(qn.Complex(1), qn.qify(30).radians)
    return


@app.cell
def _(cpair, qn, tt):
    cpair(qn.Complex(qn.qify(1)), tt)
    return


@app.cell(hide_code=True)
def _():
    cpair_alg = mo.ui.multiselect(
        label='cpair algorithm',
        max_selections=1,
        options=['scale only', 'rotate only', 'rotate & scale', 'official'],
        value=['rotate & scale']
    )
    return (cpair_alg,)


@app.cell(hide_code=True)
def cpair_sym(cpair_alg):
    def cpair_sym(w, theta, sign=1):
        sym_w = sym.sympify(w)
        sym_theta = sym.sympify(theta)
        twist = sym_theta - (sym.pi / sympify(2))
        cpa = cpair_alg.value[0]
        if cpa == 'rotate & scale':
            wplus = sym_w * sym.cos(sym_theta) * sym.exp(I * sym_theta)
            wminus = sym_w * sym.sin(sym_theta) * sym.exp(I * twist)
        elif cpa == 'rotate only':
            wplus = sym_w * sym.exp(I * sym_theta)
            wminus = sym_w * sym.exp(I * twist)
        elif cpa == 'scale only':
            wplus_r = re(sym_w) * sym.cos(theta)
            wplus_i = im(sym_w) * sym.sin(theta)
            wplus = wplus_r + wplus_i * I
            wminus_r = sym_w * sym.cos(twist)
            wminus_i = sym_w * sym.sin(twist)
            wminus = wminus_r + wminus_i * I
        elif cpa == 'official':
            if sign == 1: 
                c2a = w * m.cos(theta)**2
                c2b = w * m.cos(theta) * m.sin(theta) * 1j
                c3a = w * m.sin(theta)**2
                c3b = w * m.cos(theta) * m.sin(theta) * -1j
            else:
                c2a = w * m.cos(twist)**2
                c2b = w * m.cos(twist) * m.sin(twist) * 1j
                c3a = w * m.sin(twist)**2
                c3b = w * m.cos(twist) * m.sin(twist) * -1j
            wplus = c2a + c2b
            wminus = c3a + c3b
        else:
            raise ValueError(f'{cpair_alg.value} is not a valid value for cpair_alg')
        return wplus, wminus
    md('### cpair_sym')
    return (cpair_sym,)


@app.cell
def num_vs_sym_results(SymAngle, cpair_sym):
    cpsyms = r"$\sqrt{3} * \exp{\i * \pi / 6}/4$"
    mo.left(md(rf"""
    ### numeric vs. symbolic results
    $$
    \begin{{align*}}
    &cpair(1, Angle(30).radians)=\sqrt{{3}} *       exp(i * \pi / 6)/4 \\
    &cpair\_{{sym}}(1, SymAngle(30).radians)={cpair_sym(1, SymAngle(30).radians)}
    \end{{align*}}
    $$
    """))
    return


@app.function
def angstr(x):
    return f'{m.degrees(cm.phase(x)):.1f}º'


@app.function(disabled=True, hide_code=True)
def angstr_sym(x):
    return f'{sym.deg(sym.arg(x)):.1f}º'


@app.cell(disabled=True, hide_code=True)
def sym_measurement(SymAngle, sign, sym_cquad):
    sym_measurement = sym_cquad(1, SymAngle(30).radians, sign)
    return (sym_measurement,)


@app.cell
def latex_measurement(sym_measurement):
    md(f'${sym.latex(sym_measurement)}$')
    return


@app.cell(hide_code=True)
def plot_weights_fun():
    # comp_list = ['straight', 'crossed', 'c2', 'c3', 
    #              'c2a', 'c2b', 'c3a', 'c3b', 'w']
    # comp_i = {comp: i for i, comp in enumerate(comp_list)}
    # comp_s = {i: comp for i, comp in enumerate(comp_list)}
    def plot_weights(data, selections):
        size = 400
        if selections is None or not selections:
            return None

        # sel_i = r_[selections]
        # print(f'{sel_i=}')
        # print(f'{data=}')
        sel_data = [data[comp] for comp in selections]
        # sel_data = array(data)[sel_i]
        sel_comps = tuple(selections)
        npoints = len(selections)

        plot_frame = pd.DataFrame({
            'parallel': np.array(x.real for x in sel_data),
            'perpendicular': np.array(x.imag for x in sel_data), 
            'component': sel_comps})

        highlight = alt.selection_point(
            fields=["component"], bind='legend')
        base = alt.Chart(plot_frame)
        points = base.mark_rule().encode(
            # strokeWidth=alt.value(1),
            strokeWidth=alt.when(
                ~highlight).then(alt.value(1)).
                otherwise(alt.value(3)),
            x2=alt.datum(0.0),
            x=alt.X('parallel', axis=alt.Axis(title='Parallel'), 
                    scale=alt.Scale(domain=[-1.1,1.1])),
            y2=alt.datum(0.0),
            y=alt.Y('perpendicular', axis=alt.Axis(title='Perpendicular'),
                    scale=alt.Scale(domain=[-1.1,1.1])),
            color=alt.Color('component:N', sort=sel_comps)).add_params(highlight)
        labels = base.mark_text(
            align='left',
            baseline='middle',
            dx=7).encode(
            x='parallel:Q',
            y='perpendicular:Q',
            color=alt.Color('component:N', sort=sel_comps))

        final_chart = (points + labels).properties(
            title='Quantish Weights',
            width='container',
            height=size)
        return final_chart
    md('### plot_weights')
    return (plot_weights,)


@app.cell(disabled=True, hide_code=True)
def _():
    def sym_prob(cw):
        """probability of a complex-valued weight"""
        # print(f'prob({cw})={abs(cw)**2}')
        return abs(cw)**2
    md('### sym_prob')
    return (sym_prob,)


@app.cell
def prob_fun():
    def prob(cw):
        """probability of a complex-valued weight"""
        # print(f'prob({cw})={abs(cw)**2}')
        return abs(cw)**2
    md('### prob')
    return (prob,)


@app.cell(hide_code=True)
def topo_sort(parse_position):
    def topo_sort(links):
        sorter = TopologicalSorter()
        sources = defaultdict(list)
        for k, v in links.items():
            source = parse_position(k)
            dest = parse_position(v)
            if isinstance(source, str):
                sorter.add(source)
                gate_name = dest[0]
                sources[gate_name] += [source]
            else:
                gate_name, _ = source
                if isinstance(dest, str):
                    sources[dest] += [gate_name]
                else:
                    dest_gate_name, _ = dest
                    sources[dest_gate_name] += [gate_name]
        for dest, sources in sources.items():
            sorter.add(dest, *sources)
        order = sorter.static_order()
        return list(order)
    md('### topo_sort')
    return (topo_sort,)


@app.cell(hide_code=True)
def parse_position(SEP):
    def parse_position(pos:str):
        # print(f'{pos=}')
        parts = pos.split(SEP)
        if len(parts) == 1:
            return parts[0]
        else:
            return parts
    md('### parse_position')
    return (parse_position,)


if __name__ == "__main__":
    app.run()
