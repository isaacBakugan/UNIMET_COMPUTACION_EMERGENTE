"""Run only INSIDE bubblewrap. Replay a bounded console session and capture test matrices."""
import builtins
import json
import os
import random
import resource
import runpy
import sys
import traceback

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.colors import to_hex
import numpy as np


def main():
    source, job_path = sys.argv[1:3]
    job = json.load(open(job_path, encoding="utf-8"))
    resource.setrlimit(resource.RLIMIT_CPU, (job["cpu_seconds"], job["cpu_seconds"] + 1))
    resource.setrlimit(resource.RLIMIT_FSIZE, (32 * 1024 * 1024, 32 * 1024 * 1024))
    random.seed(job["seed"])
    np.random.seed(job["seed"])
    original_default_rng = np.random.default_rng
    np.random.default_rng = lambda seed=None: original_default_rng(job['seed'] if seed is None else seed)
    trace = {"prompts": [], "figures": [], "test_matrices": [], "test_comparisons": [], "error": "",
             "seed": job["seed"], "metadata": job["metadata"], "network": job["network"],
             "runtime": {"python": sys.version, "numpy": np.__version__, "matplotlib": matplotlib.__version__}}
    answers = iter(job["answers"])
    state = {"testing": False}

    def answer(prompt=""):
        try:
            value = next(answers)
        except StopIteration:
            raise EOFError("Console profile exhausted; inspect prompts and configure a pinned profile")
        trace["prompts"].append({"prompt": str(prompt), "answer": value})
        if value == job["test_csv"]:
            state["testing"] = True
        return value

    original_imshow = Axes.imshow

    def capture_matrix(axis, data, *args, **kwargs):
        values = np.asarray(data)
        if state["testing"] and values.ndim == 2 and values.shape[0] == values.shape[1]:
            trace["test_matrices"].append(values.astype(float).tolist())
        return original_imshow(axis, data, *args, **kwargs)

    def save_figures(*args, **kwargs):
        for number in list(plt.get_fignums()):
            figure = plt.figure(number)
            figure.canvas.draw()
            if state['testing']:
                for axis in figure.axes:
                    title = axis.get_title()
                    labels = axis.get_legend_handles_labels()[1]
                    semantic = (title + ' ' + ' '.join(labels)).lower()
                    if not any(word in semantic for word in ('correct', 'incorrect', 'acierto')):
                        continue
                    colors, points = {}, 0
                    for collection in axis.collections:
                        count = len(collection.get_offsets())
                        points += count
                        faces = collection.get_facecolors()
                        if len(faces) == 1:
                            faces = [faces[0]] * count
                        for face in faces:
                            color = to_hex(face)
                            colors[color] = colors.get(color, 0) + 1
                    trace['test_comparisons'].append({'title': title, 'labels': labels,
                                                      'points': points, 'colors': colors})
            name = f"grafico_{len(trace['figures']) + 1}.png"
            figure.savefig('/out/' + name, dpi=100, bbox_inches="tight")
            trace["figures"].append({"file": name, "stage": "test" if state["testing"] else "train",
                                     "titles": [axis.get_title() for axis in figure.axes]})
            plt.close(figure)

    builtins.input = answer
    Axes.imshow = capture_matrix
    plt.show = save_figures
    # Keep relative asset paths compatible with the original assignment directory.
    os.chdir('/src')
    sys.path.insert(0, '/src')
    try:
        runpy.run_path(source, run_name="__main__")
    except SystemExit as exc:
        if exc.code not in (None, 0):
            trace["error"] = f"SystemExit: {exc.code}"
    except BaseException:
        trace["error"] = traceback.format_exc(limit=12)
    finally:
        save_figures()
        with open('/out/traza.json', 'w', encoding='utf-8') as stream:
            json.dump(trace, stream, ensure_ascii=False, indent=2)
    if trace["error"]:
        print(trace["error"], file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
