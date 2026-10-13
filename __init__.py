"""FiestaBoard plugin shim — re-exports the plugin class from the package layout.

This file exists for compatibility with FiestaBoard installations that expect
the plugin entry point at the repository root rather than in plugins/commute/.
"""

import importlib.util
from pathlib import Path
import sys

_sub_init = Path(__file__).parent / "plugins" / "commute" / "__init__.py"
_module_name = "__commute_impl__"
_spec = importlib.util.spec_from_file_location(_module_name, _sub_init)
if _spec and _spec.loader:
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules[_module_name] = _mod
    _spec.loader.exec_module(_mod)
    globals().update({k: v for k, v in vars(_mod).items() if not k.startswith("_")})
