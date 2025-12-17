
def enough_ge(x, threshold):
    if not x: return False
    flx = float(x)
    tx = float(threshold)
    # return (not np.isclose(flx, 0)) and flx >= threshold
    return flx >= tx

def enough_g(x, threshold):
    if not x: return False
    flx = float(x)
    tx = float(threshold)
    # return (not np.isclose(flx, 0)) and flx >= threshold
    return flx > tx

def main():
    p_angles = [(x, qn.qify(f'(pi/36)*(({x}*5)/10)'), qn.qify(f'(pi/2) - ((pi/36)*(({x}*5)/10))')) for x in range(37)]
    pa1 = [(x[1].degrees, x[2].degrees, x[1].radians.sin**2, 1-x[2].radians.sin**2) for x in p_angles]
    pa2 = [(x[1].degrees, qn.Complex.rotate(1, x[1])) for x in p_angles]

    aa_probs = {}
    for aa in p_angles:
        aastr = f'{aa[1].degrees:.2f}'
        # g = FredkinGate(f'g{aastr}', theta=aa[1])
        _pp = Particle(f'p{aastr}', weight=qn.Complex.rotate(1, aa[1]), sign=1)
        aa_probs[aastr] = (_pp.weight, _pp.probability, aa[2].sin**2, _pp.probability-aa[2].sin**2)

    aap_diffs = {f'{k}º': aa_probs[k][1] - aa_probs[list(aa_probs.keys())[i+1]][1] for i, k in enumerate(aa_probs.keys()) if i < len(aa_probs.keys())-1}

    assert sum(aap_diffs.values()) == 1

if __name__ == '__main__':
    main()