import logging
from typing import List, Dict
from multiworld.gate import FredkinGate
from multiworld.config_space import ConfigSpacePoint, ConfigSpace
from multiworld.simulation import Simulation

log = logging.getLogger('multiworld')


#  (w_1,1+w_1,2+w_1,3+w_1,4)(w_2,1+w2_2+w_2,3+w_2,4)...(w_p,1+w_p,2+w_p,3+w_p,4)

class ExecutionStage:
    def __init__(self, gates: Dict[str, FredkinGate], sim=None):
        self.sim: Simulation = sim
        self._gates = gates

    def __repr__(self):
        # return f'{self.name}: {self.gates}'
        return '|'.join([f'{gate}' for gate in self._gates.values()])

    def run(self, in_point: ConfigSpacePoint, step:int) -> List[ConfigSpacePoint]:
        sim: Simulation = self.sim
        in_space:ConfigSpace = ConfigSpace(in_point)
        result_space: ConfigSpace = ConfigSpace()
        log.info(f'starting step {step} ({self})')

        for gate in self._gates.values():
            gate.reset()

