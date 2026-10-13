# Corrección de la Tarea 4 — Algoritmo genético

Espacio para la preparadora. Enunciado, rúbrica y contratos de entrega para los estudiantes:
[repo-template/tarea-4-codigo/README.md](../../repo-template/tarea-4-codigo/README.md).
Esta carpeta trae la **configuración** y las **directrices**; el corrector y los tests los escribe la preparadora
siguiendo lo que hay aquí.

> El PDF del enunciado se llama "Tarea 5" pero el encabezado dice **Tarea 4**; se tomó la Tarea 4.

## Qué hay ya en esta carpeta

| Archivo | Para qué |
|---|---|
| `tarea.json` | Rúbrica (4 criterios con escala de 4 niveles y pesos 20/20/30/30), escala 1–20, descuento por tardía (2) y cierre (`cutoff`) |
| `alumnos.csv` | Lista de apoyo `team,file,student_name,national_id` (`file` = `algoritmo_genetico_N.py`); se llena solo si la cabecera del archivo no trae el nombre |
| `entregas-tardias.csv` | Solo excepciones: commit exacto + descuento distinto de 2 |
| `decisiones-docente.json` | Decisiones manuales atadas a un commit exacto (empieza vacío) |

`rubrica.py` ya soporta escalas de N niveles (`outcomes`) desde la Tarea 3; aquí cada criterio tiene su propia escala
de puntos (20/14/7/0 en la función `a`, 30/20/10/0 en la `b`), y `rubric_grade` normaliza sobre los 100 puntos.
Como el calificador de la Tarea 1 sigue validando las decisiones docentes contra 3 niveles fijos, el corrector nuevo
debe usar `criterion_outcomes(item)`.

## Pendiente antes de corregir

- [ ] **Fijar `cutoff` en `tarea.json`.** Hoy tiene `2099-12-31T23:59:00-04:00` como centinela: con él todo cuenta
  como "a tiempo". Debe llevar zona horaria (`-04:00`).
- [ ] Escribir el **corrector** (`correcciones/calificador_tarea_4.py` + task `grade-tarea-4` en `pyproject.toml`).
- [ ] Escribir los **tests** en `correcciones/tests/` (ver "Gates" abajo).
- [ ] **Definir con el profesor qué es "distribución adecuada"** (ver más abajo): es el criterio que decide la nota y
  el enunciado no lo cuantifica. Hasta entonces, lo que el corrector no pueda decidir va a `needs_review`.
- [ ] Confirmar con el profesor qué hace el **umbral de diferencia** (el PDF no lo define; el template le pide al
  estudiante que documente su interpretación en un comentario).
- [ ] Confirmar qué cuenta como "commit posterior al cierre" (ver "Entrega tardía").

## Qué se corrige (los 4 criterios de `tarea.json`)

La corrección **no ejecuta el programa del estudiante**: carga sus archivos de población según el contrato del README
del template (`population_N_{a|b}_{low|high}.json`) y los evalúa contra las **funciones de referencia del curso**, nunca
contra el `funcion_*_N.py` del estudiante (podrían editarlo).

| Clave | Archivo | Puntos (adecuada / params / problema / no carga) |
|---|---|---|
| `low_mutation_function_a` | `population_N_a_low.json` | 20 / 14 / 7 / 0 |
| `high_mutation_function_a` | `population_N_a_high.json` | 20 / 14 / 7 / 0 |
| `low_mutation_function_b` | `population_N_b_low.json` | 30 / 20 / 10 / 0 |
| `high_mutation_function_b` | `population_N_b_high.json` | 30 / 20 / 10 / 0 |

Niveles (`outcomes`): `adequate` · `inadequate_params` (inadecuada para sus parámetros pero obedece al problema) ·
`inadequate_problem` · `no_result` (no carga). Nota = puntos proporcionales sobre 20, **mínimo 1**.

### Funciones de referencia y óptimos (calculados numéricamente, malla de 4·10⁶ puntos)

