"""The marimo apps' library side.

The notebooks under notebooks/ are thin: a cell binds widgets to
globals, holds its `mo.state`, and lays the page out; the work behind
them — locating the model library, reading a model with the defaults
underneath it, the picker memories, the results tables, the sampling
projections — lives in these modules, once, where it is importable
from every app and testable from pytest. Under Pyodide (the WASM site)
they arrive in the quantish wheel, which each notebook's first cell
installs before importing anything here.
"""
