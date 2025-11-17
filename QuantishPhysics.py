import marimo

__generated_with = "0.16.5"
app = marimo.App(width="full", app_title="Quantish Physics")


@app.cell(hide_code=True)
def _():
    import marimo as mo
    from marimo import md
    from quantish.angle import Angle
    from quantish.gate import FredkinGate
    from quantish.particle import Particle
    from quantish.sink import Sink
    from quantish.qnumber import Real
    from quantish.marimo_helpers import measure_many, plot_weights, load_models, load_selected_model
    from quantish.visualizations import diagram
    from quantish.simulation import Simulation
    from pathlib import Path
    import yaml
    return (
        Angle,
        FredkinGate,
        Particle,
        Path,
        Real,
        Simulation,
        Sink,
        diagram,
        load_models,
        load_selected_model,
        md,
        measure_many,
        mo,
        plot_weights,
        yaml,
    )


@app.cell(hide_code=True)
def _(mo):
    config_ui = mo.ui.dictionary(elements={
        'title': mo.ui.text(label='Run title', placeholder='--run title--'),
        'symbolic': mo.ui.multiselect(label='Calculation mode',
                                      max_selections=1, value=['Float'],
                                      options=['Symbolic', 'Float']),
        'merge_before_measure': mo.ui.checkbox(label='Before measure'),
        'merge_before_forward': mo.ui.checkbox(label='Before forwarding'),
        'winner_take_all': mo.ui.checkbox(label='Winner take all'),
        'normalize_inputs': mo.ui.checkbox(label='Inputs'),
        'normalize_outputs': mo.ui.checkbox(label='Outputs'),
        'combine_signs': mo.ui.checkbox(label='Combine signs'),
        'control_threshold': mo.ui.number(label='Control:', start=0, stop=0.9),
        'forward_threshold': mo.ui.number(label='Forwarding:', start=0, stop=0.9),
        'presence_threshold': mo.ui.number(label='Presence:', start=0, stop=0.9),
    })
    return (config_ui,)


@app.cell(hide_code=True)
def _(config_ui, md):
    md(rf"""
    ## Configuration

    - {config_ui['title']}

    - {config_ui['symbolic']}

    - Merge:

        -  {config_ui['merge_before_measure']}

        -  {config_ui['merge_before_forward']}

        -  {config_ui['combine_signs']}

        -  {config_ui['winner_take_all']}

    - Normalize:

        - {config_ui['normalize_inputs']}

        - {config_ui['normalize_outputs']}

    - Thresholds
        - {config_ui['control_threshold']}

        -  {config_ui['forward_threshold']}

        -  {config_ui['presence_threshold']}
    """)
    return


@app.cell(hide_code=True)
def _(config_ui, gates, links, particles, phases):
    qconfig = {
        'title': config_ui['title'].value,
        'variables': {},
        'links': list(links.values())[0],
        'phases': list(phases.values())[0],
        'particles': particles,
        'gates': gates,
        'symbolic': config_ui['symbolic'].value[0] == 'Symbolic',
        'winner_take_all': config_ui['winner_take_all'].value,
         'merge': {
             'before_measure': config_ui['merge_before_measure'].value,
             'before_forwarding': config_ui['merge_before_forward'].value,
             'combine_signs': config_ui['combine_signs'].value,
         },
        'normalize_weights': {
            'input': config_ui['normalize_inputs'].value,
            'output': config_ui['normalize_outputs'].value, 
        },
        'probability_threshold': {
            'control': config_ui['control_threshold'].value, 
            'forwarding': config_ui['forward_threshold'].value, 
            'presence': config_ui['presence_threshold'].value,
        }
    }
    qconfig
    return (qconfig,)


@app.cell
def _(Angle, Real):
    angles = {
        'theta30': Angle(30),
        'theta20': Angle(20),
        'theta37': Angle(Real('acos(4/5)', mode='Symbolic'), unit='radians'),
        'theta0': Angle(0),
        'theta90': Angle(90)
    }
    return (angles,)


