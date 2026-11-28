"""Compatibility bridge for PyTgCalls' Pyrogram adapter and the Kirugram fork.

Kirugram intentionally exposes the Pyrogram-compatible API under the `kirugram`
package name. PyTgCalls currently selects its adapter from the top-level module
name and imports adapter modules from `pyrogram.*`. This bridge aliases the
matching Kirugram modules and makes only that adapter-selection check treat
Kirugram clients as Pyrogram-compatible clients.
"""
from __future__ import annotations

import importlib
import sys

import kirugram


# Import the modules PyTgCalls' Pyrogram adapter references, then expose the
# same module objects under the legacy import paths. This avoids duplicate
# classes (which would break isinstance checks for raw updates and errors).
_KIRUGRAM_SUBMODULES = (
    "errors",
    "handlers",
    "raw",
    "raw.base",
    "raw.functions",
    "raw.functions.auth",
    "raw.functions.channels",
    "raw.functions.messages",
    "raw.functions.phone",
    "raw.functions.updates",
    "raw.functions.upload",
    "raw.types",
    "raw.types.messages",
    "session",
)


def install_pytgcalls_compat() -> None:
    """Make Kirugram clients usable by PyTgCalls without installing Pyrogram."""
    sys.modules["pyrogram"] = kirugram

    for suffix in _KIRUGRAM_SUBMODULES:
        module = importlib.import_module(f"kirugram.{suffix}")
        sys.modules[f"pyrogram.{suffix}"] = module

    # Import after the aliases are installed. PyTgCalls creates its adapter
    # lazily when PyTgCalls(client) is constructed.
    from pytgcalls.mtproto.bridged_client import BridgedClient

    current = BridgedClient.package_name
    if getattr(current, "_kirugram_compat", False):
        return

    def package_name(client):
        detected = str(client.__class__.__module__).split(".", 1)[0]
        if detected == "kirugram":
            return "pyrogram"
        return current(client)

    package_name._kirugram_compat = True
    BridgedClient.package_name = staticmethod(package_name)
