"""Tarea 2 entry point; shared grading infrastructure stays in correcciones/."""
from pathlib import Path
import runpy
import sys

if __name__ == "__main__":
    corrections = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(corrections))
    runpy.run_path(str(corrections / "calificador_tarea_2.py"), run_name="__main__")