@app.cell
def _(Gate, angles):
    gates = {
        'g0': Gate('g0', angles['theta0']),
        'g1': Gate('g1', angles['theta37']),
        'g2': Gate('g2', angles['theta37']),
        'g3': Gate('g3', angles['theta0']),
        'g4': Gate('g4', angles['theta0']),
        'g5': Gate('g5', angles['theta20']),
        'g6': Gate('g6', angles['theta20']),
        'g30': Gate('g30', angles['theta30']),
        'g90': Gate('g90', angles['theta90'])
    }
    return (gates,)


@app.cell
def _(Particle):
    particles = {
        'control1': Particle('control1', weight=0, sign=1),
        'control2': Particle('control2', weight=0, sign=1),
        'p1': Particle('p1', weight=1, sign=1),
        'p1m': Particle('p1m', weight=1, sign=-1),
        'pm1': Particle('pm1', weight=-1, sign=1),
        'pm1m': Particle('pm1m', weight=-1, sign=-1),
        'peye': Particle('peye', weight=1j, sign=1),
        'peyem': Particle('peyem', weight=1j, sign=-1),
        'pmeye': Particle('pmeye', weight=-1j, sign=1),
        'pmeyem': Particle('pmeyem', weight=-1j, sign=-1),
        'p2': Particle('p2', weight=1, sign=1),
        'p3': Particle('p3', weight=1, sign=1),
        'p90': Particle('p90', weight=1j, sign=1)
    }
    return (particles,)


@app.cell
def _(gates, particles):
    particles['p90'], gates['g1']
    return


@app.cell
def phases(yaml):
    phases = yaml.safe_load("""
    phases:
       prepare: [g1, g2]
       couple: [g3, g4]
       split: [g5, g6]
    # phases:
    #     run: [g1, g2]
    """)
    phases
    return (phases,)


@app.cell(hide_code=True)
def config_file(Path, mo):
    config_files = mo.ui.file_browser(
        label='config file',
        multiple=True, filetypes=['.yaml', '.yml'],
        initial_path=Path('models'))
    config_files
    return (config_files,)


@app.cell
def load_models_button(mo):
    load_models_button = mo.ui.run_button(label='LOAD MODELS')
    load_models_button
    return (load_models_button,)


@app.cell
def load_models(config_files, load_models, load_models_button, mo):
    mo.stop(output='Press LOAD MODELS to load selected model files', predicate=not load_models_button.value)
    all_models = load_models(config_files)
    return (all_models,)


@app.cell
def select_model(all_models, mo):
    try:
        model_selector = mo.ui.multiselect(label='Select model to instantiate:', 
                                           max_selections=1, options=all_models.keys())
        model_selector
    except NameError:
        pass
    return (model_selector,)


@app.cell
def _(model_selector):
    model_selector
    return


@app.cell
def loaded_model(all_models, config_ui, load_selected_model, model_selector):
    try:
        selected = model_selector.value
        loaded_model = load_selected_model(all_models, selected, config_ui.value)
        print(loaded_model)
    except NameError:
        pass
    return (loaded_model,)


@app.cell
def _(config_ui):
    config_ui.value
    return


@app.cell(hide_code=True)
def show_objects(angles, config_ui, gates, md, mo, particles):
    def _():
        calc_str = f'{config_ui['symbolic'].value[0]}'
        pstrs = '\n'.join([rf'&{x}\\' for x in particles.values()])
        gstrs = '\n'.join([rf'&{x}\\' for x in gates.values()])
        return mo.left(md(rf"""
    $$
    \begin{{align*}}
    \text{{Calculation mode}}&=\text{{{calc_str}}}&\\
    \text{{Angles}}&\\
    &\theta30={angles['theta30']}\\
    &\theta20={angles['theta20']}\\
    &\theta37={angles['theta37']}\\
    \text{{Particles}}&\\
    {pstrs}
    \text{{Gates}}&\\
    {gstrs}
    \end{{align*}}
    $$
    """))
    _()
    return


@app.cell(hide_code=True)
def measure_parts(md):
    measure_parts = ['c2a', 'c2b', 'c3a', 'c3b']
    md(rf"measure_parts={measure_parts}")
    return (measure_parts,)


