import sympy as sym

class CalcMode:
    mode = 'Float'
    _instance = None

    @classmethod
    def default(cls, new_mode:str=None):
        global I, PI
        if new_mode is None or new_mode == '':
            return cls._mode
        else:
            cls._mode = new_mode
            if cls._mode == 'Float':
                I = 1j
                PI = m.pi
            else:
                I = sym.I
                PI = sym.pi
            return cls._mode

CALC_MODE = CalcMode()

