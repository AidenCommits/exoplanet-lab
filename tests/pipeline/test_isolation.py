"""The pipeline must never see the truth (spec 2.5, blind mode).

Importing the pipeline must not load any generator module, so no pipeline code can reach the
answer key or the noise-free model, even by accident.
"""

import subprocess
import sys

CHECK = """
import sys
import exoplanet_lab.pipeline
leaked = sorted(m for m in sys.modules if m.startswith("exoplanet_lab.generator"))
print(",".join(leaked))
"""


def test_pipeline_does_not_import_the_generator() -> None:
    # A fresh interpreter, because this test session has already imported the generator.
    completed = subprocess.run(
        [sys.executable, "-c", CHECK], capture_output=True, text=True, check=True
    )
    assert completed.stdout.strip() == "", f"pipeline imports {completed.stdout.strip()}"
