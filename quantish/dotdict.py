import enum
import json
import warnings
from collections import abc
from typing import Any
from collections import defaultdict
import copy

# try:
#     from yaml_util import load_yaml
# except ImportError:
#     from src.yaml_util import load_yaml
from pathlib import Path
# from warnings import warn
# import sys

# MIN_PYTHON = (3, 9)
# assert sys.version_info >= MIN_PYTHON, f"dotdict requires Python {'.'.join([str(n) for n in MIN_PYTHON])} or newer"
DEBUG = False
NOSHAPE = True

DDNULL = {}

# def ddfactory():
#     return defaultdict(ddfactory)
#
#
# class DefDD(defaultdict):
#     def __init__(self, default_factory=None, **kwargs):
#         if default_factory is None:
#             default_factory = ddfactory
#         self.default_factory = default_factory
#         super().__init__(default_factory, **kwargs)

class DotDict(abc.MutableMapping):
    """Enable key.val syntax for Python dicts.
    Can be initialized from a JSON file, or a vanilla dict.
    """

    def __init__(self, *args, **kwargs):
        # object.__setattr__(self, '__parent', kwargs.pop('__parent', None))
        # object.__setattr__(self, '__key', kwargs.pop('__key', None))
        # object.__setattr__(self, '__frozen', False)
        # print(kwargs)
        object.__setattr__(self, '__dict__', {'__initialized__': False})
        object.__setattr__(self, '__vals__', dict())
        if 'DEFAULT' not in kwargs.keys():
            object.__setattr__(self, '__return_default__', False)
        else:
            if 'AUTOEXTEND' in kwargs.keys():
                warnings.warn('AUTOEXTEND should not be used in combination with DEFAULT',
                              RuntimeWarning, stacklevel=2)
            object.__setattr__(self, '__return_default__', True)
            object.__setattr__(self, '__autoextend__', False)
            object.__setattr__(self, '__default__', kwargs.get('DEFAULT'))
            kwargs.__delitem__('DEFAULT')
        if 'AUTOEXTEND' not in kwargs.keys():
            object.__setattr__(self, '__autoextend__', True)
        else:
            object.__setattr__(self, '__autoextend__', kwargs.get('AUTOEXTEND'))
            kwargs.__delitem__('AUTOEXTEND')
        vals = kwargs
        if kwargs.get('file') is not None:
            filearg = kwargs['file']
            if isinstance(filearg, str):
                with open(filearg, 'r') as jf:
                    vals = json.load(jf)
            else:
                vals = json.load(filearg)
        elif kwargs.get('vals') is not None:
            vals = kwargs['vals']
            if isinstance(vals, str):
                vals = json.loads(vals)
        if isinstance(vals, abc.Mapping):
            for k, v in vals.items():
                if DEBUG: print(f'DotDict.__init__ {k=}, {v=}')
                newv = v
                if isinstance(v, abc.Set):
                    newv = set(DotDict(vals=item,
                                       AUTOEXTEND=self.__autoextend__, DEFAULT=self.__default__)
                            if isinstance(item, (abc.Mapping, abc.Set, list, tuple)) else item for item in v)
                elif isinstance(v, abc.Mapping):
                    newv = DotDict(vals=v)
                elif isinstance(v, list):
                    newv = list(DotDict(vals=item, AUTOEXTEND=self.__autoextend, DEFAULT=self.__default)
                            if isinstance(item, (abc.Mapping, abc.Set, list, tuple)) else item for item in v)
                elif isinstance(v, tuple):
                    newv = tuple(DotDict(vals=item, AUTOEXTEND=self.__autoextend, DEFAULT=self.__default)
                            if isinstance(item, (abc.Mapping, abc.Set, list, tuple)) else item for item in v)
                else:
                    pass
                self.__vals__.__setitem__(k, newv)
                object.__setattr__(self, k, newv)
        object.__setattr__(self, '__initialized__', True)
        super().__init__()
        pass

    def __getattr__(self, item):
        if NOSHAPE and item == 'shape':
            raise AttributeError(item)
        initialized = object.__getattribute__(self, '__initialized__')
        if initialized:
            # return object.__getattribute__(self, item)
            try:
                return object.__getattribute__(self, item)
            except AttributeError:
                if DEBUG: print(f"AttributeError GETATTR {item}")
                if self.__return_default__:
                    return object.__getattribute__(self, '__default__')
                elif self.__autoextend__:
                    newval = DotDict()
                    self.__setattr__(item, newval)
                    return newval
                else:
                    raise AttributeError
        else:
            if item in ('__initialized', '__vals__'):
                return object.__getattribute__(self, item)
            else:
                raise AttributeError(item)

    def __setattr__(self, key: str, value: Any):
        if key in ('__initialized', '__vals__'):
            object.__setattr__(self, key, value)
        else:
            # star = '*' if key not in self.__dict__ else ''
            # print(f'{star}key={key}, value={value}')
            # if key == 'shape':
            #     print(f'setting {key} = {value}')
            if value != '__dict__':
                if DEBUG: print(f"SETATTR {key},{value}")
                if (object.__getattribute__(self, '__initialized__') and
                        isinstance(value, abc.Mapping) and
                        type(value) not in (DotDict, defaultdict)):
                    if len(value) == 0:
                        value = DotDict(AUTOEXTEND=self.__autoextend__, DEFAULT=self.__default__)
                    else:
                        value = DotDict(vals=value, AUTOEXTEND=self.__autoextend__, DEFAULT=self.__default__)
            object.__setattr__(self, key, value)
            self.__vals__[key] = value

    def __delattr__(self, item):
        del self.__vals__[item]
        del self.__dict__[item]

    @property
    def dict(self):
        ret = {}
        for k, v in self.__vals__.items():
            if str(k)[0:1] == '_':
                continue
            elif isinstance(v, DotDict):
                ret[k] = v.__vals__
            else:
                ret[k] = v
        return ret

    def __repr__(self):
        return str(self.dict)

    def __getitem__(self, item):
        return self.__dict__[item]

    def __setitem__(self, key, value):
        self.__setattr__(key, value)

    def __delitem__(self, key):
        self.__delattr__(key)

    def __delete__(self, instance):
        print(f'Calling __delete__ on  {instance}')

    def __len__(self):
        return len(self.__vals__)

    def __iter__(self):
        idict = {k: self[k] for k in self.__vals__.keys()}
        return iter(idict)

    def __or__(self, other):
        if DEBUG:
            print(f'__or__, self.__vals__={self.__vals__}, other={other}')
        new_dd = DotDict(vals=self.__vals__)
        if self.get('__autoextend__') is not None: object.__setattr__(new_dd, '__autoextend__', self.__autoextend)
        if self.get('__default__') is not None: object.__setattr__(new_dd, '__default__', self.__default)
        return new_dd.update(other)

    # def __return_default(self):
    #     return False
    #
    # def __default(self):
    #     return None

    def update(self, other:abc.Mapping, overwrite_existing=False):
        if DEBUG: print(f'{self.__vals__=}, {other=}')
        for k, v in other.items():
            if isinstance(v, abc.Mapping):
                if overwrite_existing or k not in self.keys():
                    newv = DotDict(vals=v)
                    self[k] = newv
                else:
                    self[k].update(v)
            else:
                self[k] = v
        return self

    def assurepath(self, *attrs: str):
        obj = self
        for attr in attrs:
            if not hasattr(obj, attr):
                newobj = DotDict()
                obj.__setattr__(attr, newobj)
            else:
                newobj = getattr(obj, attr)
            obj = newobj


class DotDictEncoder(json.JSONEncoder):
    def default(self, o: DotDict) -> dict:
        return o.dict
