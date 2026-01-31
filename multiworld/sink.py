from collections import defaultdict
import json
import logging

from multiworld.util import wstr
from multiworld.particle import Particle

log = logging.getLogger('multiworld')

## This module is more or less obsolete now

class Sink:
    def __init__(self, name, position, presence_threshold=0, initial_values=None,
                 precision=2, combine_signs=True, combine_names=True):
        self.name = f'{name}@{position}'
        log.debug(f'NEW SINK: {self.name}, {presence_threshold=}, {initial_values=}, {combine_signs=}, {combine_names=}')
        self.precision = precision
        self.trace = defaultdict(list)
        self.pnames = set()
        self.values = {}
        self.combine_signs = combine_signs
        self.combine_names = combine_names
        self.presence_threshold = presence_threshold
        if initial_values is not None:
            self.add(initial_values)

    def __repr__(self):
        if len(self.values) == 0:
            return f'EMPTY'
        else:
            sink_vals = list(self.values.values())
            return f'{sink_vals}'

    @property
    def value(self):
        return list(self.values.values())

    @property
    def vstr(self):
        vals = []
        for p in self.values.values():
            if p.name[:4] == 'null':
                vals += ['None']
                continue
            # if enough(p.probability, self.presence_threshold):
            ss = f"{'+' if p.sign > 0 else '-'}"
            pstr = f'%.{self.precision}f'
            probstr = pstr % p.probability
            p_short_name = p.name.split('>')[0]
            vals += [f'{ss}{p_short_name} {wstr(p.weight, precision=self.precision)}|{probstr}']
        if len(vals) == 0:
            return '0'
        else:
            return ', '.join(vals)

    def summary_probability(self)->float:
        if len(list(self.values.values())) > 0:
            return float(Particle.merge(self.values.values()).probability)
        else:
            return 0

    def add(self, new_particles):
        log.debug(f'SINK {self.name}: ADD {new_particles}')
        def add_some(particles):
            if self.combine_names:
                if self.combine_signs:
                    p_key = lambda particle: '*'
                else:
                    p_key = lambda particle: f'{"+" if particle.sign > 0 else "-"}'
            elif self.combine_signs:
                p_key = lambda particle: particle.ps(name_only=True)
            else:
                p_key = lambda particle: f'{"+" if particle.sign > 0 else "-"}{particle.ps(name_only=True)}'
            for p in particles:
                key = p_key(p)
                if key not in self.values.keys():
                    self.values[key] = p
                    self.trace[key] = [p]
                    log.debug(f'SINK {self.name}: NEW VALUE {p}')
                else:
                    self.trace[key].append(p)
                    prev_particle = self.values[key]
                    before = prev_particle.weight
                    prev_particle += p
                    after = prev_particle.weight
                    # prev_particle.trace = f'{prev_particle.trace}+={p.trace}'
                    self.values[key] = prev_particle
                    log.debug(f'{self.name}: SINK UPDATED VALUE {wstr(before, precision=self.precision)}->{wstr(after, precision=self.precision)}')
        if self.combine_signs:
            add_some(new_particles)
        else:
            pluses = [x for x in new_particles if x.sign > 0]
            minuses = [x for x in new_particles if x.sign < 0]
            add_some(pluses)
            add_some(minuses)

    def vlist(self):
        result = []
        for p in self.values.values():
            sign = int(float(p.sign))
            ss = f'{"+" if sign == 1 else "-"}'
            result.append(
                {f'{ss}{p.name.split('>')[0]}': {'weight': [p.weight.real, p.weight.imag], 'sign': sign, 'probability': float(p.probability)}})
        return result


class SinkEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Sink):
            result = []
            for p in obj.values.values():
                sign = int(float(p.sign))
                result.append({p.name: {'weight': [p.weight.real, p.weight.imag], 'sign': sign, 'probability': float(p.probability)}})
            return result
        return super().default(obj)
