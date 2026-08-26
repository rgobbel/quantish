"""Schema validation for the model YAMLs.

The schema lives in models/schema.yaml, next to the files it
describes. It is a yaml-schema (ys) schema — JSON Schema semantics
written in YAML — so the same file drives the ys CLI
(`ys -f models/schema.yaml <model>.yaml`) and this module, which
reads it with jsonschema (ys has no Python bindings) and wraps it in
the same problems-list idiom as builder.validate_graph: empty list
means valid.
"""
from functools import lru_cache
from pathlib import Path

import jsonschema
import yaml

SCHEMA_PATH = Path(__file__).parent.parent / 'models' / 'schema.yaml'

# keys that may also appear in defaults.yaml (model files override it)
OPTION_KEYS = ('calculation_mode', 'loglevel', 'string_precision',
               'max_symbolic_len', 'sample', 'n_samples', 'epr_stats')


@lru_cache(maxsize=1)
def load_schema() -> dict:
    with open(SCHEMA_PATH) as f:
        return yaml.safe_load(f)


def _problems(config, schema) -> list[str]:
    validator = jsonschema.Draft202012Validator(schema)
    return [(f"{'.'.join(str(p) for p in e.path)}: " if e.path else '')
            + e.message
            for e in sorted(validator.iter_errors(config),
                            key=lambda e: list(e.path))]


def validate_model(config: dict) -> list[str]:
    """Problems with a model config dict; empty when it is valid."""
    return _problems(config, load_schema())


def validate_defaults(config: dict) -> list[str]:
    """Problems with a defaults.yaml dict: option keys only, each
    checked against the model schema's definition of that option."""
    schema = load_schema()
    keys = OPTION_KEYS + ('variables',)   # the standard-names block
    return _problems(config, {
        'type': 'object',
        'additionalProperties': False,
        'properties': {k: schema['properties'][k] for k in keys},
        '$defs': schema['$defs'],   # lifted subschemas keep their $refs
    })
