# Repositorio Central de Evaluación Emergente

Ver [README.md](README.md) para la arquitectura completa (repo central + N repos de
grupo por trimestre, corrección automática, guards de copias).

## Estándar de código: inglés en código, español en documentos

Regla obligatoria en todo el repo. Detalle completo y ejemplos en
[guias/estandares-de-codigo.md](guias/estandares-de-codigo.md). Resumen:

- **Inglés**: nombres de variables/funciones/parámetros, comentarios de código, claves de
  JSON, valores tipo enum (`true_false`, `active`, `tuesday-week-1`), mensajes de log de
  los scripts (`Write-Host`, `assert`).
- **Español**: todo `.md`, el contenido que lee un estudiante o el profesor (texto de
  preguntas, nombres de equipo), mensajes de commit (`prefijo: Se hace tal cosa`, sin corchetes: `feat:`, `fix:`, `infra:`, `docs:`, `ref:`), nombres de rama.
- **Sin traducir**: nombres de carpetas/archivos ya establecidos (`formatos/`,
  `correcciones/`, `corte-preguntas-1/`, `crear-repos-trimestre.ps1`, `equipos.json`, ...).

Antes de agregar un test, script o esquema nuevo, seguir esa línea — no "todo en inglés",
sino estructura en inglés / contenido humano en español.

## Convenciones que ya están en el repo, no reinventar

- **Idempotencia**: `crear-repos-trimestre.ps1` y `actualizar-repos-trimestre.ps1` nunca
  recrean ni pisan un repo/archivo que ya existe sin necesidad. Cualquier script nuevo que
  toque repos de grupo sigue el mismo patrón.
- **Modelo de delegado**: no se conocen los usernames de GitHub de todo el curso. Solo se
  invita al delegado de cada equipo (`trimestre-actual/equipos.json`); el delegado agrega
  al resto desde GitHub.
- **`repo-template/` es lo único que ven los estudiantes**: cualquier archivo ahí se
  pushea a cada repo de grupo. `trimestre-actual/` y el resto del repo central son
  operativos, para el profesor, y nunca se pushean tal cual.
- **Los entregables de los alumnos nunca se sobreescriben**: archivos como `preguntas.json` o `perceptron_X.py` son la respuesta real del estudiante, no solo un placeholder del template. **Regla de oro:** Conforme se publiquen nuevas tareas, DEBES agregar los nombres de sus archivos a la lista `$PreservedFiles` dentro de `scripts/actualizar-repos-trimestre.ps1`.
- **Repos siempre públicos, nunca en organización** (`gh repo create ... --public`, sin
  `--org`).
- Un test/gate nuevo que valide formato de un entregable debe fallar en rojo cuando no hay
  solución todavía (no asumir contenido que no existe) — así se comprobó con cada test de
  este repo antes de darlo por bueno.

## Corrección de tareas: un comando, orden alfabético

`python correcciones/calificador.py` (task `grade`; `--update` refresca antes los clones) corrige la Tarea 1
de todos los estudiantes y deja en `correcciones/resultados/<trimestre>/tarea-1/` (ignorado por git):
`notas.csv`, `informe.md` y `notas-sheets.csv`. Detalle de uso en [README.md](README.md).

- **Las notas se entregan en orden alfabético por apellido.** La fuente de ese orden es
  `trimestre-actual/lista-entrega.csv` (`last_name,first_name,team`, ya ordenada). Reporte de consola,
  `informe.md`, `notas.csv` y `notas-sheets.csv` salen **siempre** en ese orden; nunca por equipo ni por archivo.
- `notas-sheets.csv` (`Apellido,Nombre,Equipo,Nota,Observación`) es el que se copia a Google Sheets: la columna
  `Nota` se pega tal cual, alineada con la lista de la planilla.
- Un archivo se cruza con la lista por el nombre de su cabecera (sin distinguir acentos ni mayúsculas). Los que
  no traen nombre se asignan **por equipo** a las entradas sin archivo y salen marcados **provisional**
  (`assignment = by_team`): confirmar a mano y, cuando se conozca, corregir la cabecera/`alumnos.csv`.
- Los nombres de equipo de `lista-entrega.csv` deben ser los de `trimestre-actual/estado.json` (`Cyberleak`,
  `areperos`, `LUMON`...); el gate de `correcciones/tests/test_lista.py` falla si hay un typo o el orden se rompe.
- Tarea nueva = carpeta `correcciones/tarea-N/` con `tarea.json`, `alumnos.csv`,
  `entregas-tardias.csv` y `decisiones-docente.json`: los gates la descubren por disco, sin registrarla en ningún lado.
- Las decisiones docentes (`decisiones-docente.json`) van atadas a un commit exacto: si el estudiante pushea otro,
  caducan y el corrector avisa. Nunca se hardcodea un `if team == ...` en el código.

