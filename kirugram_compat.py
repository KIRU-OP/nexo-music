"""Bridge legacy Pyrogram import paths to the Kirugram distribution.

NEXO plugins still contain older pyrogram.* imports. This module loads
Kirugram first and maps already-loaded package modules to those compatibility
names so the application uses the KIRU-OP-maintained implementation.
"""

import importlib
import sys

import kirugram

# Load the subpackages used directly by NEXO before installing aliases.
for _name in (
    "kirugram.enums",
    "kirugram.errors",
    "kirugram.filters",
    "kirugram.handlers",
    "kirugram.raw",
    "kirugram.session.auth",
    "kirugram.storage.sqlite_storage",
    "kirugram.types",
):
    importlib.import_module(_name)

# The root package and loaded submodules share the same module objects.
sys.modules["pyrogram"] = kirugram
for _module_name, _module in tuple(sys.modules.items()):
    if _module_name.startswith("kirugram."):
        _legacy_name = "pyrogram" + _module_name[len("kirugram"): ]
        sys.modules.setdefault(_legacy_name, _module)
