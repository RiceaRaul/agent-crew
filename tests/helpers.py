"""Shared test setup: a temp project with a git repo and a temp COPILOT_HOME."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class TempProjectCase(unittest.TestCase):
    """Each test gets its own project folder and Copilot home, removed afterwards."""

    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        base = Path(self._temp.name)
        self.root = base / "project"
        self.home = base / "copilot-home"
        self.root.mkdir()
        self.home.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        self._old_cwd = Path.cwd()
        self._old_home = os.environ.get("COPILOT_HOME")
        os.environ["COPILOT_HOME"] = str(self.home)
        os.chdir(self.root)

    def tearDown(self) -> None:
        os.chdir(self._old_cwd)

        if self._old_home is None:
            os.environ.pop("COPILOT_HOME", None)
        else:
            os.environ["COPILOT_HOME"] = self._old_home

        self._temp.cleanup()
