else:
log.info(f'            NON-LOOPING SPLIT of {d}')
# d1
i = 0
dest_str = sim.links.get(str(wire_pos_w))
if dest_str is not None:
    dest = GatePort(*dest_str.split(SEP))
else:
    w_gate = wire_pos_w.gate
    if i < 2:
        w_port = wire_pos_w.port
    else:
        w_port = OTHER[wire_pos_w.port]
    dest = GatePort(w_gate, f'{w_port}')
    # dest = NOWHERE
new_ds[i].pcvals[pname].pcoord.position.endpoint = dest
new_ds[i].pcvals[pname].sign = sign_s
# weight = d.pcvals[pname].particle.weight
# if abs(weight) > 1:
#     log.warning(f'IN SPLIT PARTICLE GENERATION, NEW WEIGHT IS > 1: {weight}')
if not control_present:
    if c.pcvals[pname].particle.sign == Sign.plus:
        weight = d.pcvals[pname].particle.weight * sim.gates[wire_pos_w.gate].cos2_theta
    elif c.pcvals[pname].particle.sign == Sign.minus:
        weight = d.pcvals[pname].particle.weight * sim.gates[wire_pos_w.gate].sin2_theta
    else:
        raise RuntimeError(f'{c.pcvals[pname].particle.sign=}')
else:
    if c.pcvals[pname].particle.sign == Sign.plus:
        weight = d.pcvals[pname].particle.weight * sim.gates[wire_pos_w.gate].sin2_theta
    elif c.pcvals[pname].particle.sign == Sign.minus:
        weight = d.pcvals[pname].particle.weight * sim.gates[wire_pos_w.gate].cos2_theta
    else:
        raise RuntimeError(f'{c.pcvals[pname].particle.sign=}')
if abs(weight) > 1:
    log.error(f'IN SPLIT PARTICLE GENERATION, NEW WEIGHT IS > 1: {weight}')
    if self.sim.disallow_excess_weights: skip_this_one = True
new_ds[i].pcvals[pname].particle.weight = weight
# if abs(new_ds[i].pcvals[pname].particle.weight) > 1:
#     log.warning(f'IN SPLIT PARTICLE GENERATION, NEW WEIGHT IS > 1: {new_ds[i].pcvals[pname].particle.weight=}')
new_ds[i].pcvals[pname].particle.trace += [f'd{i + 1}{sign_s}:{dest}']

# d2
i = 1
dest_str = sim.links.get(str(wire_pos_w))
if dest_str is not None:
    dest = GatePort(*dest_str.split(SEP))
else:
    w_gate = wire_pos_w.gate
    if i < 2:
        w_port = wire_pos_w.port
    else:
        w_port = OTHER[wire_pos_w.port]
    dest = GatePort(w_gate, f'{w_port}')
    # dest = NOWHERE
new_ds[i].pcvals[pname].pcoord.position.endpoint = dest
new_ds[i].pcvals[pname].sign = sign_s.negative
if not control_present:
    if c.pcvals[pname].particle.sign == Sign.plus:
        weight = d.pcvals[pname].particle.weight * sim.gates[wire_pos_w.gate].cos_sin_theta
    elif c.pcvals[pname].particle.sign == Sign.minus:
        weight = d.pcvals[pname].particle.weight * sim.gates[wire_pos_w.gate].mcos_sin_theta
    else:
        raise RuntimeError(f'{c.pcvals[pname].particle.sign=}')
else:
    if c.pcvals[pname].particle.sign == Sign.plus:
        weight = d.pcvals[pname].particle.weight * sim.gates[wire_pos_w.gate].mcos_sin_theta
    elif c.pcvals[pname].particle.sign == Sign.minus:
        weight = d.pcvals[pname].particle.weight * sim.gates[wire_pos_w.gate].cos_sin_theta
    else:
        raise RuntimeError(f'{c.pcvals[pname].particle.sign=}')
if abs(weight) > 1:
    log.error(f'IN SPLIT PARTICLE GENERATION, NEW WEIGHT IS > 1: {weight}')
    if self.sim.disallow_excess_weights: skip_this_one = True
new_ds[i].pcvals[pname].particle.weight = weight
new_ds[i].pcvals[pname].particle.trace += [f'd{i + 1}{sign_s.negative}:{dest}']

# d3
i = 2
dest_str = sim.links.get(str(GatePort(wire_pos_w.gate, OTHER[wire_pos_w.port])))
if dest_str is not None:
    dest = GatePort(*dest_str.split(SEP))