@app.cell(hide_code=True)
def _(Particle, gates, md, measure_parts, mo, particles):
    mp = particles['p1']
    mg = gates['g30']
    mpresult = mg.measure2(mp)
    mpdict = {k: v.v for k, v in zip(measure_parts, mpresult)}
    mpresult2 = mg.measure(Particle('pc2b', mpdict['c2b'], sign=-1))
    mp2dict = {k: v.v for k, v in zip(measure_parts, mpresult2)}
    mpstr = '\n'.join([f'{k}&=&{v:+.2f}\\\\' for k, v in mpdict.items()])
    mp2str = '\n'.join([f'{k}&=&{v:+.2f}\\\\' for k, v in mp2dict.items()])

    mo.left(md(rf"""
    ### {mp} through {mg}
    $$
    \begin{{align*}}
    {mpstr}
    \\\\
    {mp2str}
    \end{{align*}}
    $$
    """))
    return mg, mp, mpdict, mpresult


@app.cell
def _(mpdict):
    mpdict['c2b']
    return


@app.cell
def _(p1mp):
    p1mp
    return


@app.cell(hide_code=True)
def _(Particle, md, mo, mpresult, particles):
    _p1 = particles['p1']
    p1mp = [Particle('p1', w, s) for w, s in zip(mpresult, [_p1.sign, -_p1.sign, _p1.sign, -_p1.sign])]

    p1str = '\\\\\n'.join([f'&{x}' for x in p1mp])
    mo.left(md(rf"""
    $$
    \begin{{align*}}
    {p1str}\\
    \end{{align*}}
    $$
    """))
    return (p1mp,)


@app.cell
def _(gates, measure_many, p1mp, qconfig):
    p3outs, p3sinks = measure_many(gate=gates['g1'], controls=None, uppers=p1mp[:2], lowers=p1mp[2:], udest='g3.control', config=qconfig)
    p3outs, p3sinks
    return


@app.cell
def _(gates, particles):
    [f'{x:.2f}' for x in gates['g2'].measure(particles['p2'])]
    return


@app.cell
def links(yaml):
    links = yaml.safe_load("""
    # links:
    #    control1: g1.control
    #    p1: g1.upper
    #    g1.control: g2.control
    #    g1.upper: g2.upper
    #    g1.lower: g2.lower
    links:
       control1: g1.control
       control2: g2.control
       p1: g1.upper
       p2: g2.upper
       p3: g3.upper
       g1.upper: g3.control
       g1.lower: g5.lower
       g2.upper: g4.control
       g2.lower: g6.lower
       g3.control: g5.upper
       g3.upper: g4.upper
       g3.lower: g4.lower
       g4.control: g6.upper
    """)
    list(links.values())[0]
    return (links,)


@app.cell(hide_code=True)
def run_button(md, mo):
    run_button = mo.ui.run_button(label='RUN')
    # def set_run_enabled(_):
    #     run_button.disabled = False
    # init_sim = mo.ui.run_button(label='INIT SIM', on_change=set_run_enabled)
    md(f'{run_button}')
    return (run_button,)


@app.cell(hide_code=True)
def sim(Simulation, loaded_model):
    try:
        sim = Simulation(loaded_model)
        # sim.gates, sim.particles, sim.phases, sim.links
    except NameError:
        pass
    return (sim,)


@app.cell(hide_code=True)
def run_sim(Sink, diagram, mo, run_button, sim):
    # mo.stop(output='Press INIT SIM button to initialize simulation', predicate=not init_sim.value)
    # print('INIT SIM was pressed')
    # diag = diagram(sim, has_run=False)
    # init_sim.label = 'Initialized'
    # run_button.disabled = False
    mo.stop(output='Press RUN button to run simulation with current settings', predicate=not run_button.value)
    # print('after stop')
    simresult, result_particles = sim.propagate_weights()
    for _pname, _particle in result_particles.items():
        simresult[_pname] = Sink(_pname, initial_values=[_particle])
    rr0 = {x.name: list(x.value.values())[0] for x in simresult.values() if len(x.value.values()) > 0 and list(x.value.values())[0].name != 'temp' and list(x.value.values())[0].weight != 0}
    rr = {f'{k}: {v.name}': v.weight.v for k, v in rr0.items()}

    mo.mermaid(f'{diagram(sim, has_run=True)}')
    return rr, rr0, simresult


@app.cell
def _(simresult):
    simresult
    return


