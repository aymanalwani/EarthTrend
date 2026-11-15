"""Startup diagnostics report missing dependencies as failures."""

from contextlib import redirect_stdout
from importlib.metadata import PackageNotFoundError
from io import StringIO
import unittest
from unittest.mock import patch

from earthtrend.health import main


class HealthTests(unittest.TestCase):
    def test_missing_distribution_fails(self):
        output = StringIO()
        with patch("earthtrend.health.version", side_effect=PackageNotFoundError):
            with redirect_stdout(output):
                self.assertEqual(main(), 1)
        self.assertIn("streamlit: MISSING", output.getvalue())

    def test_installed_distributions_pass_on_supported_python(self):
        with patch("earthtrend.health.version", return_value="test-version"):
            with patch("earthtrend.health.sys.version_info", (3, 11)):
                with redirect_stdout(StringIO()):
                    self.assertEqual(main(), 0)
