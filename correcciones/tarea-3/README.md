# Corrección de la Tarea 3 — PyTorch

Espacio para la preparadora. Enunciado, rúbrica y contrato de entrega para los estudiantes:
[repo-template/tarea-3-codigo/README.md](../../repo-template/tarea-3-codigo/README.md).
Esta carpeta trae la **configuración** y las **directrices**; el corrector y los tests los escribe la preparadora
siguiendo lo que hay aquí.

## Qué hay ya en esta carpeta

| Archivo | Para qué |
|---|---|
| `tarea.json` | Rúbrica (4 criterios × escala de 5 niveles 25/15/10/5/0 + umbrales de accuracy), escala 1–20, descuento por tardía (2) y cierre (`cutoff`) |
| `alumnos.csv` | Lista de apoyo `team,file,student_name,national_id` (`file` = `pytorch_fashion_N.ipynb`); se llena solo si la cabecera del notebook no trae el nombre |
| `entregas-tardias.csv` | Solo excepciones: commit exacto + descuento distinto de 2 |
| `decisiones-docente.json` | Decisiones manuales atadas a un commit exacto (empieza vacío) |

## Qué cambió en el código compartido

`correcciones/rubrica.py` ya acepta **escalas de N niveles**: un criterio puede declarar `outcomes` (nombres de nivel,
de mejor a peor) y `thresholds` (cota inferior exclusiva de accuracy para alcanzar cada nivel). Sin `outcomes` sigue
siendo la escala de 3 niveles (`correct`/`incorrect`/`no_result`) de las Tareas 1 y 2, que no se tocaron.
`load_rubric` valida que los puntos y los umbrales sean estrictamente descendentes; los tests
`test_rubric_rejects_a_broken_five_level_scale` lo cubren (y fueron verificados en rojo).

**Pendiente de generalizar:** `calificador.py` (Tarea 1) todavía valida `outcome` de las decisiones docentes contra los
tres niveles fijos. El corrector de esta tarea debe usar `criterion_outcomes(item)` en vez de esa lista.

## Pendiente antes de corregir

- [ ] **Fijar `cutoff` en `tarea.json`.** Hoy tiene `2099-12-31T23:59:00-04:00` como centinela: con él todo cuenta
  como "a tiempo". Debe llevar zona horaria (`-04:00`).
- [ ] Escribir el **corrector** (`correcciones/calificador_tarea_3.py` + task `grade-tarea-3` en `pyproject.toml`).
- [ ] Escribir los **tests** en `correcciones/tests/` (ver "Gates" abajo).
- [ ] Confirmar con el profesor la **errata del enunciado** (segunda capa oculta convolucional: 258 en el PDF, 268 por
  interpolación lineal). El corrector **no debe** validar el número exacto de neuronas, solo el accuracy.
- [ ] Confirmar qué cuenta como "commit posterior al cierre" (ver "Entrega tardía").

## Qué se corrige (los 4 criterios de `tarea.json`)

Para cada notebook `pytorch_fashion_N.ipynb`, se cargan sus cuatro `.pth` y se mide el **accuracy sobre el conjunto de
prueba de Fashion MNIST** (10 000 imágenes):

| Clave | Archivo | Clases | Umbrales (accuracy) |
|---|---|---|---|
| `original_rectangular` | `pytorch_fashion_N_original_rectangular.pth` | 10 | > 0.75 · > 0.5 · > 0.1 |
| `original_convolutional` | `pytorch_fashion_N_original_convolutional.pth` | 10 | > 0.75 · > 0.5 · > 0.1 |
| `simplified_rectangular` | `pytorch_fashion_N_simplified_rectangular.pth` | 4 | > 0.8 · > 0.5 · > 0.25 |
| `simplified_convolutional` | `pytorch_fashion_N_simplified_convolutional.pth` | 4 | > 0.8 · > 0.5 · > 0.25 |

Niveles (puntos por criterio): `great_majority` 25 · `majority` 15 · `better_than_chance` 10 · `worse_than_chance` 5 ·
`no_result` 0. Los umbrales viven en `tarea.json` (no hardcodeados en el corrector).

- **`worse_than_chance` vs `no_result`:** el `.pth` carga y evalúa pero queda por debajo del umbral de azar →
  `worse_than_chance`. El archivo falta, no carga o no cumple el contrato → `no_result`.
- Nota = puntos proporcionales sobre 20 (100 pts = 20), **mínimo 1**. `rubric_grade` ya lo hace con la escala nueva.
- Las clases simplificadas se derivan de las etiquetas nativas de Fashion MNIST (la tabla está en el README del template):
  Top = {0, 2, 4, 6}, Bottom = {1, 3}, Footwear = {5, 7, 9}, Bag = {8}.

### Cómo se carga un `.pth` (contrato del README del template)

La corrección **no ejecuta el notebook** (el menú usa `input()` y no es automatizable): carga el `.pth` directamente.

- Formato: `{"state_dict": ..., "hyperparameters": {...}}`.
- Modelo: `nn.Sequential` que empieza en `Flatten` y usa solo `Linear`, `ReLU`, `BatchNorm1d`, `Dropout`. Se
  reconstruye a partir de las formas del `state_dict` (pesos 2D = `Linear`; `running_mean` = `BatchNorm1d`).
- Entrada: `ToTensor()` → `[0, 1]`, sin `Normalize` fuera del modelo.
- Orden de salida: 10 clases = orden nativo de Fashion MNIST; 4 clases = `0` Top, `1` Bottom, `2` Footwear, `3` Bag.
- **Cargar con `torch.load(..., weights_only=True)`** y correr en un proceso aparte con timeout: los `.pth` son archivos
  de estudiantes (pickle) y nunca deben cargarse sin `weights_only`. Reutiliza el patrón de `sandbox.py` para el aislamiento.
