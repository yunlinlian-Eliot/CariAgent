"""English Streamlit entry point; deploy in its own process/application."""

import os
import runpy
from pathlib import Path

os.environ["CARIAGENT_LANGUAGE"] = "en"
runpy.run_path(str(Path(__file__).with_name("app.py")), run_name="__main__")
