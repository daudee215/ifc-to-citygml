"""Read-only diagnostics for an installed package and its external validator."""
import platform
import sys

from .common import BUILTIN_PROFILES, CHECKOUT_ROOT, PACKAGE_DIR, code_digest, load_profile, software_versions, verify_resources
from .validation import load_schema
from .validator_tools import probe_validator
from . import __version__


def doctor() -> dict:
    result = {"installation_mode": "source_checkout" if CHECKOUT_ROOT else "installed_package",
              "package_directory": str(PACKAGE_DIR), "python": sys.version, "platform": platform.platform(),
              "software": software_versions(), "converter_source_sha256": code_digest()}
    try:
        if result["software"]["ifc-citygml"] != __version__:
            raise ValueError("Installed metadata and source versions differ; reinstall the package")
        result["resources"] = verify_resources()
        load_schema()
        result["bundled_schema_compilation"] = "passed"
        result["profiles"] = {name: load_profile(name)["representation"] for name in BUILTIN_PROFILES}
    except (ValueError, OSError) as exc:
        result.update({"status": "failed", "resource_error": str(exc)})
        return result
    result["validator"] = probe_validator()
    result["status"] = "passed" if result["validator"]["status"] == "passed" else "needs_validator"
    return result
