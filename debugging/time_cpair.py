from quantish.gate import FredkinGate
import quantish.qnumber as qn
from quantish.particle import Particle
from timeit import timeit

for mode in ('Float', 'Symbolic'):
    qn.CalcMode.mode = mode
    angle = qn.qify('rad(30)')
    # p_plus = Particle('p', qn.qify(1+0j), 1)
    # p_minus = Particle('p', qn.qify(1+0j), -1)
    one = qn.Complex("1")
    minus_one = qn.Complex(-1)
    p_plus = Particle('p', one, 1)
    p_minus = Particle('p', one, -1)
    # g_basic = FredkinGate('g_basic', angle, alternative_measure=False)
    # g_alt = FredkinGate('g_alt', angle, alternative_measure=True)
    # g_0 = FredkinGate('g_0', angle, alternative_measure='cpair0')
    # g_1 = FredkinGate('g_1', angle, alternative_measure='cpair1')
    # g_2 = FredkinGate('g_2', angle, alternative_measure='cpair2')
    # g_3 = FredkinGate('g_3', angle, alternative_measure='cpair3')
    #
    # m_basic = lambda p: g_basic.measure(p)
    # m_alt = lambda p: g_alt.measure(p)
    # m_0 = lambda p: g_0.measure(p)
    # m_1 = lambda p: g_1.measure(p)
    # m_2 = lambda p: g_2.measure(p)
    # m_3 = lambda p: g_3.measure(p)


    # for meth in (False, True, 'cpair0', 'cpair1', 'cpair2', 'cpair3'):
    #     gate = FredkinGate(f'g_{meth}', angle, alternative_measure=meth)
    #     print(f'{gate=}')
    #     for p in (p_plus, p_minus):
    #         print(f'{p=}')
    #         cpair_method = getattr(getattr(gate.__class__, 'cpair_m'), '__name__')
    #         print(f'{cpair_method=}, {gate.measure(p)=}')
    #         print(timeit(lambda: gate.measure(p), number=10000))
    #     print()

    gate = FredkinGate('g', angle)
    print(f'{gate=}')
    for p in (p_plus, p_minus):
        print(f'{p=}')
        # cpair_method = getattr(getattr(gate.__class__, 'cpair_m'), '__name__')
        print(f'{gate.measure(p)=}')
        print(timeit(lambda: gate.measure(p), number=1))

# for gate in (g_basic, g_alt, g_0, g_1, g_2, g_3):
#     print(f'{gate=}')
#     print(timeit(lambda: gate.measure(gate, p), number=10000))
