from quantish.gate import FredkinGate
from quantish.particle import Particle
# from quantish.sink import Sink
from quantish.qnumber import Real, probability
from quantish.util import enough
from collections import defaultdict
import marimo as mo
import altair as alt
import numpy as np
import pandas as pd
import yaml

# def measure_many(gate: FredkinGate, controls=None, uppers=None, lowers=None,
#                  cdest=None, udest=None, ldest=None,
#                  config=None):
#
#     # def merge_inputs(group):
#     #     pluses = Particle.merge([x for x in group if x.sign > 0])
#     #     pluses = [] if not pluses else [pluses]
#     #     minuses = Particle.merge([x for x in group if x.sign < 0])
#     #     minuses = [] if not minuses else [minuses]
#     #     group = pluses + minuses
#     #     if group and combine_signs:
#     #         group = Particle.merge(group)
#     #         group = [] if not group else [group]
#     #     return group
#
#     if config is None:
#         merge_before_measure = False
#         merge_before_forward = False
#         combine_signs = False
#         combine_names = True
#         # normalize_inputs = False
#         normalize_outputs = False
#         control_threshold = Real(0)
#         forwarding_threshold = Real(0)
#         presence_threshold = Real(0)
#     else:
#         merge_before_measure = (
#             config.get('merge', {'before_measure': False}).get('before_measure'))
#         merge_before_forward = (
#             config.get('merge', {'before_forwarding': False}).get('before_forwarding'))
#         combine_signs = config.get('merge', {'combine_signs': False}).get('combine_signs')
#         combine_names = config.get('merge', {'combine_names': False}).get('combine_names')
#         normalize_inputs = config.get('normalize_weights', {}).get('input', False)
#         normalize_outputs = config.get('normalize_weights', {}).get('output', False)
#         control_threshold = Real(config.get('control_threshold', {}).get('control', 0))
#         forwarding_threshold = Real(config.get('forward_threshold', {}).get('forwarding', 0))
#         presence_threshold = Real(config.get('presence_threshold', {}).get('presence', 0))
#
#     ctrl_pos = f'{gate.name}.control'
#     upper_pos = f'{gate.name}.upper'
#     lower_pos = f'{gate.name}.lower'
#
#     output_dict = defaultdict(list)
#     sinks = {}
#
#     # controls = controls or [Particle('temp', 0, 1)]
#     # uppers = uppers or []
#     # lowers = lowers or []
#     # if merge_before_measure: controls = merge_inputs(controls)
#     # for control in controls:
#     #     # output_dict[ctrl_pos].append(
#     #     #     Sink(ctrl_pos, ctrl_pos, presence_threshold=presence_threshold, initial_values=[control]))
#     #     if cdest is not None:
#     #         output_dict[cdest] += [control]
#     #     swap = enough(control.probability, control_threshold)
#     #     if merge_before_measure:
#     #         uppers = merge_inputs(uppers)
#     #         lowers = merge_inputs(lowers)
#     #     up_outs = []
#     #     lo_outs = []
#     #     # out_dict = defaultdict(list)
#     #     for inputs, in_wire in [(uppers, 'upper'), (lowers, 'lower')]:
#     #         for p_in in inputs:
#     #             if p_in.probability > 0:  # never zero
#     #                 p_outs = list(gate.measure(p_in))
#     #                 if normalize_outputs:
#     #                     for i in range(len(p_outs)):
#     #                         p_outs[i] *= 1 / p_in.weight
#     #                 signs = [p_in.sign, -p_in.sign, p_in.sign, -p_in.sign]
#     #                 parts = [f'c{parperp}{subc}' for parperp in ['2', '3'] for subc in ['a', 'b']]
#     #                 for i, (sign, part) in enumerate(zip(signs, parts)):
#     #                     weight = p_outs[i]
#     #                     if enough(probability(weight), presence_threshold):
#     #                         p_out = Particle(p_in.name, p_outs[i], sign)
#     #                         output_dict[f'{in_wire}_{part}'] += [p_out]
#     #     up_outs += output_dict['upper_c2a'] + output_dict['upper_c2b'] + output_dict['lower_c3a'] + output_dict['lower_c3b']
#     #     lo_outs += output_dict['upper_c3a'] + output_dict['upper_c3b'] + output_dict['lower_c2a'] + output_dict['lower_c2b']
#     #     if swap:
#     #         up_outs, lo_outs = lo_outs, up_outs
#     #     for (out_pos, dest, outs, msg) in zip(
#     #             (upper_pos, lower_pos),
#     #             (udest, ldest),
#     #             (up_outs, lo_outs),
#     #             ('upper', 'lower')):
#     #         if outs is not None:
#     #             sink = Sink(out_pos, out_pos, presence_threshold=presence_threshold)
#     #             sinks[out_pos] = sink
#     #             outputs = []
#     #             for pval in outs:
#     #                 if pval.name != 'temp' and enough(probability(pval.weight), forwarding_threshold):
#     #                     outputs.append(Particle(pval.name, pval.weight, pval.sign))
#     #             if outputs:
#     #                 if merge_before_forward:
#     #                     for sign_test, sign_str in [('__gt__', 'plus'), ('__lt__', 'minus')]:
#     #                         merged = Particle.merge([x for x in outputs if getattr(x, sign_test)(0)])
#     #                         if merged is not None and enough(merged.probability, forwarding_threshold):
#     #                             output_dict[dest].append(merged)
#     #                             sink.add([merged])
#     #                 else:
#     #                     sink.add(outputs)
#     #                     for pout in outputs:
#     #                         if dest is not None:
#     #                             output_dict[dest].append(pout)
#     # return output_dict, sinks

load_fields = ['gates', 'particles', 'links', 'phases', 'title']

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
                'selector': config_ui['selector'],
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
