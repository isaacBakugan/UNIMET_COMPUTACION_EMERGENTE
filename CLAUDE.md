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
  preguntas, nombres de equipo), mensajes de commit (`[PREFIJO] ...`), nombres de rama.
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
  `correcciones/tarea-N/lista-entrega.csv` (`last_name,first_name,team`, ya ordenada). Reporte de consola,
  `informe.md`, `notas.csv` y `notas-sheets.csv` salen **siempre** en ese orden; nunca por equipo ni por archivo.
- `notas-sheets.csv` (`Apellido,Nombre,Equipo,Nota,Observación`) es el que se copia a Google Sheets: la columna
  `Nota` se pega tal cual, alineada con la lista de la planilla.
- Un archivo se cruza con la lista por el nombre de su cabecera (sin distinguir acentos ni mayúsculas). Los que
  no traen nombre se asignan **por equipo** a las entradas sin archivo y salen marcados **provisional**
  (`assignment = by_team`): confirmar a mano y, cuando se conozca, corregir la cabecera/`alumnos.csv`.
- Los nombres de equipo de `lista-entrega.csv` deben ser los de `trimestre-actual/estado.json` (`Cyberleak`,
  `areperos`, `LUMON`...); el gate de `correcciones/tests/test_lista.py` falla si hay un typo o el orden se rompe.
- Tarea nueva = carpeta `correcciones/tarea-N/` con `tarea.json`, `lista-entrega.csv`, `alumnos.csv`,
  `entregas-tardias.csv` y `decisiones-docente.json`: los gates la descubren por disco, sin registrarla en ningún lado.
- Las decisiones docentes (`decisiones-docente.json`) van atadas a un commit exacto: si el estudiante pushea otro,
  caducan y el corrector avisa. Nunca se hardcodea un `if team == ...` en el código.
