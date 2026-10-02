"""Run Pi tests using paths relative to this file, from any working directory."""

import argparse
from pathlib import Path
import sys
import unittest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("patterns", nargs="*", help="Test filenames or glob patterns; default: test_*.py")
    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument("-q", "--quiet", action="store_true")
    verbosity.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    project = Path(__file__).resolve().parent
    sys.path.insert(0, str(project))
    suite = unittest.TestSuite()
    for pattern in args.patterns or ["test_*.py"]:
        if not pattern.endswith(".py"):
            pattern += ".py"
        if not list((project / "tests").glob(pattern)):
            parser.error(f"No test files match {pattern!r} in {project / 'tests'}")
        suite.addTests(unittest.defaultTestLoader.discover(
            start_dir=str(project / "tests"), pattern=pattern, top_level_dir=str(project),
        ))
    result = unittest.TextTestRunner(verbosity=1 if args.quiet else 2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
