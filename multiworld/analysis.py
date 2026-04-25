# if not sim.sample:
#     result_space, steps_run = sim.run()
#     has_run = True
# else:
#     ## Initial setup
#     fig411 = sim.title == 'Figure 4.11'
#     log.info(f'Running {sim.n_samples} trials')
#     log.info('')
#     log.info('PARTICLES:')
#     for particle in sim.particles.values():
#         log.info(f'   {particle}')
#     log.info('GATES:')
#     for gate in sim.gates.values():
#         log.info(f'   {gate}')
#     histogram = defaultdict(int)
#     angle_counts = defaultdict(int)
#     pair_counts = defaultdict(int)
#     coupled_pair_counts = defaultdict(int)
#     for k in ('ab', 'bc', 'ac'):
#         pair_counts[k] = 0
#         coupled_pair_counts[k] = 0
#     discrepancy_count = 0
#     disc_ab = 0
#     disc_bc = 0
#     disc_ac = 0
#     disc_ba = 0
#     disc_cb = 0
#     disc_ca = 0
#     up5not6 = 0
#     up6not5 = 0
#     lo5not6 = 0
#     lo6not5 = 0
#     coupled_count = 0
#     if epr_stats:
#         epr_histogram = defaultdict(int)
#         epr_histogram['coupled-equal'] = 0
#         epr_histogram['coupled-unequal'] = 0
#         epr_histogram['uncoupled-equal'] = 0
#         epr_histogram['uncoupled-unequal'] = 0
#
#         epr_histogram['coupled-both-upper'] = 0
#         epr_histogram['coupled-both-lower'] = 0
#         epr_histogram['coupled-upper-lower'] = 0
#         epr_histogram['coupled-lower-upper'] = 0
#         epr_histogram['uncoupled-both-upper'] = 0
#         epr_histogram['uncoupled-both-lower'] = 0
#         epr_histogram['uncoupled-upper-lower'] = 0
#         epr_histogram['uncoupled-lower-upper'] = 0
#     if config.config_path == 'fig416plus':
#         fig417a = {}
#         fig417b = {}
#         fig417c = {}
#     global_result = {}
#     w1w3 = None
#     w1w4 = None
#     w2w3 = None
#     w2w4 = None
#     w1w3m = None
#     w1w4m = None
#     w2w3m = None
#     w2w4m = None
#
#     w1aw3 = None
#     w1aw4 = None
#     w2aw3 = None
#     w2aw4 = None
#     w1aw3m = None
#     w1aw4m = None
#     w2aw3m = None
#     w2aw4m = None
#
#     w1aw3a = None
#     w1aw4a = None
#     w2aw3a = None
#     w2aw4a = None
#     w1aw3am = None
#     w1aw4am = None
#     w2aw3am = None
#     w2aw4am = None
#
#     save_level = log.level
#     log.setLevel(logging.WARNING)
#
#     ## Now run all trials
#     for i in tqdm(range(sim.n_samples)):
#         experiment_results = {} # new result each time
#         if config.measure_discrepancy:
#             angle_choices = ['qa', 'qb', 'qc']
#             # angle_choices = ['qa', 'qc']
#             random.shuffle(angle_choices) # this should produce an even distribution for all combinations
#             q1, q2 = angle_choices[:2]
#             angle_counts[q1] += 1
#             angle_counts[q2] += 1
#             pair = None
#             if q1 == 'qa':
#                 if q2 == 'qb':
#                     pair = 'ab'
#                 else:
#                     pair = 'ac'
#             elif q1 == 'qb':
#                 if q2 == 'qc':
#                     pair = 'bc'
#                 else:
#                     pair = 'ba'
#             elif q1 == 'qc':
#                 if q2 == 'qa':
#                     pair = 'ca'
#                 else:
#                     pair = 'cb'
#             pair_counts[pair] += 1
#             config.gates.g5.angle = config.variables[q1]
#             config.gates.g6.angle = config.variables[q2]
#             del sim
#             sim = Simulation(config)
#             assert sim.gates.g5.theta == qify(config.variables[q1])
#             assert sim.gates.g6.theta == qify(config.variables[q2])
#         else:
#             del sim
#             sim = Simulation(config)
#         experiment_results = sim.run()
#         # for stage in sim.run_stages.values():
#         #     stage.run(sim.world_states)
#         g1 = sim.gates.get('g1')
#         g2 = sim.gates.get('g2')
#         g3 = sim.gates.get('g3')
#         g4 = sim.gates.get('g4')
#         g5 = sim.gates.get('g5')
#         g6 = sim.gates.get('g6')
#         g7 = sim.gates.get('g7')
#         g8 = sim.gates.get('g8')
#         if fig411:
#             if g1.output_wire == 'upper':
#                 if g2.output_wire == 'upper':
#                     histogram['411-g2.upper'] += 1
#                 else:
#                     histogram['411-g2.lower'] += 1
#         if config.measure_discrepancy:
#             for gate, var in zip([sim.gates.g5, sim.gates.g6], [q1, q2]):
#                 for angle in ['qa', 'qb', 'qc']:
#                     if var == angle:
#                         if gate.output_wire == 'upper':
#                             histogram[f'{angle}.upper'] += 1
#                         else:
#                             histogram[f'{angle}.lower'] += 1
#         for g in sim.gates.values():
#             if type(g) is FredkinGate:
#                 g_result = g.results
#                 for wire in WIRES:
#                     out_pos = f'{g.name}{SEP}{wire}'
#                     if g_result[wire]:
#                         experiment_results[out_pos] = g_result[wire]
#                     else:
#                         experiment_results[out_pos] = None
#             has_run = True
#         if config.config_path == 'fig49':
#             if experiment_results.get('g2.upper') and experiment_results.get('g3.upper'):
#                 histogram.both_upper += 1
#             if experiment_results.get('g2.lower') and experiment_results.get('g3.lower'):
#                 histogram.both_lower += 1
#             if not (experiment_results.get('g2.upper') or experiment_results.get('g3.upper')):
#                 histogram.neither_upper += 1
#             if not (experiment_results.get('g2.lower') or experiment_results.get('g3.lower')):
#                 histogram.neither_lower += 1
#             if not(experiment_results.get('g2.upper') or experiment_results.get('g3.upper')):
#                 histogram.neither_upper += 1
#             if experiment_results.get('g2.upper') and not experiment_results.get('g3.upper'):
#                 histogram.g2_upper_not_g3_upper += 1
#             if experiment_results.get('g3.upper') and not not experiment_results.get('g2.upper'):
#                 histogram.g3_upper_not_g2_upper += 1
#             if experiment_results.get('g2.lower') and not experiment_results.get('g3.lower'):
#                 histogram.g2_lower_not_g3_lower += 1
#             if experiment_results.get('g3.lower') and not experiment_results.get('g2.lower'):
#                 histogram.g3_lower_not_g2_lower += 1
#         # if config.config_path == 'fig416plus' and experiment_results.get('g4.upper'):
#         #     log.info('coupled')
#         if config.config_path == 'fig416plus' and i == 0:
#             g1uw = Particle.merge(flat_list(sim.gates.g1.port_weights('upper')))
#             g1lw = Particle.merge(flat_list(sim.gates.g1.port_weights('lower')))
#             g2uw = Particle.merge(flat_list(sim.gates.g2.port_weights('upper')))
#             g2lw = Particle.merge(flat_list(sim.gates.g2.port_weights('lower')))
#             g1up_phase = (g1uw and g1uw.weight.phase) or qify('0+0j')
#             g2up_phase = (g2uw and g2uw.weight.phase) or qify('0+0j')
#             log.info(f'upper combined phase: {(g1up_phase + g2up_phase).degrees:.2f}, probabilities: {g1uw.probability:.2f}, {g2uw.probability:.2f}')
#             g1lo_phase = g1lw and g1lw.weight.phase
#             g2lo_phase = g2lw and g2lw.weight.phase
#             if g1lo_phase and g2lo_phase:
#                 log.info(f'lower combined phase: {(g1lo_phase + g2lo_phase).degrees:.2f}, probabilities: {g1lw.probability:.2f}, {g2lw.probability:.2f}')
#             else:
#                 log.info(f'{g1lw=}, {g2lw=}')
#             fig417a.p1 = sim.gates.g1.measure(sim.particles.p1)
#         for k, v in experiment_results.items():
#             if v:
#                 global_result[k] = v
#                 histogram[k] += 1
#         if config.measure_discrepancy or epr_stats:
#             ag1 = {'control': g1.results.control, 'swapping': g1.swapping, 'upper': g1.results.upper, 'lower': g1.results.lower}
#             ag2 = {'control': g2.results.control, 'swapping': g2.swapping, 'upper': g2.results.upper, 'lower': g2.results.lower}
#             ag3 = {'control': g3.results.control, 'swapping': g3.swapping, 'upper': g3.results.upper, 'lower': g3.results.lower}
#             ag4 = {'control': g4.results.control, 'swapping': g4.swapping, 'upper': g4.results.upper, 'lower': g4.results.lower}
#             ag5 = {'control': g5.results.control, 'swapping': g5.swapping, 'upper': g5.results.upper, 'lower': g5.results.lower}
#             ag6 = {'control': g6.results.control, 'swapping': g6.swapping, 'upper': g6.results.upper, 'lower': g6.results.lower}
#             # ag7 = {'control': g7.results.control, 'swapping': g7.swapping, 'upper': g7.results.upper, 'lower': g7.results.lower}
#             # ag8 = {'control': g8.results.control, 'swapping': g8.swapping, 'upper': g8.results.upper, 'lower': g8.results.lower}
#             coupled = g4.output_wire == 'upper' # and (g4.results.upper is not None)
#
#             # Discrepancy occurs when particles end up on different wires (one upper, one lower)
#             if coupled:
#                 coupled_count += 1
#                 if not w1aw3:
#                     g5up = sim.gates.g5.outputs.upper or []
#                     g6up = sim.gates.g6.inputs.upper or []
#                     w1aw3 = (g5up + g6up) or []
#                     w1aw3m = Particle.merge(w1aw3)
#                 if not w2aw3:
#                     g5lo = sim.gates.g5.outputs.lower or []
#                     g6up = sim.gates.g6.inputs.upper or []
#                     w2aw3 = (g5lo + g6up) or []
#                     w2aw3m = Particle.merge(w2aw3)
#                 if not w1aw4:
#                     g5up = sim.gates.g5.outputs.upper or []
#                     g6lo = sim.gates.g6.inputs.upper or []
#                     w1aw4 = (g5up + g6lo) or []
#                     w1aw4m = Particle.merge(w1aw4)
#                 if not w2aw3:
#                     g5lo = sim.gates.g5.outputs.lower or []
#                     g6lo = sim.gates.g6.inputs.upper or []
#                     w2aw3 = (g5lo + g6lo) or []
#                     w2aw3m = Particle.merge(w2aw3)
#
#                 if not w1aw3a:
#                     g5up = sim.gates.g5.outputs.upper or []
#                     g6up = sim.gates.g6.outputs.upper or []
#                     w1aw3a = (g5up + g6up) or []
#                     w1aw3am = Particle.merge(w1aw3a)
#                 if not w2aw3a:
#                     g5lo = sim.gates.g5.outputs.lower or []
#                     g6up = sim.gates.g6.outputs.upper or []
#                     w2aw3a = (g5lo + g6up) or []
#                     w2aw3am = Particle.merge(w2aw3a)
#                 if not w1aw4a:
#                     g5up = sim.gates.g5.outputs.upper or []
#                     g6lo = sim.gates.g6.outputs.lower or []
#                     w1aw4a = (g5up + g6lo) or []
#                     w1aw4am = Particle.merge(w1aw4a)
#                 if not w2aw4a:
#                     g5lo = sim.gates.g5.outputs.lower or []
#                     g6lo = sim.gates.g6.outputs.lower or []
#                     w2aw4a = (g5lo + g6lo) or []
#                     w2aw4am = Particle.merge(w2aw4a)
#
#                 if (not w1w3) and g5.output_wire == 'upper' and g6.output_wire == 'upper':
#                     g5up = sim.gates.g1.weights.upper or []
#                     g6up = sim.gates.g2.weights.upper or []
#                     w1w3 = g5up + g6up
#                     w1w3m = Particle.merge(w1w3)
#                 if (not w2w4) and g5.output_wire == 'lower' and g6.output_wire == 'lower':
#                     g5lo = sim.gates.g1.weights.lower or []
#                     g6lo = sim.gates.g2.weights.lower or []
#                     w2w4 = g5lo + g6lo
#                     w2w4m = Particle.merge(w2w4)
#                 if (not w1w4) and g5.output_wire == 'upper' and g6.output_wire == 'lower':
#                     g5up = sim.gates.g1.weights.upper or []
#                     g6lo = sim.gates.g2.weights.lower or []
#                     w1w4 = g5up + g6lo
#                     w1w4m = Particle.merge(w1w4)
#                 if (not w2w3) and g5.output_wire == 'lower' and g6.output_wire == 'upper':
#                     g5lo = sim.gates.g1.weights.lower or []
#                     g6up = sim.gates.g2.weights.upper or []
#                     w1w4 = g5lo + g6up
#                     w1w4m = Particle.merge(w1w4)
#
#                 for gate, var in zip([sim.gates.g5, sim.gates.g6], [q1, q2]):
#                     for angle in ['qa', 'qb', 'qc']:
#                         if var == angle:
#                             if gate.output_wire == 'upper':
#                                 histogram[f'{angle}.upper_coupled'] += 1
#                             else:
#                                 histogram[f'{angle}.lower_coupled'] += 1
#                 coupled_pair_counts[pair] += 1
#                 discrepancy = g7.output_wire != g8.output_wire
#                 if discrepancy:
#                     discrepancy_count += 1
#                     if q1 == 'qa':
#                         if q2 == 'qb':
#                             disc_ab += 1
#                         else:
#                             disc_ac += 1
#                     elif q1 == 'qb':
#                         if q2 == 'qa':
#                             disc_ba += 1
#                         else:
#                             disc_bc += 1
#                     elif q1 == 'qc':
#                         if q2 == 'qb':
#                             disc_cb += 1
#                         else:
#                             disc_ca += 1
#                     else:
#                         raise RuntimeError(f'invalid value: {q1=}')
#         if epr_stats:
#             if coupled:
#                 # if g4_up and g4_up[0].probability > 0:
#                 if g7.output_wire == 'upper' and g8.output_wire == 'upper':
#                     epr_histogram['coupled-both-upper'] += 1
#                 elif g7.output_wire == 'lower' and g8.output_wire == 'lower':
#                     epr_histogram['coupled-both-lower'] += 1
#                 elif g7.output_wire == 'upper' and g8.output_wire == 'lower':
#                     epr_histogram['coupled-upper-lower'] += 1
#                 elif g7.output_wire == 'lower' and g8.output_wire == 'upper':
#                     epr_histogram['coupled-lower-upper'] += 1
#             #     if experiment_results.get('g5.upper') and experiment_results.get('g6.upper'):
#             #         if np.isclose(float(experiment_results['g5.upper'][0].probability),
#             #                       float(experiment_results['g6.upper'][0].probability)):
#             #             epr_histogram['coupled-equal'] += 1
#             #         else:
#             #             epr_histogram['coupled-unequal'] += 1
#             #     elif experiment_results.get('g5.lower') and experiment_results.get('g6.lower'):
#             #         epr_histogram['coupled-both-lower'] += 1
#             #         if np.isclose(float(experiment_results['g5.lower'][0].probability),
#             #                       float(experiment_results['g6.lower'][0].probability)):
#             #             epr_histogram['coupled-equal'] += 1
#             #         else:
#             #             epr_histogram['coupled-unequal'] += 1
#             #     else:
#             #         epr_histogram['coupled-unequal'] += 1
#             else:
#                 if g7.output_wire == 'upper' and g8.output_wire == 'upper':
#                     epr_histogram['uncoupled-both-upper'] += 1
#                 elif g7.output_wire == 'lower' and g8.output_wire == 'lower':
#                     epr_histogram['uncoupled-both-lower'] += 1
#                 elif g7.output_wire == 'upper' and g8.output_wire == 'lower':
#                     epr_histogram['uncoupled-upper-lower'] += 1
#                 elif g7.output_wire == 'lower' and g8.output_wire == 'upper':
#                     epr_histogram['uncoupled-lower-upper'] += 1
#                 # if experiment_results.get('g5.upper') and experiment_results.get('g6.upper'):
#                 #     epr_histogram['uncoupled-both-upper'] += 1
#                     # if np.isclose(float(experiment_results['g5.upper'][0].probability),
#                     #               float(experiment_results['g6.upper'][0].probability)):
#                     #     epr_histogram['uncoupled-equal'] += 1
#                     # else:
#                     #     epr_histogram['uncoupled-unequal'] += 1
#                 # elif experiment_results.get('g5.lower') and experiment_results.get('g6.lower'):
#                 #     epr_histogram['uncoupled-both-lower'] += 1
#                     # if np.isclose(float(experiment_results['g5.lower'][0].probability),
#                     #               float(experiment_results['g6.lower'][0].probability)):
#                     #     epr_histogram['uncoupled-equal'] += 1
#                     # else:
#                     #     epr_histogram['uncoupled-unequal'] += 1
#                 # else:
#                 #     epr_histogram['uncoupled-unequal'] += 1
#
#     ## Now report stats
#     log.setLevel(save_level)
#     switch_vals = {'control': 0, 'upper': 1, 'lower': 2, 'upper_coupled': 3, 'lower_coupled': 4}
#     def switch_order(s):
#         if '.' not in s: return s
#         gate, switch = s.split('.')
#         return gate + str(switch_vals[switch])
#     hist_keys = sorted(histogram.keys(), key=lambda x: switch_order(x))
#     hist_key_width = max_width(hist_keys)
#     count_width = max_width(histogram.values())
#     log.info('FINAL OUTPUTS:')
#     log.info('   FREDKIN GATES:')
#     result_keys = sorted(experiment_results.keys(), key=lambda x: switch_order(x))
#     result_key_width = max_width(result_keys)
#     for k in result_keys:
#         if not experiment_results[k]:
#             v = 'None'
#         else:
#             v = Particle.merge(experiment_results[k])
#         log.info(f'      {k:{result_key_width+1}s}: {v}')
#     log.info('')
#     log.info('DELAY GATES:')
#     for v in sim.delay_gates:
#         if v.state is None:
#             vstr = 'None'
#         else:
#             vstr = f'{Particle.merge(v.state)}'
#         log.info(f'    {k}: {vstr} {v}')
#     log.info('')
#     log.info('RESULT COUNTS:')
#     for k in hist_keys:
#         count = histogram[k]
#         if k in global_result.keys() and global_result[k]:
#             log.info(f'   {k:{hist_key_width}s}: {count:{count_width}d} ({(count/sim.n_samples):>6.1%}) {Particle.merge(global_result[k])}')
#     if config.measure_discrepancy:
#         if coupled_count == 0:
#             log.info('COUPLED COUNT 0!')
#             coupled_count = 1
#         if discrepancy_count == 0:
#             log.info('DISCREPANCY COUNT 0!')
#             discrepancy_count = 1
#         acounts = defaultdict(int)
#         log.info('')
#
#         log.info('Figure 4.17:')
#         log.info('   a:')
#         log.info(f'      w1,w3 = {w1w3m} {w1w3}')
#         log.info(f'      w1,w4 = {w1w4m} {w1w4}')
#         log.info(f'      w2,w3 = {w2w3m} {w2w3}')
#         log.info(f'      w2,w4 = {w2w4m} {w2w4}')
#         log.info('')
#
#         log.info('   b:')
#         log.info(f'      w1a,w3 = {w1aw3m} {w1aw3}')
#         log.info(f'      w1a,w4 = {w1aw4m} {w1aw4}')
#         log.info(f'      w2a,w3 = {w2aw3m} {w2aw3}')
#         log.info(f'      w2a,w4 = {w2aw4m} {w2aw4}')
#         log.info('')
#
#         log.info('   c:')
#         log.info(f'      w1a,w3a = {w1aw3am} {w1aw3a}')
#         log.info(f'      w1a,w4a = {w1aw4am} {w1aw4a}')
#         log.info(f'      w2a,w3a = {w2aw3am} {w2aw3a}')
#         log.info(f'      w2a,w4a = {w2aw4am} {w2aw4a}')
#         log.info('')
#
#         log.info('uncoupled lower/angle total:')
#         for angle in ['qa', 'qb', 'qc']:
#             upstr = f'{angle}.upper'
#             lostr = f'{angle}.lower'
#             upcount = histogram[upstr]
#             locount = histogram[lostr]
#             atotal = upcount + locount
#             acounts[angle] = locount/atotal
#             g1_angle_value = abs(qify(config.variables[angle]) - sim.gates.g1.theta)
#             g2_angle_value = abs(qify(config.variables[angle]) - sim.gates.g2.theta)
#             log.info(f'{angle}({g1_angle_value.degrees:.1f}º, {g2_angle_value.degrees:.1f}º): {locount}/{atotal}={(locount/atotal):.3f} ({g1_angle_value.sin**2:.3f}, {g2_angle_value.sin**2:.3f})')
#         log.info('')
#         log.info('coupled lower/angle total:')
#         c_acounts = defaultdict(int)
#         for angle in ['qa', 'qb', 'qc']:
#             upstr = f'{angle}.upper_coupled'
#             lostr = f'{angle}.lower_coupled'
#             upcount = histogram[upstr]
#             locount = histogram[lostr]
#             atotal = upcount + locount
#             c_acounts[angle] = locount / atotal
#             g1_angle_value = abs(qify(config.variables[angle]) - sim.gates.g1.theta)
#             g2_angle_value = abs(qify(config.variables[angle]) - sim.gates.g2.theta)
#             log.info(f'{angle}({g1_angle_value.degrees:.1f}º, {g2_angle_value.degrees:.1f}º): {locount}/{atotal}={(locount/atotal):.3f} ({g1_angle_value.sin**2:.3f}, {g2_angle_value.sin**2:.3f})')
#         log.info('')
#
#         log.info(f'uncoupled qb-qa={acounts["qb"]-acounts["qa"]:.3f}, qc-qb={acounts["qc"]-acounts["qb"]:.3f}, qc-qa={acounts["qc"]-acounts["qa"]:.3f}')
#         log.info(f'coupled qb-qa={c_acounts["qb"]-c_acounts["qa"]:.3f}, qc-qb={c_acounts["qc"]-c_acounts["qb"]:.3f}, qc-qa={c_acounts["qc"]-c_acounts["qa"]:.3f}')
#         log.info(f'coupled count = {coupled_count} ({coupled_count/sim.n_samples:.2%}), discrepancy_count = {discrepancy_count} ({discrepancy_count/coupled_count:.2%}), {disc_ab=}, {disc_bc=}, {disc_ac=}, {disc_ba=}, {disc_cb=}, {disc_ca=}')
#         log.info(f'disc/coupled={discrepancy_count/coupled_count:.2f}, disc/samples={discrepancy_count/sim.n_samples:.2f}')
#         log.info(f'coupled_pair_counts: ab={coupled_pair_counts["ab"]}, bc={coupled_pair_counts["bc"]}, ac={coupled_pair_counts["ac"]}, ba={coupled_pair_counts["ba"]}, cb={coupled_pair_counts["cb"]}, ca={coupled_pair_counts["ca"]}')
#         v_q1, v_qa, v_qb, v_qc = (qify(config.variables[x]) for x in ['q1', 'qa', 'qb', 'qc'])
#         log.info(f'{v_q1=:.3f}, {v_qa=:.3f}, {v_qb=:.3f}, {v_qc=:.3f}')
#         pred_q1 = abs(v_q1).sin**2
#         pred_qa = abs(v_qa - v_q1).sin**2
#         pred_qb = abs(v_qb - v_q1).sin**2
#         pred_qc = abs(v_qc - v_q1).sin**2
#         pred_ac = pred_qa
#         pred_ab = pred_qb
#         pred_bc = pred_qc
#         pred_ab_bc = pred_qa + pred_qb
#         log.info(f'q1 = {v_q1.degrees:.1f}º, qa = {v_qa.degrees:.1f}º, qb = {v_qb.degrees:.1f}º, qc = {v_qc.degrees:.1f}º')
#         log.info(f'angles: qa:{angle_counts["qa"]}, qb:{angle_counts["qb"]}, qc:{angle_counts["qc"]}')
#         pcab = pair_counts.ab
#         pcbc = pair_counts.bc
#         pcac = pair_counts.ac
#         pcba = pair_counts.ba
#         pccb = pair_counts.cb
#         pcca = pair_counts.ca
#         cpcab = coupled_pair_counts.ab
#         cpcbc = coupled_pair_counts.bc
#         cpcac = coupled_pair_counts.ac
#         cpcba = coupled_pair_counts.ba
#         cpccb = coupled_pair_counts.cb
#         cpcca = coupled_pair_counts.ca
#         pss = ', '.join([f'{pk}: {pair_counts[pk]}' for pk in ['ab', 'bc', 'ac', 'ba', 'cb', 'ca']]) #pair_counts.keys()])
#         log.info(f'pairs: {pss}')
#         log.info('')
#
#         # log.info(f'pairs: ab:{pair_counts["ab"]}, bc:{pair_counts["bc"]}, ac:{pair_counts["ac"]}, ba:{pair_counts["ba"]}, bc:{pair_counts["cb"]}, ac:{pair_counts["ca"]}')
#
#         measures = ['coupled pair counts', 'n_samples', 'pair counts', 'discrepancy count', 'coupled count']
#         pad_len = max([len(s) for s in measures])
#
#         discs = [disc_ab, disc_bc, disc_ac, disc_ab+disc_bc, disc_ba, disc_cb, disc_ba+disc_cb]
#
#         rate_calc = lambda term, divisor: term/divisor
#
#         try:
#             m_type = 'predicted'
#             hit = '*' if pred_ac > pred_ab+pred_bc else ''
#             log.info(f'{m_type: >{pad_len}}: ab={pred_ab:.3f},          bc={pred_bc:.3f},          ac={pred_ac:.3f},          ab+bc={pred_ab_bc:.3f}{hit}')
#             log.info('')
#         except ZeroDivisionError:
#             pass
#
#         # discrepancy rates / coupled pair counts
#         try:
#             rate_ab = disc_ab/cpcab
#             rate_bc = disc_bc/cpcbc
#             rate_ab_bc = rate_ab + rate_bc
#             rate_ac = disc_ac/cpcac
#             rate_ba = disc_ba/cpcba
#             rate_cb = disc_cb/cpccb
#             rate_ba_cb = rate_ba + rate_cb
#             rate_ca = disc_ca/cpcca
#             avg_ab = (disc_ab + disc_ba) / (cpcab + cpcba)
#             avg_bc = (disc_bc + disc_cb) / (cpcbc + cpccb)
#             avg_ac = (disc_ac + disc_ca) / (cpcac + cpcca)
#             avg_ab_bc = (rate_ab_bc + rate_ba_cb) / 2
#             m_type = 'coupled pair counts'
#             hit = '*' if rate_ac > rate_ab_bc else ''
#             log.info(f'{m_type: >{pad_len}}: ab={rate_ab:.3f},          bc={rate_bc:.3f},          ac={rate_ac:.3f},          ab+bc={rate_ab_bc:.3f}{hit}')
#             hit = '*' if rate_ca > rate_ba_cb else ''
#             log.info(f'{" ":>{pad_len}}: ba={rate_ba:.3f},          cb={rate_cb:.3f},          ca={rate_ca:.3f},          ba+cb={rate_ba_cb:.3f}{hit}')
#             log.info(f'{"avg":>{pad_len}}: ab={avg_ab:.3f} ({pred_ab-avg_ab:> 6.3f}), bc={avg_bc:.3f} ({pred_bc-avg_bc:> 6.3f}), ac={avg_ac:.3f} ({pred_ac-avg_ac:> 6.3f}), ab+bc={avg_ab_bc:.3f} ({pred_ab_bc-avg_ab_bc:> 6.3f}){hit}')
#             log.info('')
#         except ZeroDivisionError:
#             pass
#
#         # discrepancy rates / total number of trials, both coupled and uncoupled
#         try:
#             divisor = sim.n_samples
#             rate_ab = disc_ab/divisor
#             rate_bc = disc_bc/divisor
#             rate_ab_bc = rate_ab + rate_bc
#             rate_ac = disc_ac/divisor
#             rate_ba = disc_ba/divisor
#             rate_cb = disc_cb/divisor
#             rate_ba_cb = (disc_ba+disc_cb) / divisor
#             rate_ca = disc_ca/divisor
#             m_type = 'n_samples'
#             hit = '*' if rate_ac > rate_ab_bc else ''
#             log.info(f'{m_type: >{pad_len}}: ab={rate_ab:.3f},          bc={rate_bc:.3f},          ac={rate_ac:.3f},          ab+bc={rate_ab_bc:.3f}{hit}')
#             hit = '*' if rate_ca > rate_ba_cb else ''
#             log.info(f'{" ":>{pad_len}}: ba={rate_ba:.3f},          cb={rate_cb:.3f},          ca={rate_ca:.3f},          ba+cb={rate_ba_cb:.3f}{hit}')
#             log.info('')
#         except ZeroDivisionError:
#             pass
#
#         # discrepancy rates / pair counts, both coupled and uncoupled
#         try:
#             rate_ab = disc_ab/pcab
#             rate_bc = disc_bc/pcbc
#             rate_ab_bc = rate_ab + rate_bc
#             rate_ac = disc_ac/pcac
#             rate_ba = disc_ba/pcba
#             rate_cb = disc_cb/pccb
#             rate_ba_cb = rate_ba + rate_cb
#             rate_ca = disc_ca/pcca
#             m_type = 'pair counts'
#             log.info(f'{m_type: >{pad_len}}: ab={rate_ab:.3f},          bc={rate_bc:.3f},          ac={rate_ac:.3f},          ab+bc={rate_ab_bc:.3f}')
#             log.info(f'{" ":>{pad_len}}: ba={rate_ba:.3f},          cb={rate_cb:.3f},          ca={rate_ca:.3f},          ba+cb={rate_ba_cb:.3f}')
#             log.info('')
#         except ZeroDivisionError:
#             pass
#
#         # individual discrepancy rates / total number of discrepancies
#         try:
#             divisor = discrepancy_count
#             rate_ab = disc_ab/divisor
#             rate_bc = disc_bc/divisor
#             rate_ab_bc = rate_ab + rate_bc
#             rate_ac = disc_ac/divisor
#             rate_ba = disc_ba/divisor
#             rate_cb = disc_cb/divisor
#             rate_ba_cb = rate_ba + rate_cb
#             rate_ca = disc_ca/divisor
#             m_type = 'discrepancy count'
#             hit = '*' if rate_ac > rate_ab_bc else ''
#             log.info(f'{m_type: >{pad_len}}: ab={rate_ab:.3f},          bc={rate_bc:.3f},          ac={rate_ac:.3f},          ab+bc={rate_ab_bc:.3f}{hit}')
#             hit = '*' if rate_ca > rate_ba_cb else ''
#             log.info(f'{" ":>{pad_len}}: ba={rate_ba:.3f},          cb={rate_cb:.3f},          ca={rate_ca:.3f},          ba+cb={rate_ba_cb:.3f}{hit}')
#             log.info('')
#         except ZeroDivisionError:
#             pass
#
#         # discrepancy rate / total number of coupled trials
#         try:
#             divisor = coupled_count
#             rate_ab = disc_ab/divisor
#             rate_bc = disc_bc/divisor
#             rate_ab_bc = rate_ab + rate_bc
#             rate_ac = disc_ac/divisor
#             rate_ba = disc_ba/divisor
#             rate_cb = disc_cb/divisor
#             rate_ba_cb = rate_ba + rate_cb
#             rate_ca = disc_ca/divisor
#             m_type = 'coupled count'
#             hit = '*' if rate_ac > rate_ab_bc else ''
#             log.info(f'{m_type: >{pad_len}}: ab={rate_ab:.3f},          bc={rate_bc:.3f},          ac={rate_ac:.3f},          ab+bc={rate_ab_bc:.3f}{hit}')
#             hit = '*' if rate_ca > rate_ba_cb else ''
#             log.info(f'{" ":>{pad_len}}: ba={rate_ba:.3f},          cb={rate_cb:.3f},          ca={rate_ca:.3f},          ba+cb={rate_ba_cb:.3f}{hit}')
#             log.info('')
#         except ZeroDivisionError:
#             pass
#
#     if epr_stats:
#         log.info('\nEPR COUNTS:')
#         epr_key_width = max_width(epr_histogram.keys())
#         epr_count_width = max_width(epr_histogram.values())
#         for k in epr_histogram.keys():
#             log.info(f'   {k:{epr_key_width+1}s}: {epr_histogram[k]:{epr_count_width + 1}d}')
#         log.info('')
#
#     log.info('FULL HISTOGRAM VALUES:')
#     for k, v in histogram.items():
#         log.info(f'   {k}: {v}')
#
#     if fig411:
#         log.info('FOR FIGURE 4.11:')
#         log.info(f'{histogram["411-g2.upper"]/histogram["g1.upper"]=}')
#         log.info(f'{((g2.theta - g1.theta).cos ** 2)=}')