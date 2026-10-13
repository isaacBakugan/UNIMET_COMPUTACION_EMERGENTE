# Corrección de la Tarea 5 — Sim City (grupal)

Espacio para la preparadora. Enunciado, rúbrica y contrato de ejecución para los estudiantes:
[repo-template/tarea-5-codigo/README.md](../../repo-template/tarea-5-codigo/README.md).
Esta carpeta trae la **configuración** y las **directrices**; el corrector y los tests los escribe la preparadora
siguiendo lo que hay aquí.

> Es la **primera tarea grupal de código**: un solo `simcity.py` + un `ciudad.txt` por repo. Se corrige **por equipo**,
> y cada integrante recibe la nota de su equipo (como el corte de preguntas), con la penalización por tardía **individual**.

## Qué hay ya en esta carpeta

| Archivo | Para qué |
|---|---|
| `tarea.json` | Rúbrica (2 criterios × 50/25/0, escala de 3 niveles estándar), escala 1–20, descuento por tardía (2) y cierre (`cutoff`) |
| `alumnos.csv` | **Una fila por equipo** (`team,file,student_name,national_id`, `file` = `simcity.py`); el nombre queda vacío: la entrega es del grupo |
| `entregas-tardias.csv` | Solo excepciones: commit exacto + descuento distinto de 2 |
| `decisiones-docente.json` | Decisiones manuales atadas a un commit exacto (empieza vacío) |

## Pendiente antes de corregir

- [ ] **Fijar `cutoff` en `tarea.json`.** Hoy tiene `2099-12-31T23:59:00-04:00` como centinela: con él todo cuenta
  como "a tiempo". Debe llevar zona horaria (`-04:00`).
- [ ] Escribir el **corrector** (`correcciones/calificador_tarea_5.py` + task `grade-tarea-5` en `pyproject.toml`).
- [ ] Escribir los **tests** en `correcciones/tests/` (ver "Gates" abajo).
- [ ] **Pedirle al profesor que aclare el enunciado** (ver "Ambigüedades"): sin eso, el segundo criterio solo se puede
  juzgar con un oráculo propio y revisión manual.

## Qué se corrige (los 2 criterios de `tarea.json`)

A diferencia de las Tareas 2 a 4, **sí se ejecuta el programa del estudiante**: los comandos están fijados por el enunciado
(`r`, `c`, `i`, `a`, `guardar`, `cargar`, `salir`, Enter), así que se puede manejar por stdin. El contrato de ejecución
que se les exigió está en el README del template (`python simcity.py` desde la carpeta, sin argumentos, `input()`,
cuadrícula impresa tras cada comando/tick, errores que empiezan con `Error`, rutas relativas, solo stdlib).

| Clave | Qué se hace | 50 | 25 | 0 |
|---|---|---|---|---|
| `blank_grid_add_zone` | Arrancar en blanco, agregar una zona (`r`/`c`/`i`), dar ticks | La zona aparece donde debe (3×3 celdas, letra del tipo, esquina sup. izq. en la celda pedida) y se actualiza con los ticks | Existe el comando pero la zona sale mal (posición, tamaño, letra) o no responde a los ticks | No hay forma de agregar una zona (o el programa no arranca) |
| `loaded_city_updates` | `cargar ciudad.txt`, agregar una zona o arteria, dar ticks | Carga, es modificable, y se actualiza según la **mayoría** de las reglas | Carga y corre ticks, pero la actualización no respeta la mayoría de las reglas | No carga, no es modificable o no se puede correr un tick |

Niveles: `correct` / `incorrect` / `no_result` (la escala estándar de `rubrica.py`). Nota = puntos sobre 100 → sobre 20,
**mínimo 1**.

### Guion de ejecución propuesto (entrada estándar)

```
# blank_grid_add_zone                    # loaded_city_updates
r c 4                                    cargar ciudad.txt
<Enter> x 5                              <Enter> x 5
salir                                    c <celda libre>  <- agrega una zona: debe aceptarla (elegida leyendo la cuadrícula)
                                         <Enter> x 5
                                         salir
```

Corre en el sandbox (`sandbox.py`: bubblewrap en WSL, sin red, fuentes de solo lectura) con **timeout** y tope de salida;
un programa que se cuelga o imprime sin fin es `no_result`/`incorrect`, nunca un cuelgue del corrector.

### Qué se puede verificar automáticamente (y qué no)

