from multiworld.gate import FredkinGate
from multiworld.particle import Particle
# from multiworld.sink import Sink
from multiworld.qnumber import Real, probability
from multiworld.util import enough
from collections import defaultdict
import marimo as mo
import altair as alt
import numpy as np
import pandas as pd
import yaml

load_fields = ['gates', 'particles', 'links', 'run_stages', 'title']

def extract_config(cf):
    newconfig = {}
    for section in load_fields:
        newconfig[section] = cf[section]
    return newconfig

def load_models(config_files):
    results = {}
    for file_info in config_files.value:
        with open(file_info.path, 'r') as f:
            full_config = yaml.safe_load(f)
        extracted = extract_config(full_config)
        results[file_info.path.stem] = extracted
    return results

def load_selected_model(configs, selected, config_ui):
    if configs is not None:
        if selected is not None and len(selected) > 0:
            sel_name = selected[0]
            config = configs[sel_name]
            config['merge'] = {
                'before_measure': config_ui['merge_before_measure'],
                'before_forwarding': config_ui['merge_before_forward'],
                'combine_signs': config_ui['combine_signs'],
                'combine_names': config_ui['combine_names']
            }
            config['probability_threshold'] = {
                'control': config_ui['control_threshold'],
                'forwarding': config_ui['forward_threshold'],
                'presence': config_ui['presence_threshold']
            }
            config['normalize_weights'] = {
                'input': config_ui['normalize_inputs'],
                'output': config_ui['normalize_outputs']
            }
            # config['title'] = config_ui['title']
            config['symbolic'] = config_ui['symbolic'] == 'Symbolic'
            config['variables'] = {}
            print(f'{config=}')
            return config

def plot_weights(data, selections, title='Quantish Weights'):
    chart_size = 600
    if selections is None or not selections:
        return None

    sel_data = [data[comp] for comp in selections]
    sel_components = tuple(selections)
    npoints = len(selections)

    limit = max(max([max(abs(x.real), x.imag) for x in data.values()]), 1) * 1.05
    limits = [-limit, limit]

    ncircle = 100
    circle_data = np.linspace(0, 2*np.pi, ncircle)
    source = pd.DataFrame({
        'x': np.cos(circle_data),
        'y': np.sin(circle_data),
        'sequence': range(ncircle)
    })
    plot_frame = pd.DataFrame({
        'parallel': np.array(x.real for x in sel_data),
        'perpendicular': np.array(x.imag for x in sel_data),
        'component': sel_components})

    unit_circle = alt.Chart(source).mark_line(strokeWidth=0.5).encode(
        x=alt.X('x'),
        y=alt.Y('y'),
        order='sequence'
    )

    sel_line = alt.selection_point(name="sel_line", on="click", bind='legend', empty=False)
    sel_leg = alt.selection_point(name='sel_leg',
        fields=["component"], bind='legend', empty=False)
    high_line = alt.selection_point(name="high_line", on="pointerover", empty=False)
    # sel_some = sel_line | sel_leg
    # sel_any_condition = sel_line | sel_leg | high_line
    # sel_any = alt.when(sel_line).then(alt.value(5)).when(sel_leg).then(alt.value(4)).otherwise(alt.value(1))
    stroke_width = \
        alt.when(sel_leg).then(alt.value(5)).\
            when(sel_line).then(alt.value(4)).\
            when(high_line).then(alt.value(3)).\
            otherwise(alt.value(1))

    base = alt.Chart(plot_frame)
    points = base.mark_rule().encode(
        x2=alt.datum(0.0),
        x=alt.X('parallel', axis=alt.Axis(title='Parallel'),
                scale=alt.Scale(domain=limits)),
        y2=alt.datum(0.0),
        y=alt.Y('perpendicular', axis=alt.Axis(title='Perpendicular'),
                scale=alt.Scale(domain=limits)),
        strokeWidth=stroke_width,
        tooltip=['component', 'parallel', 'perpendicular'],
        color=alt.Color('component:N', sort=sel_components),
    ).add_params(sel_leg, sel_line, high_line)
    labels = base.mark_text(
        align='left',
        baseline='middle',
        dx=7).encode(
        x='parallel:Q',
        y='perpendicular:Q',
        color=alt.Color('component:N', sort=sel_components))

    almost_final_chart = (points + labels + unit_circle).properties(
        title=title,
        height=chart_size,
        width=chart_size
    ).interactive()
    final_chart = mo.ui.altair_chart(
        chart=almost_final_chart,
        chart_selection=False,
        legend_selection=False
    )
    return final_chart