## Corrección del corte de preguntas: las pruebas del alumno SON la evaluación

`python correcciones/calificador_corte.py` (task `grade-corte`; `--update` hace `git fetch` de los repos primero)
corrige `corte-preguntas-1` de todos los equipos. Misma salida que la Tarea 1 en
`correcciones/resultados/<trimestre>/corte-preguntas-1/` (`notas.csv` por equipo, `notas-sheets.csv` por
estudiante en orden alfabético, `informe.md`).

- **Una sola fuente de verdad:** el corrector corre `repo-template/corte-preguntas-1/tests/test_validar_entregable_1.py`
  (el mismo archivo que corren los alumnos) con `QUESTIONS_FILE` apuntando al `preguntas.json` del commit al cierre.
  Nunca la copia del repo del alumno, que podrían editar. Cambiar una regla = editar ese test.
- **Cada test debe pertenecer a un criterio de `correcciones/corte-preguntas-1/corte.json`** (4 criterios × 5 pts,
  crédito proporcional). El gate en `correcciones/tests/test_corte.py` descubre los tests por AST y falla si agregas
  un test sin asignarlo a un criterio (o si dejas uno obsoleto).
- **La plantilla sin tocar debe sacar la nota mínima.** Los placeholders (`PONGAN AQUÍ`, `(edítenla)`) no cuentan como
  preguntas, y `load_questions()` falla si no hay ninguna, para que nada pase "por vacuidad". Gate:
  `test_gate_the_untouched_template_scores_the_minimum_grade`.
- Cierre en `corte.json` (`cutoff`, zona -04:00). **Regla de la rúbrica: la entrega tardía se evalúa igual y se penaliza
  con 2 puntos menos (`late_penalty_points`), y la penalización es INDIVIDUAL, no por equipo.** Todos reciben la nota del
  último commit anterior al cierre; quien hizo commits posteriores (por email de autor, `corte-preguntas-1/autores.csv`)
  recibe `max(versión al cierre, versión final - 2)`: un commit tardío nunca perjudica. Autor tardío sin mapear = ADVERTENCIA.
  Gate: `test_gate_every_author_maps_to_a_student_of_the_delivery_list`.
- En la Tarea 1 cada archivo ya es de un estudiante: misma regla (evalúa el último commit con -2 y toma la mejor versión);
  `entregas-tardias.csv` solo para excepciones.
- Alcance de la regla de fáciles (< 3) / difíciles (> 7): constante `DIFFICULTY_SCOPE` del test (`"total"` o `"reading"`).
- La lista de entrega alfabética (`trimestre-actual/lista-entrega.csv`) es del trimestre y la comparten todas las
  correcciones; en el corte cada integrante recibe la nota de su equipo.

## Cortes de preguntas 2, 3 y 4: criterios deterministas

`python correcciones/calificador_corte.py --corte corte-preguntas-N` (tasks `grade-corte-2`, `-3`, `-4`). Mismo corrector y
misma regla de entrega tardía individual; config en `correcciones/corte-preguntas-N/` (`corte.json`, `autores.csv` propio).

- **Lecturas** (5 V/F + 5 selección por lectura): corte 2 = martes y jueves sem. 3 y 4 + martes sem. 5 (**50 preguntas**);
  corte 3 = martes y jueves sem. 7 y 8 (40); corte 4 = martes y jueves sem. 9 + martes sem. 10 y 11 (40).
- Los tres cortes tienen **las mismas reglas**; un gate lo exige (el test de cada corte solo puede diferir en `VALID_READINGS`
  y el total, y una lectura no puede repetirse entre cortes). Un corte nuevo con los mismos criterios queda sujeto por estar en disco.
- Criterios (sobre 20): `count` 11 (la mayoría), `format` 3, `difficulty` 3 (≥10 preguntas en cada banda 1-3 / 4-6 / 7-10),
  `balance` 3 (V/F 40-60 % `Verdadero`; ninguna posición A-D > 50 % de las correctas). Todos deterministas, sin LLM.
- Selección simple: **exactamente 4 opciones**, sin repetidas ni "todas/ninguna de las anteriores". Cada pregunta lleva
  `source_quote` (cita literal de la lectura, ≥ 20 caracteres); la verificación contra el texto de la lectura y la
  evaluación de calidad con LLM son la fase siguiente.
- Los escenarios de puntaje y esos gates están en `correcciones/tests/test_cortes_deterministas.py` (corren contra cada corte
  con criterios deterministas); los gates genéricos de `test_corte.py` cubren cualquier `corte-*/corte.json` (cada test asignado
  a un criterio, plantilla sin tocar = nota mínima).
- `cutoff` de cada `corte.json` está en 2099-12-31 hasta que se fije la fecha real (el reporte sale PRELIMINAR).
