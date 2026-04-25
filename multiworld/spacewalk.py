import random
from collections import defaultdict
import numpy as np
from multiworld.config_space import ConfigSpace
from multiworld.particle import Particle
import multiworld.qnumber as qn
from multiworld.util import select, normalize_list, enough
import logging

log = logging.getLogger('multiworld')

def run_paths(initial_point, final_points, n_trials, sim=None):
    histogram = defaultdict(int)
    rejected = set()
    p3lo = 0
    n_agree = 0
    n_disc = 0
    for trial in range(n_trials):
        # cur_point = initial_point
        # print('#', end='')
        candidates = list(initial_point.successors)
        for input_step in range(sim.result_space.max_step):
            # print(f'step {step}:')
            # successor_list = [point for point in cur_point.successors
            #                   if np.all([enough(abs(p.particle.weight), qn.ZERO_THRESHOLD) for p in point.pcvals.values()])]
            # successor_list = list(cur_point.successors)
            assert np.all(point.step == input_step+1 for point in candidates)
            uppers = []
            lowers = []
            orphans = []
            upper_indexes = []
            lower_indexes = []
            orphan_indexes = []
            for i, point in enumerate(candidates):
                active_pcvs = [pcv for pcv in point.pcvals.values() if pcv.particle.name in sim.step_particles[input_step]]
                for pcv in active_pcvs:
                    if pcv.pcoord.position.origin.port == 'upper':
                        uppers.append(pcv)
                        upper_indexes.append(i)
                    elif pcv.pcoord.position.origin.port == 'lower':
                        lowers.append(pcv)
                        lower_indexes.append(i)
                    else:
                        orphans.append(pcv)
                        orphan_indexes.append(i)
            upper_composite = Particle.merge([u.particle for u in uppers], combine_signs=True)[0]
            lower_composite = Particle.merge([l.particle for l in lowers], combine_signs=True)[0]
            upper_lower = [upper_composite, lower_composite]
            chosen = ['upper', 'lower'][select([p.probability for p in upper_lower], random.random())]
            # cur_point = upper_lower[chosen]
            if chosen == 'upper':
                chosen_indexes = upper_indexes
            else:
                chosen_indexes = lower_indexes
            next_candidate_sets = [candidates[i].successors for i in chosen_indexes]
            next_candidates = list(set().union(*next_candidate_sets))
            if len(next_candidates) == 0:
                break
            else:
                candidates = next_candidates
        if trial < 10:
            log.debug(f'{trial=}')
            for candidate in candidates:
                log.debug(f'   {candidate=}')
        finalists = [point for point in candidates if point in final_points]

        for finalist in finalists:
            if finalist.step == sim.result_space.max_step:
                pcvals = list(finalist.pcvals.values())
                pcvp1, pcvp2, pcvp3 = pcvals
                if enough(abs(pcvp3.particle.weight), qn.ZERO_THRESHOLD):
                    if pcvp3.pcoord.position.origin.port != 'upper':
                        p3lo += 1
                    else:
                        if pcvp1.pcoord.position.origin.port == pcvp2.pcoord.position.origin.port:
                            n_agree += 1
                        else:
                            n_disc += 1
                    histogram[finalist.key] += 1
            else:
                rejected.add(finalist)
                histogram['other'] += 1
    log.info('histogram done')
    log.info(f'discrepancy rate = {n_disc / (n_agree + n_disc)}')
    return histogram