else:
    w_gate = wire_pos_w.gate
    if i < 2:
        w_port = wire_pos_w.port
    else:
        w_port = OTHER[wire_pos_w.port]
    dest = GatePort(w_gate, f'{w_port}')
    # dest = NOWHERE
new_ds[i].pcvals[pname].pcoord.position.endpoint = dest
new_ds[i].pcvals[pname].sign = sign_s
# weight = d.pcvals[pname].particle.weight
# if abs(weight) > 1:
#     log.warning(f'IN SPLIT PARTICLE GENERATION, NEW WEIGHT IS > 1: {weight}')
if not control_present:
    if c.pcvals[pname].particle.sign == Sign.plus:
        weight = d.pcvals[pname].particle.weight * sim.gates[wire_pos_w.gate].sin2_theta
    elif c.pcvals[pname].particle.sign == Sign.minus:
        weight = d.pcvals[pname].particle.weight * sim.gates[wire_pos_w.gate].cos2_theta
    else:
        raise RuntimeError(f'{c.pcvals[pname].particle.sign=}')
else:
    if c.pcvals[pname].particle.sign == Sign.plus:
        weight = d.pcvals[pname].particle.weight * sim.gates[wire_pos_w.gate].cos2_theta
    elif c.pcvals[pname].particle.sign == Sign.minus:
        weight = d.pcvals[pname].particle.weight * sim.gates[wire_pos_w.gate].sin2_theta
    else:
        raise RuntimeError(f'{c.pcvals[pname].particle.sign=}')
if abs(weight) > 1:
    log.error(f'IN SPLIT PARTICLE GENERATION, NEW WEIGHT IS > 1: {weight}')
    if self.sim.disallow_excess_weights: skip_this_one = True
new_ds[i].pcvals[pname].particle.weight = weight
# if abs(new_ds[i].pcvals[pname].particle.weight) > 1:
#     log.warning(f'IN SPLIT PARTICLE GENERATION, NEW WEIGHT IS > 1: {new_ds[i].pcvals[pname].particle.weight=}')
new_ds[i].pcvals[pname].particle.trace += [f'd{i + 1}{sign_s}:{dest}']

# d4
i = 3
dest_str = sim.links.get(str(GatePort(wire_pos_w.gate, OTHER[wire_pos_w.port])))
if dest_str is not None:
    dest = GatePort(*dest_str.split(SEP))
else:
    w_gate = wire_pos_w.gate
    if i < 2:
        w_port = wire_pos_w.port
    else:
        w_port = OTHER[wire_pos_w.port]
    dest = GatePort(w_gate, f'{w_port}')
    # dest = NOWHERE
new_ds[i].pcvals[pname].pcoord.position.endpoint = dest
new_ds[i].pcvals[pname].sign = sign_s.negative
# weight = d.pcvals[pname].particle.weight
# if abs(weight) > 1:
#     log.warning(f'IN SPLIT PARTICLE GENERATION, NEW WEIGHT IS > 1: {weight}')
if not control_present:
    if c.pcvals[pname].particle.sign == Sign.plus:
        weight = d.pcvals[pname].particle.weight * sim.gates[wire_pos_w.gate].mcos_sin_theta
    elif c.pcvals[pname].particle.sign == Sign.minus:
        weight = d.pcvals[pname].particle.weight * sim.gates[wire_pos_w.gate].cos_sin_theta
    else:
        raise RuntimeError(f'{c.pcvals[pname].particle.sign=}')
else:
    if c.pcvals[pname].particle.sign == Sign.plus:
        weight = d.pcvals[pname].particle.weight * sim.gates[wire_pos_w.gate].cos_sin_theta
    elif c.pcvals[pname].particle.sign == Sign.minus:
        weight = d.pcvals[pname].particle.weight * sim.gates[wire_pos_w.gate].mcos_sin_theta
    else:
        raise RuntimeError(f'{c.pcvals[pname].particle.sign=}')
if abs(weight) > 1:
    log.error(f'IN SPLIT PARTICLE GENERATION, NEW WEIGHT IS > 1: {weight}')
    if self.sim.disallow_excess_weights: skip_this_one = True
new_ds[i].pcvals[pname].particle.weight = weight
# if abs(new_ds[i].pcvals[pname].particle.weight) > 1:
#     log.warning(f'IN SPLIT PARTICLE GENERATION, NEW WEIGHT IS > 1: {new_ds[i].pcvals[pname].particle.weight=}')
new_ds[i].pcvals[pname].particle.trace += [f'd{i + 1}{sign_s.negative}:{dest}']

