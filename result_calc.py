P_UPPER = 0.75
DEPTH = 5
SAMPLES_PER_EXPERIMENT = 32

def calc_total(n_tries, p_upper=P_UPPER, depth=DEPTH, samples_per=SAMPLES_PER_EXPERIMENT):
    n_samples = n_tries * samples_per
    n_upper = round(n_samples * p_upper)
    n_lower = n_samples - n_upper
    if depth > 0:
        if n_upper > 0:
            upper, lower = calc_total(n_upper, p_upper, depth-1, samples_per)
            n_upper += upper
            n_lower += lower
        if n_lower > 0:
            upper, lower = calc_total(n_lower, p_upper, depth-1, samples_per)
            n_upper += upper
            n_lower += lower
    assert n_upper >= 0 and n_lower >= 0
    return n_upper, n_lower