**Sin ambigüedad (se verifica directo sobre la cuadrícula impresa):**

- Geometría: 29 columnas × 15 filas, celda de 3 caracteres; una zona nueva es un bloque 3×3 celdas = 9×3 caracteres de la
  letra de su tipo en minúscula, con la esquina superior izquierda en la celda indicada. `r c 4` → C4:E6.
- Orden de lectura de las mayúsculas: el nivel `k` es las primeras `k` letras en orden de lectura (fila a fila), tope 27.
- `a c 7 p` dibuja `=` entre C7 y P7; `a F 4 9` dibuja `| |` entre F4 y F9; el cruce es `:+:`.
- **Celda ocupada → `Error`** y la cuadrícula **no cambia**.
- **Tráfico aislado:** una celda de arteria junto a **una** zona de nivel `L` tiene tráfico `sqrt(L)`; entre dos, la suma.
  Es el caso que el enunciado define sin ambigüedad (Figura 5: nivel 16 → 4; dos de nivel 16 → 8).
- `guardar` + `cargar` de la misma cuadrícula devuelve **la misma cuadrícula** (ida y vuelta).
- `cargar` **reemplaza por completo** la cuadrícula en pantalla.

**Con ambigüedad (no hay respuesta única; usar oráculo propio + revisión):**

El criterio dice "la **mayoría** de las reglas". La propuesta es construir una **ciudad de prueba pequeña** donde cada regla
de voto se pueda aislar (una zona + una sola causa de voto), medir en cuántos escenarios el programa del equipo hace lo que
la regla manda (crece / decrece / se mantiene) y fijar el umbral de "mayoría" en `> 50%` de los escenarios. Lo que dependa
de una decisión de diseño documentada por el equipo (distancia, combinación de votos) va a `needs_review` con la
explicación, nunca se penaliza automáticamente.

### Ambigüedades del enunciado (para el profesor)

| # | Punto | Cómo está en el template |
|---|---|---|
| 1 | El comando `i <celda>` dice "zona **comercial**" | Se asume **industrial** (typo): `c` ya es comercial |
| 2 | "A 10 celdas de distancia": ¿Manhattan/Chebyshev/euclidiana? ¿desde esquina, centro o borde? | **Decisión del equipo**, documentada en el `.py` |
| 3 | Cómo se combinan los votos y cuántos niveles se sube/baja por tick | **Decisión del equipo** |
| 4 | Residencial, decrecimiento: "cada zona industrial **a partir de la 11ª**, a 10 celdas" (¿la 11ª en qué orden?) | **Decisión del equipo** |
| 5 | Comercial, decrecimiento: "cada celda de arteria cuyo tráfico haya decrecido" — ¿cuáles? (no dice "adyacente") | **Decisión del equipo** |
| 6 | Tráfico de arterias que se tocan ("se considera el nivel de esa celda adyacente") | **Decisión del equipo** |
| 7 | Dibujo de un tráfico ≥ 10 en una celda de 3 caracteres (la Figura 5 muestra `26`) | **Decisión del equipo**; el corrector **no** parsea dígitos de tráfico ≥ 10 |
| 8 | Cuadrícula "88 × 16": con 29 columnas × 3 = 87 queda 1 carácter de margen, que no alcanza para las etiquetas de fila de dos dígitos | Se exige la geometría de celdas (29 × 15); el margen de etiquetas es libre |
| 9 | Solape de arterias paralelas y arterias fuera de la cuadrícula | Debe dar `Error` o resolverse documentado |
| 10 | Caption de la Figura 4 describe una arteria C7–P7 que no corresponde al dibujo (F4–F9) | Irrelevante para el corrector |

El PDF se llama "Enunciado Tarea 5-SimCity" y el encabezado dice **Tarea 5**.

## Directrices que ya rigen (misma mecánica que las Tareas 1 a 4 y el corte)

### Entrega tardía: individual, −2 puntos (aunque la entrega sea grupal)

- Todos los integrantes se evalúan sobre el **último commit anterior al cierre** de `tarea-5-codigo/`.
- Si hay commits posteriores al cierre, se evalúa **además** el último commit, con `late_penalty_points` menos, y quien
  hizo esos commits (por **email de autor**) recibe **la mejor** de las dos notas: un commit tardío nunca perjudica.
  Los compañeros que no tocaron nada tarde conservan la nota del cierre. Es exactamente la regla del corte
  (`corte.py` / `calificador_corte.py`): reutiliza esa mecánica, no la reinventes.
