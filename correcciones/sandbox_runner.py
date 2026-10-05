"""Drive a student perceptron program with scripted answers and capture its matplotlib figures.

Runs INSIDE the bubblewrap sandbox (mounted read-only at /runner), so it may only use the
standard library and matplotlib. Never run it directly on the host: it executes student code.

Usage (set by sandbox.py): sandbox_runner.py <source.py> <csv_path> <case> <menu_choice>
Writes /out/grafico_N.png and /out/traza.json (prompts answered, figures, axes counts, error).
"""

import builtins
import json
import os
import runpy
import sys
import traceback

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import to_hex

MAX_PROMPTS = 50
RETRY_WORDS = ("otro", "repet", "nuev", "continuar", "quieres probar", "desea probar")
BIAS_WORDS = ("sesgo", "bias", "w0")
PATH_WORDS = ("ruta", "archivo csv", "nombre del archivo", "nombre o ruta", "escribe la ruta")
ACTIVATION_WORDS = ("activaci", "funcion", "función")
WEIGHT_WORDS = ("peso", " w1", " w2", "entrada x", "dimensión")
MENU_WORDS = ("opci", "elige", "selecc", "1 o 2")


def main():
    source, csv_path, case_name, dataset_choice = sys.argv[1:5]
    prompts = []
    figures = []
    state = {"weight_index": 0, "file_selected": False, "activation_selected": False}

    def answer(prompt=""):
        if len(prompts) >= MAX_PROMPTS:
            raise EOFError(f"More than {MAX_PROMPTS} console prompts")
        text = str(prompt).lower()
        if any(word in text for word in RETRY_WORDS):
            value = "n"
        elif any(word in text for word in BIAS_WORDS):
            value = "0"
        elif any(word in text for word in PATH_WORDS):
            value = csv_path
            state["file_selected"] = True
        elif "s = signo" in text and "h =" in text:
            value = "h"
            state["activation_selected"] = True
        elif any(word in text for word in ACTIVATION_WORDS):
            value = "1"
            state["activation_selected"] = True
        elif any(word in text for word in WEIGHT_WORDS):
            value = ("1", "-1")[state["weight_index"] % 2]
            state["weight_index"] += 1
        elif "csv" in text:
            value = csv_path
            state["file_selected"] = True
        elif not state["file_selected"] and any(word in text for word in MENU_WORDS):
            value = dataset_choice
            state["file_selected"] = True
        elif not state["activation_selected"] and any(word in text for word in MENU_WORDS):
            value = "1"
            state["activation_selected"] = True
        else:
            value = "n"
        prompts.append({"prompt": str(prompt), "answer": value})
        return value

    def save_figures(*args, **kwargs):
        for number in list(plt.get_fignums()):
            fig = plt.figure(number)
            fig.canvas.draw()
            name = f"grafico_{len(figures) + 1}.png"
            fig.savefig(os.path.join("/out", name), dpi=120, bbox_inches="tight")
            axes = []
            for ax in fig.axes:
                color_counts = {}
                point_count = 0
                for scatter in ax.collections:
                    count = len(scatter.get_offsets())
                    point_count += count
                    colors = scatter.get_facecolors()
                    if len(colors) == 1:
                        colors = [colors[0]] * count
                    for color in colors:
                        key = to_hex(color, keep_alpha=False)
                        color_counts[key] = color_counts.get(key, 0) + 1
                axes.append({"title": ax.get_title(), "points": point_count,
                             "colors": color_counts, "lines": len(ax.lines)})
            figures.append({"file": name, "axes": len(fig.axes), "axes_detail": axes})
            plt.close(fig)

    builtins.input = answer
    plt.show = save_figures
    result = {"case": case_name, "source": source, "csv": csv_path,
              "prompts": prompts, "figures": figures, "error": ""}
    try:
        runpy.run_path(source, run_name="__main__")
        if plt.get_fignums():
            save_figures()
    except BaseException:
        result["error"] = traceback.format_exc(limit=12)
    finally:
        with open("/out/traza.json", "w", encoding="utf-8") as file:
            json.dump(result, file, ensure_ascii=False, indent=2)
    if result["error"]:
        print(result["error"], file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