@app.cell(hide_code=True)
def _(md, mo, rr0, sim):
    _rrstr = '\n'.join([rf'&\text{{{k}}}:&\hspace*{{1em}}&{v}\\' for k, v in rr0.items()])
    mo.left(md(rf"""
    ## Results for {sim.title}
    $$
    \begin{{align*}}
    {_rrstr}
    \end{{align*}}
    $$
    """))
    # print(_rrstr)
    return


@app.cell
def _():
    # rr0 = {x.name: list(x.value.values())[0] for x in result_sinks.values() if len(x.value.values()) > 0 and list(x.value.values())[0].name != 'temp' and list(x.value.values())[0].weight != 0}
    # rr = {f'{k}: {v.name}': v.weight.v for k, v in rr0.items()}
    # rr
    return


@app.cell
def _(loaded_model, plot_weights, rr):
    plot_weights(data=rr, title=f'Results for {loaded_model["title"]}', selections=list(rr.keys()))
    return


@app.cell
def _(mg, mp, mpdict, plot_weights):
    plot_weights(mpdict, ['c2a', 'c2b', 'c3a', 'c3b'], title=f'{mp} -> {mg}')
    return


@app.cell
def _():
    import math as m
    import cmath as cm
    def cpair(w, theta):
        """basic weight rotation with trig scaling"""
        twist = theta - cm.pi/2
        wplus = w * cm.cos(theta)* cm.exp(1j * theta)
        wminus = w * cm.sin(theta) * cm.exp(1j * twist)
        return wplus, wminus

    return cm, cpair, m


@app.cell
def _(cm):
    def cpair2(w, theta):
        c2a = w * cm.cos(theta)**2
        c2b = w * 1j * cm.cos(theta) * cm.sin(theta)
        c3a = w * cm.sin(theta)**2
        c3b = w * -1j * cm.sin(theta) * cm.cos(theta)
        return c2a+c2b, c3a+c3b

    return (cpair2,)


@app.cell
def _(cpair2, m):
    cpair2(1, m.radians(30))
    return


@app.cell
def _(cpair, m):
    cpair(1, m.radians(30))
    return


@app.cell
def _(cpair, m):
    cp1 = cpair(0.43, m.radians(30))
    cp2 = cpair(cp1[0], -m.radians(30))
    cp3 = cpair(cp1[1], -m.radians(30))
    f'{cp1[0]:+.2f}, {cp1[1]:+.2f}, {cp2[0]:+.2f}, {cp2[1]:+.2f}, {cp3[0]:+.2f}, {cp3[1]:+.2f}'
    return


@app.cell
def _(cpair2, m):
    cp21 = cpair2(0.43, m.radians(30))
    cp22 = cpair2(cp21[0], -m.radians(30))
    cp23 = cpair2(cp21[1], -m.radians(30))
    f'{cp21[0]:+.2f}, {cp21[1]:+.2f}, {cp22[0]:+.2f}, {cp22[1]:+.2f}, {cp23[0]:+.2f}, {cp23[1]:+.2f}'
    return


@app.cell
def _(cpair, m):
    xp1 = cpair(0.43j, m.radians(30))
    xp2 = cpair(xp1[0], -m.radians(30))
    xp3 = cpair(xp1[1], -m.radians(30))
    f'{xp1[0]:+.2f}, {xp1[1]:+.2f}, {xp2[0]:+.2f}, {xp2[1]:+.2f}, {xp3[0]:+.2f}, {xp3[1]:+.2f}'
    return


@app.cell
def _(cpair, m):
    xp21 = cpair(0.43j, m.radians(30))
    xp22 = cpair(xp21[0], -m.radians(30))
    xp23 = cpair(xp21[1], -m.radians(30))
    f'{xp21[0]:+.2f}, {xp21[1]:+.2f}, {xp22[0]:+.2f}, {xp22[1]:+.2f}, {xp23[0]:+.2f}, {xp23[1]:+.2f}'
    return


@app.cell
def _(cm, m):
    (0.43) * cm.cos(m.radians(30))**2, (0.43) * cm.sin(m.radians(30))**2
    return


@app.cell
def _(cm, m):
    (0.43j) * cm.cos(m.radians(30))**2, (0.43j) * cm.sin(m.radians(30))**2
    return


if __name__ == "__main__":
    app.run()