- El mapeo email → estudiante ya existe en [`corte-preguntas-1/autores.csv`](../corte-preguntas-1/autores.csv); un autor
  tardío sin mapear es una ADVERTENCIA. Si falta alguien, agrégalo ahí (es el registro del trimestre).
- La entrega tardía **se evalúa igual**, no se anula; el aviso queda en las ADVERTENCIAS y en las notas del informe.
- `entregas-tardias.csv` solo para excepciones. Nunca un `if team == ...` en el código.
- Los archivos del equipo son `simcity.py` y `ciudad.txt`: un commit es "posterior" si toca **cualquiera** de los dos.

### Decisiones docentes

- Lo que el corrector automático no puede decidir (una regla interpretada de forma defendible pero distinta de tu oráculo,
  un `ciudad.txt` con formato que no carga por un detalle menor...) va en `decisiones-docente.json`, **atado a
  `team + file + commit`** (`file` = `simcity.py`). Con `reason` obligatorio y, por criterio, `outcome`
  (`correct` / `incorrect` / `no_result`) + `explanation`.
- Si el equipo pushea otro commit, la decisión **caduca** y el corrector avisa ("Decisión docente obsoleta").

### Reporte

Todo en **orden alfabético por apellido** (fuente: `trimestre-actual/lista-entrega.csv`), cada integrante con la nota de su
equipo. Salidas en `correcciones/resultados/<trimestre>/tarea-5/` (ignorado por git), con el mismo formato que
`calificador_corte.py`:

| Salida | Contenido |
|---|---|
| **Consola** | Tabla por estudiante en orden alfabético y las `ADVERTENCIA:` al final |
| `notas-sheets.csv` | `Apellido,Nombre,Equipo,Nota,Observación`: **la columna `Nota` se pega tal cual en Google Sheets** |
| `notas.csv` | Detalle por **equipo** (commit evaluado, nivel y puntos por criterio, `needs_review`, comentario) |
| `informe.md` | Tabla resumen + advertencias + detalle por equipo con lo que se observó en cada criterio |

- Si lo corres antes del cierre, el reporte debe salir marcado **PRELIMINAR**.
- Reutiliza `lista.py` (cruce y orden), `entregas.py` (commit al cierre, `git archive`, `commits_after_cutoff_by_author` con
  `folder="tarea-5-codigo"`), `rubrica.py` (escala y nota) y `sandbox.py`.
- Prohibido en `simcity.py` (revisión estática): rutas absolutas, imports fuera de la librería estándar y
  APIs que exijan terminal interactiva (`curses`, `msvcrt`).

## Gates (los descubre por disco, sin registrar nada)

`correcciones/tests/test_calificador.py` ya recorre `correcciones/tarea-*/tarea.json`, por lo que esta carpeta queda
sujeta a que `tarea.json`, `decisiones-docente.json`, `alumnos.csv` y `entregas-tardias.csv` carguen y tengan las
columnas esperadas, y hay un test que exige **una sola fila por equipo** en `alumnos.csv` (tarea grupal). Los tests nuevos
de esta tarea (los escribe la preparadora) deben seguir lo que pide el repo:

- Descubrir sujetos **por disco** (el `simcity.py` y el `ciudad.txt` de cada repo) y fallar si no encuentran ninguno.
- Que la **plantilla sin tocar** (`simcity.py` con el placeholder y sin `ciudad.txt`) saque la **nota mínima**, no "pase
  por vacuidad" (un programa que no hace nada no puede dar 50).
- Que el **oráculo de referencia** (tu simulador mínimo) reproduzca los casos sin ambigüedad de arriba: geometría,
  `r c 4` → C4:E6, nivel 16 → mayúsculas en orden de lectura, tráfico `sqrt(16) = 4`, cruce `:+:`. Es el gate de que lo
  que mide el corrector es correcto antes de medir a nadie.
- Que "celda ocupada" produzca `Error` y deje la cuadrícula idéntica.
- Que el corrector **no se cuelgue** con un programa que no termina o que imprime sin fin (timeout y tope de salida).
- Verificar el gate **en rojo** antes de darlo por bueno (romper algo a propósito y comprobar que el mensaje nombra el
  equipo o archivo culpable).
- Correr con `task test` (`pytest repo-template/tests correcciones/tests`), que es la suite que bloquea el build.
