"""Run with python -m earthtrend.health before launching Streamlit."""

from importlib.metadata import PackageNotFoundError, version
import platform
import sys
import sysconfig


DEPENDENCIES = (
    "streamlit", "pandas", "numpy", "scipy", "plotly", "requests",
    "pymannkendall", "statsmodels",
)


def main() -> int:
    """Check interpreter and installed distributions without network requests."""
    print(f"Python {platform.python_version()} ({sysconfig.get_platform()})")
    print(f"Interpreter: {sys.executable}")
    healthy = sys.version_info >= (3, 11)
    if not healthy:
        print("Python 3.11 or newer is required.")
    for name in DEPENDENCIES:
        try:
            print(f"{name}: {version(name)}")
        except PackageNotFoundError:
            print(f"{name}: MISSING")
            healthy = False
    print("Dependency check passed." if healthy else "Install requirements using this interpreter.")
    print("This check does not verify imports, NASA connectivity, or scientific calculations.")
    return 0 if healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())