- Si un `.pth` incumple el contrato pero es evidentemente una red válida, no lo arregles en el código: va a
  `decisiones-docente.json` (ver abajo).
- El **hardware no debe importar**: evaluar en CPU, con `torch.manual_seed` fijo si algo es estocástico (en `eval()`
  `Dropout` es inerte, pero `BatchNorm1d` debe estar en modo `eval`).

## Directrices que ya rigen (misma mecánica que las Tareas 1 y 2)

### Entrega tardía: individual, −2 puntos

- Cada `pytorch_fashion_N.ipynb` es de **un** estudiante, así que la tardanza también.
- Todos se evalúan sobre el **último commit anterior al cierre**.
- Si hay commits posteriores al cierre, se evalúa **además** el último commit con `late_penalty_points` menos, y el
  estudiante recibe **la mejor** de las dos notas: un commit tardío nunca perjudica a quien entregó a tiempo.
- **Propuesta (por confirmar):** los archivos de un estudiante son `pytorch_fashion_N.ipynb` + sus cuatro
  `pytorch_fashion_N_*.pth`; un commit es "posterior" si toca **cualquiera** de esos cinco. Ojo: `git archive` de la
  carpeta completa traería también los archivos de los otros dos integrantes; exporta solo los de `N`.
- La entrega tardía **se evalúa igual**, no se anula; el aviso queda en las ADVERTENCIAS y en las notas del informe.
- `entregas-tardias.csv` solo para excepciones. Nunca un `if team == ...` en el código.

### Decisiones docentes

- Lo que el corrector automático no puede decidir (un `.pth` con otro contenedor, una red con capas no soportadas,
  normalización incompatible...) va en `decisiones-docente.json`, **atado a `team + file + commit`**. Con `reason`
  obligatorio y, por criterio, `outcome` (uno de los niveles de la escala del criterio) + `explanation`.
- Si el estudiante pushea otro commit, la decisión **caduca** y el corrector avisa ("Decisión docente obsoleta").

### Reporte

Todo en **orden alfabético por apellido**, la fuente es `trimestre-actual/lista-entrega.csv`. Nunca por equipo ni por
archivo. Salidas en `correcciones/resultados/<trimestre>/tarea-3/` (ignorado por git):

| Salida | Contenido |
|---|---|
| **Consola** | Tabla `# · Apellido, nombre · Equipo · Archivo · C1..C4 · Rúbrica · Desc · Nota · Revisar`, `*` = asignación provisional, y al final las `ADVERTENCIA:` |
| `notas-sheets.csv` | `Apellido,Nombre,Equipo,Nota,Observación`: **la columna `Nota` se pega tal cual en Google Sheets**, alineada con la lista de la planilla |
| `notas.csv` | Detalle por archivo (commit evaluado, accuracy y nivel por criterio, descuento, `needs_review`, comentario) |
| `informe.md` | Tabla resumen + advertencias + detalle por archivo con el accuracy medido y el nivel de cada criterio |

- Un archivo se cruza con la lista por el nombre de su **cabecera** (primera celda del notebook: `**Nombre del
  integrante:**`), sin distinguir acentos ni mayúsculas. Los que no traen nombre se asignan **por equipo** y salen
  marcados **provisional** (`assignment = by_team`): confirmar a mano.
- Si lo corres antes del cierre, el reporte debe salir marcado **PRELIMINAR**.
- Reutiliza `lista.py` (cruce y orden), `entregas.py` (commit al cierre, `git archive`), `rubrica.py` (escala y nota).
  Ojo: `entregas.py` hoy fija `ASSIGNMENT_DIR = "tarea-1-codigo"` (`export_assignment` ya acepta `folder`) y sus
  helpers asumen `.py`: aquí la cabecera está dentro del JSON del `.ipynb` (`cells[0].source`), y los imports prohibidos
  no aplican (PyTorch **es** la librería de la tarea).

## Gates (los descubre por disco, sin registrar nada)

`correcciones/tests/test_calificador.py` ya recorre `correcciones/tarea-*/tarea.json`, por lo que esta carpeta queda
sujeta a que `tarea.json`, `decisiones-docente.json`, `alumnos.csv` y `entregas-tardias.csv` carguen y tengan las
columnas esperadas, y a que la escala de 5 niveles y sus umbrales sean válidos. Los tests nuevos de esta tarea (los
escribe la preparadora) deben seguir lo que pide el repo:

- Descubrir sujetos **por disco** (los `pytorch_fashion_N.ipynb` y `.pth` de cada repo) y fallar si no encuentran ninguno.
- Que la **plantilla sin tocar** (notebook sin código y sin `.pth`) saque la **nota mínima**, no "pase por vacuidad".
- Que cada `.pth` cumpla el contrato (formato `dict`, solo capas permitidas, forma de entrada 784, salida 10 o 4) y que
  el mensaje nombre el archivo culpable.
- Que el mapeo de clases simplificadas cubra las 10 clases exactamente una vez (una clase sin asignar o repetida
  falsea todos los accuracy de 4 clases).
- Verificar el gate **en rojo** antes de darlo por bueno (romper algo a propósito y comprobar que el mensaje nombra el
  archivo culpable).
- Correr con `task test` (`pytest repo-template/tests correcciones/tests`), que es la suite que bloquea el build.