| | Función | Óptimo global en [-10, 10] | Otros máximos locales |
|---|---|---|---|
| **a** | `y = sin²(x)/x` (en `x = 0` el límite es 0) | `x ≈ 1.1656`, `y ≈ 0.7246` | `x ≈ 4.604` (0.2147), `x ≈ 7.790` (0.1278) |
| **b** | `z = 20 + x − 10·cos(2πx) + y − 10·cos(2πy)` | `x = y ≈ 9.5025`, `z ≈ 59.0025` | Un pico por unidad en cada eje (≈ 20 por eje, 400 en total; los de `x, y ≈ 8.5025` y `7.5025` rinden ≈ 57 y ≈ 55) |

Notas que importan para juzgar:

- **a:** el mínimo global es el espejo (`x ≈ -1.1656`, `y ≈ -0.7246`): una población que **minimiza** en vez de maximizar
  cae aquí. Es el error típico; debe salir como `inadequate_problem`.
- **b:** el óptimo está **pegado al borde** (`x = 10` da `z = 20`; el pico real está en 9.5025). Una mutación que se
  salga de `[-10, 10]` debe contar como miembro inválido.
- Cada `fitness` del archivo se **recalcula** con la función de referencia; si no coincide con `variables`, el archivo es
  inconsistente (la población fue editada o la función del estudiante está mal).

### Propuesta de clasificación (por confirmar con el profesor)

El enunciado dice "distribución adecuada para sus parámetros y el problema", sin números. Propuesta de proxy
automático, con las tolerancias **por fijar** (no están en `tarea.json` a propósito, hasta que haya acuerdo):

1. **`no_result`:** el archivo falta, no es JSON válido, no cumple el contrato, o `members` no tiene `population_size`
   miembros.
2. **`inadequate_problem`:** carga, pero la población no obedece al problema: miembros fuera de `[-10, 10]`, `fitness`
   que no coincide con la función de referencia, o el mejor miembro lejos de **todos** los máximos (p. ej. minimiza).
3. **`inadequate_params`:** obedece al problema (el mejor miembro cae en un máximo, global o local) pero **no es
   coherente con sus parámetros**: variabilidad en el lado equivocado de 1 (`low` con ≥ 1, `high` con ≤ 1),
   `generations_elapsed` mayor que `max_generations`, o dispersión que no corresponde a la variabilidad declarada
   (con baja variabilidad se espera una población concentrada; con alta, más dispersa).
4. **`adequate`:** todo lo anterior bien **y** el mejor miembro dentro de la tolerancia del **óptimo global**.

Lo que no se pueda decidir con estas reglas va a `needs_review` con la explicación (nunca un `if team == ...`).

## Directrices que ya rigen (misma mecánica que las Tareas 1 a 3)

### Entrega tardía: individual, −2 puntos

- Cada `algoritmo_genetico_N.py` es de **un** estudiante, así que la tardanza también.
- Todos se evalúan sobre el **último commit anterior al cierre**.
- Si hay commits posteriores al cierre, se evalúa **además** el último commit con `late_penalty_points` menos, y el
  estudiante recibe **la mejor** de las dos notas: un commit tardío nunca perjudica a quien entregó a tiempo.
- **Propuesta (por confirmar):** los archivos de un estudiante son `algoritmo_genetico_N.py`, `funcion_a_N.py`,
  `funcion_b_N.py` y sus cuatro `population_N_*.json`; un commit es "posterior" si toca **cualquiera** de esos siete.
  Exporta solo los de `N` (la carpeta trae también los de los otros integrantes).
- La entrega tardía **se evalúa igual**, no se anula; el aviso queda en las ADVERTENCIAS y en las notas del informe.
- `entregas-tardias.csv` solo para excepciones. Nunca un `if team == ...` en el código.

### Decisiones docentes

