import random
from collections import defaultdict
import numpy as np
from multiworld.config_space import ConfigSpace
import multiworld.qnumber as qn
from multiworld.util import select, normalize_list, enough

def run_paths(initial_point, final_points, n_trials):
    histogram = defaultdict(int)
    rejected = set()
    for trial in range(n_trials):
        cur_point = initial_point
        print('#', end='')
        while len(cur_point.successors) > 0:
            successor_list = [point for point in cur_point.successors
                              if np.all([enough(abs(p.particle.weight), qn.ZERO_THRESHOLD) for p in point.pcvals.values()])]
            successor_weights = [abs(succ.weight) for succ in successor_list]
            selection_point = random.random()
            chosen = select(successor_weights, selection_point)
            print('.', end='')
            cur_point = successor_list[chosen]
        if cur_point in final_points:
            histogram[cur_point.key] += 1
        else:
            rejected.add(cur_point)
            histogram['other'] += 1
    print('histogram done')
    return histogram