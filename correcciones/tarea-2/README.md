# Corrección de la Tarea 2 — Perceptrón multicapa

Espacio para la preparadora. Enunciado y rúbrica para los estudiantes:
[repo-template/tarea-2-codigo/README.md](../../repo-template/tarea-2-codigo/README.md).
Esta carpeta trae la **configuración** y las **directrices**; el corrector, los casos
ocultos y los tests los escribe la preparadora siguiendo lo que hay aquí.

## Qué hay ya en esta carpeta

| Archivo | Para qué |
|---|---|
| `tarea.json` | Rúbrica (4 criterios × 25/15/0), escala 1–20, descuento por tardía (2) y cierre (`cutoff`) |
| `alumnos.csv` | Lista de apoyo `team,file,student_name,national_id`; se llena solo si la cabecera del archivo no trae el nombre |
| `entregas-tardias.csv` | Solo excepciones: commit exacto + descuento distinto de 2 |
| `decisiones-docente.json` | Decisiones manuales atadas a un commit exacto (empieza vacío) |

## Pendiente antes de corregir

- [ ] **Fijar `cutoff` en `tarea.json`.** Hoy tiene `2099-12-31T23:59:00-04:00` como centinela: con él todo cuenta
  como "a tiempo". Debe llevar zona horaria (`-04:00`).
- [ ] Definir los **nombres de archivo de las dos redes entregadas** (CSV de perceptrón multicapa, formato del
  enunciado) y ponerlos en el README del template.
- [ ] Escribir el **corrector** (`correcciones/calificador_tarea_2.py` + task `grade-tarea-2` en `pyproject.toml`).
- [ ] Escribir los **casos ocultos** en `correcciones/tarea-2/casos/` (nunca en `repo-template/`): un ejemplo no visto
  de 2D/2 clases y uno de 3D/4 clases.
- [ ] Escribir los **tests** en `correcciones/tests/` (ver "Gates" abajo).

## Qué se corrige (los 4 criterios de `tarea.json`)

1. `given_network_2d_2class`: la red entregada para el ejemplo de 2D/2 clases se **carga** con el programa del
   estudiante y clasifica `assets/2-d_2-class_*.csv`.
2. `given_network_3d_4class`: ídem para 3D/4 clases con `assets/3-d_4-class_*.csv`.
3. `hidden_training_2d_2class`: los **hiperparámetros** de esa red (filas `u,v,L,b,e` del CSV) entrenan, desde cero,
   una red que clasifica un ejemplo **no visto** de 2D/2 clases.
4. `hidden_training_3d_4class`: ídem para 3D/4 clases.

Escala por criterio: correcto 25 · incorrecto 15 · no hace nada 0. Nota = puntos proporcionales sobre 20, **mínimo 1**.
Las claves de `criteria` son libres (`load_rubric` solo exige claves únicas): si cambias una, cámbiala también en el
corrector y en `decisiones-docente.json`.

## Directrices que ya rigen (misma mecánica que la Tarea 1)

### Entrega tardía: individual, −2 puntos

- Cada archivo `perceptron_multicapa_N.py` es de **un** estudiante, así que la tardanza también.
- Todos se evalúan sobre el **último commit anterior al cierre**.
- Si hay commits posteriores al cierre (en `tarea-2-codigo/<archivo>`), se evalúa **además** el último commit con
  `late_penalty_points` menos, y el estudiante recibe **la mejor** de las dos notas: un commit tardío nunca perjudica
  a quien entregó a tiempo.
- La entrega tardía **se evalúa igual**, no se anula; el aviso queda en las ADVERTENCIAS y en las notas del informe.
- `entregas-tardias.csv` solo para excepciones. Nunca un `if team == ...` en el código.

### Decisiones docentes

- Lo que el corrector automático no puede decidir (ruta absoluta de Windows, menú distinto, formato de CSV de red
  ambiguo...) va en `decisiones-docente.json`, **atado a `team + file + commit`**. Con `reason` obligatorio y, por
  criterio, `outcome` (`correct` / `incorrect` / `no_result`) + `explanation`.
- Si el estudiante pushea otro commit, la decisión **caduca** y el corrector avisa ("Decisión docente obsoleta").

### Reporte

Todo en **orden alfabético por apellido**, la fuente es `trimestre-actual/lista-entrega.csv`. Nunca por equipo ni por
archivo. Salidas en `correcciones/resultados/<trimestre>/tarea-2/` (ignorado por git):

| Salida | Contenido |
|---|---|
| **Consola** | Tabla `# · Apellido, nombre · Equipo · Archivo · C1..C4 · Rúbrica · Desc · Nota · Revisar`, `*` = asignación provisional, y al final las `ADVERTENCIA:` |
| `notas-sheets.csv` | `Apellido,Nombre,Equipo,Nota,Observación`: **la columna `Nota` se pega tal cual en Google Sheets**, alineada con la lista de la planilla |
| `notas.csv` | Detalle por archivo (commit evaluado, puntos por criterio, descuento, `needs_review`, comentario) |
| `informe.md` | Tabla resumen + advertencias + detalle por archivo con la explicación de cada criterio |

- Un archivo se cruza con la lista por el nombre de su **cabecera** (`# Nombre del integrante:`), sin distinguir acentos
  ni mayúsculas. Los que no traen nombre se asignan **por equipo** y salen marcados **provisional**
  (`assignment = by_team`): confirmar a mano.
- Si lo corres antes del cierre, el reporte debe salir marcado **PRELIMINAR**.
- Reutiliza `lista.py` (cruce y orden), `entregas.py` (commit al cierre, `git archive`), `rubrica.py` (escala y nota) y
  el sandbox de la Tarea 1 en vez de duplicarlos. Ojo: `entregas.py` hoy fija `ASSIGNMENT_DIR = "tarea-1-codigo"` y
  `ALLOWED_IMPORTS = {"matplotlib"}`; para esta tarea hay que parametrizar la carpeta (`export_assignment` ya acepta
  `folder`) y permitir `numpy`/`pandas`, y **prohibir** `torch`, `tensorflow` y afines.

## Gates (los descubre por disco, sin registrar nada)

`correcciones/tests/test_calificador.py` ya recorre `correcciones/tarea-*/tarea.json`, por lo que esta carpeta queda
sujeta a que `tarea.json`, `decisiones-docente.json`, `alumnos.csv` y `entregas-tardias.csv` carguen y tengan las
columnas esperadas. Los tests nuevos de esta tarea (los escribe la preparadora) deben seguir lo que pide el repo:

- Descubrir sujetos **por disco** y fallar si no encuentran ninguno.
- Que la plantilla sin tocar (`perceptron_multicapa_N.py` vacío) saque la **nota mínima**, no "pase por vacuidad".
- Que cada caso oculto exista en disco y tenga el encabezado esperado.
- Verificar el gate **en rojo** antes de darlo por bueno (romper algo a propósito y comprobar que el mensaje nombra
  el archivo culpable).
- Correr con `task test` (`pytest repo-template/tests correcciones/tests`), que es la suite que bloquea el build.
