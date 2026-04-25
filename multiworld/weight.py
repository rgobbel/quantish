from typing import Tuple, Self
import numpy as np
from multiworld.gate import FredkinGate
from multiworld.qnumber import Complex, Real

class PartTree:
    def __init__(self, root_index:Tuple[int], weights:Tuple[Complex], children:Tuple[Self]=None):
        self.root_index = root_index
        self.weights = {i: w for i, w in enumerate(weights)}
        if children is not None:
            self.children = children
        else:
            self.children = (None,) * 4
        self.roots = {root_index: self}

    @property
    def weight(self):
        return sum(self.weights.values())

    def add(self, other:Self):
        for our_index, other_index in zip(self.root_index, other.root_index):


