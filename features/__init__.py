"""Drop-in feature modules for DriveLegal India.

Every ``features/<name>.py`` module is auto-discovered. A feature module is
self-contained: it owns its data loading, validation, Pydantic models, core
logic and (optionally) a FastAPI ``router``. Adding a feature therefore only
adds new files, and never edits ``app_core.py``, ``api.py`` or ``models.py``,
so independent pull requests cannot conflict with each other.

Feature names are still reachable as ``app_core.<name>`` and ``models.<name>``
(see ``lookup``), which keeps existing call sites and tests working.
"""

from __future__ import annotations

import importlib
import pkgutil
import sys
from types import ModuleType
from typing import Any

_modules: list[ModuleType] | None = None
_loading = False


def load_all() -> list[ModuleType]:
    """Import every public feature module once, in alphabetical order."""
    global _modules, _loading
    if _modules is None:
        _loading = True
        try:
            found = sorted(pkgutil.iter_modules(__path__), key=lambda info: info.name)
            _modules = [
                importlib.import_module(f"{__name__}.{info.name}")
                for info in found
                if not info.name.startswith("_")
            ]
        finally:
            _loading = False
    return _modules


def routers() -> list[Any]:
    """Return the FastAPI routers exported by feature modules."""
    return [module.router for module in load_all() if hasattr(module, "router")]


def lookup(name: str) -> Any:
    """Resolve a public name defined by any feature module."""
    if not name.startswith("__"):
        for module in _partial_modules() if _loading else load_all():
            if name in vars(module):
                return vars(module)[name]
    raise AttributeError(name)


def _partial_modules() -> list[ModuleType]:
    """Feature modules imported so far (used while discovery is still running)."""
    prefix = f"{__name__}."
    return [module for key, module in list(sys.modules.items()) if key.startswith(prefix)]