- Lo que el corrector automático no puede decidir (una población con otro formato, una interpretación del umbral que
  cambie la dispersión esperada...) va en `decisiones-docente.json`, **atado a `team + file + commit`**. Con `reason`
  obligatorio y, por criterio, `outcome` (uno de los niveles de la escala del criterio) + `explanation`.
- Si el estudiante pushea otro commit, la decisión **caduca** y el corrector avisa ("Decisión docente obsoleta").

### Reporte

Todo en **orden alfabético por apellido**, la fuente es `trimestre-actual/lista-entrega.csv`. Nunca por equipo ni por
archivo. Salidas en `correcciones/resultados/<trimestre>/tarea-4/` (ignorado por git):

| Salida | Contenido |
|---|---|
| **Consola** | Tabla `# · Apellido, nombre · Equipo · Archivo · C1..C4 · Rúbrica · Desc · Nota · Revisar`, `*` = asignación provisional, y al final las `ADVERTENCIA:` |
| `notas-sheets.csv` | `Apellido,Nombre,Equipo,Nota,Observación`: **la columna `Nota` se pega tal cual en Google Sheets**, alineada con la lista de la planilla |
| `notas.csv` | Detalle por archivo (commit evaluado, nivel y puntos por criterio, descuento, `needs_review`, comentario) |
| `informe.md` | Tabla resumen + advertencias + detalle por archivo con la métrica medida y el nivel de cada criterio |

- Un archivo se cruza con la lista por el nombre de su **cabecera** (`# Nombre del integrante:`, en
  `algoritmo_genetico_N.py`, igual que en la Tarea 2), sin distinguir acentos ni mayúsculas. Los que no traen nombre se
  asignan **por equipo** y salen marcados **provisional** (`assignment = by_team`): confirmar a mano.
- Si lo corres antes del cierre, el reporte debe salir marcado **PRELIMINAR**.
- Reutiliza `lista.py` (cruce y orden), `entregas.py` (commit al cierre, `git archive`, cabecera) y `rubrica.py` (escala y
  nota). Ojo: `entregas.py` hoy fija `ASSIGNMENT_DIR = "tarea-1-codigo"` (`export_assignment` ya acepta `folder`) y
  `ALLOWED_IMPORTS = {"matplotlib"}`; para esta tarea se permite la librería estándar y `numpy`, y se revisa
  estáticamente que el `.py` **no tenga rutas absolutas** ("debe poder ejecutarse en cualquier computadora") y compile.
- Los `.json` de estudiantes son datos no confiables: se leen con `json` puro, nunca se ejecuta nada de ellos.

## Gates (los descubre por disco, sin registrar nada)

`correcciones/tests/test_calificador.py` ya recorre `correcciones/tarea-*/tarea.json`, por lo que esta carpeta queda
sujeta a que `tarea.json`, `decisiones-docente.json`, `alumnos.csv` y `entregas-tardias.csv` carguen y tengan las
columnas esperadas. Los tests nuevos de esta tarea (los escribe la preparadora) deben seguir lo que pide el repo:

- Descubrir sujetos **por disco** (los `algoritmo_genetico_N.py` y `population_N_*.json` de cada repo) y fallar si no
  encuentran ninguno.
- Que la **plantilla sin tocar** (los `.py` con el placeholder y sin poblaciones) saque la **nota mínima**, no "pase por
  vacuidad".
- Que las funciones de referencia devuelvan en el óptimo de la tabla de arriba el valor esperado (a: 0.7246 en 1.1656;
  b: 59.0025 en 9.5025, 9.5025) y que `x = 0` en la función `a` no lance excepción: es el gate de que la referencia
  del corrector es correcta.
- Que una población cuyo `fitness` no coincide con la función de referencia, o con miembros fuera de `[-10, 10]`, no
  llegue a `adequate`, y que el mensaje nombre el archivo culpable.
- Verificar el gate **en rojo** antes de darlo por bueno (romper algo a propósito y comprobar que el mensaje nombra el
  archivo culpable).
- Correr con `task test` (`pytest repo-template/tests correcciones/tests`), que es la suite que bloquea el build.
