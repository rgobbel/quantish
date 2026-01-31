from multiworld.config_space import (Wire, Position, PKey, CSCoordinate,
                                     ConfigSpacePoint, PCoordinate, PCoordValue)
from multiworld.particle import Particle, PKey
from multiworld.util import Sign
from multiworld.gate import FredkinGate
import multiworld.qnumber as qn

p1 = Particle('p1', 1, 1)
p1m = Particle('p1', -1, 1)
p1mm = Particle('p1', -1, -1)
p2 = Particle('p2', 1, 1)
p2m = Particle('p2', -1, 1)
p2mm = Particle('p2', -1, -1)
particles = [p1, p1m, p2, p2m, p1mm, p2mm]
pkeys = [p.pkey for p in particles]

g1 = FredkinGate('g1', qn.qify('rad(30)'))

pos = Position(Wire('g1', 'upper'), Wire('g3', 'control'))
pos2 = Position(Wire('g1', 'lower'), Wire('g5', 'lower'))

coord1 = PCoordinate(step=1, pkey=p1.pkey, position=pos)
coord2 = PCoordinate(step=1, pkey=p1m.pkey, position=pos)
coord3 = PCoordinate(step=1, pkey=p2.pkey, position=pos2)
coord4 = PCoordinate(step=1, pkey=p2m.pkey, position=pos2)
# coord3 = PCoordinate(pkeys[2], pos2)
# coord4 = PCoordinate(pkeys[3], pos2)

# pcoords = coord, coord2
pcoords = coord1, coord2, coord3, coord4
pcoords1 = coord1, coord3
pcoords2 = coord2, coord4
ppluses = [p1, p2]
pminuses = [p1m, p2m]

cs_coord = CSCoordinate(pcoords)

pcvs = [PCoordValue(PCoordinate(step=1, pkey=p.pkey, position=pos), p) for p, pos in zip(particles, ([pos]*3) + ([pos2]* 3)) ]

cp = ConfigSpacePoint(step=1, initial_values=pcvs)

mmt1 = g1.measure(p1)

cp2 = ConfigSpacePoint(step=1, initial_values=[PCoordValue(pc, p) for pc, p in zip(pcoords2, pminuses)])

cp.add(cp2)


pass
