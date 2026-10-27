"""Generate the installed manifest during wheel builds without changing sources."""
from pathlib import Path
import runpy

from setuptools import setup
from setuptools.command.build_py import build_py


class BuildPy(build_py):
    def run(self):
        super().run()
        render = runpy.run_path(str(Path(__file__).parent / 'scripts/build_manifest.py'))['render']
        (Path(self.build_lib) / 'lqcd_agent/_build_manifest.json').write_text(render())


setup(cmdclass={'build_py': BuildPy})
