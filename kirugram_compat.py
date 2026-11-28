"""Runtime sanity checks for the Kirugram client used by NEXO."""

import kirugram

if not hasattr(kirugram, "Client") or not hasattr(kirugram, "filters"):
    raise ImportError("Installed Kirugram package is missing required Client/filters API")
