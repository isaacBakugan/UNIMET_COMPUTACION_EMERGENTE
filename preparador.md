# Guía del preparador

Cómo trabajar en este repo: traer los cambios del resto, subir los tuyos, y generar las notas del
trimestre en tu máquina. Arquitectura y detalle de cada corrector: [README.md](README.md).
Estándar de código: [CLAUDE.md](CLAUDE.md) y [GUIAS/estandares-de-codigo.md](GUIAS/estandares-de-codigo.md).

## 1. Dinámica de trabajo

```
tú ──push──▶ develop ──Pull Request (el profe revisa y aprueba)──▶ main
```

- **Tú trabajas y subes a `develop`. Nunca a `main`.**
- El profe revisa el Pull Request `develop → main`, lo aprueba y hace el merge. Solo lo que está en `main` se
  considera oficial.
- `main` es lo que se reparte a los estudiantes (`repo-template/`) y lo que corre el CI; `develop` es tu zona de
  trabajo.

### Preparación inicial (una sola vez)

```powershell
git clone https://github.com/isaacBakugan/UNIMET_COMPUTACION_EMERGENTE.git
cd UNIMET_COMPUTACION_EMERGENTE
git switch develop
python -m pip install pytest matplotlib numpy
gh auth login                          # para clonar/crear/actualizar repos de grupo
```

Para correr el sandbox de la Tarea 1 (WSL + bubblewrap, sin red): `sudo apt install bubblewrap python3-matplotlib`.

> **Profe, una sola vez:** crear `develop` (`git switch -c develop; git push -u origin develop`), dar permiso de
> escritura al preparador y activar protección de `main` (Settings > Branches > *Require a pull request before merging*
> con aprobación). Hoy `main` no tiene protección.

### Traerte los cambios de los demás (un comando)

```powershell
git pull origin develop
```

Hazlo **siempre antes de empezar a trabajar** y antes de hacer push. Si Git te dice que hay conflictos, resuélvelos
en local, `git add` + `git commit`, y recién ahí sigues.

### Subir tu trabajo

```powershell
git status                                  # revisa QUÉ vas a subir (ver sección 2)
git add <archivos concretos>                # evita `git add .` a ciegas
git diff --cached --name-only               # última mirada: ¿hay notas o código de estudiantes aquí?
git commit -m "feat: Se agrega el corrector de la Tarea 2"
git push origin develop
```

Luego avisa al profe para que abra/apruebe el Pull Request `develop → main`.

**Convenciones de commit:** prefijo de tipo sin corchetes, descripción en español y en tercera persona impersonal:
`feat:`, `docs:`, `infra:`, `fix:`, `ref:`. Ejemplos: `fix: Se corrige el orden alfabético del reporte`,
`ref: Se extrae la lectura del CSV de la red`.

## 2. Qué NUNCA se sube al repo

El repo central es **público**. No se versiona nada de lo que producen los estudiantes ni las notas del trimestre:

| Nunca al repo | Dónde vive | Cómo está protegido |
|---|---|---|
| **Código de los estudiantes** (clones de los repos de grupo) | `.repos-trimestre-*/` | `.gitignore` |
| **Notas** (`notas.csv`, `notas-sheets.csv`) | `correcciones/resultados/<trimestre>/` | `.gitignore` + patrón `notas*.csv` |
| **Informes con notas** (`informe.md`) | `correcciones/resultados/<trimestre>/` | `.gitignore` + patrón `informe*.md` |
| **Evidencia** (gráficas, fuentes exportadas) | `evidence/`, `sources/` | `.gitignore` |

Todo eso **se regenera** corriendo los comandos de la sección 3: el profe y cualquier preparador nuevo obtienen la misma
data ejecutando, no copiando archivos. Si necesitas pasarle las notas al profe, envía el `notas-sheets.csv` por un
canal privado (o pégalo directo en la planilla), nunca por un commit.

Reglas prácticas:

- Antes de cada commit: `git status` y `git diff --cached --name-only`. Si aparece una ruta con `resultados/`,
  `.repos-trimestre-`, `notas` o `informe`, **no hagas el commit**.
- Si ya subiste algo por error, avisa al profe **antes** de seguir: borrarlo en un commit nuevo no lo saca del
  historial público.
- Qué **sí** está versionado (porque los gates lo necesitan): la lista de entrega
  (`trimestre-actual/lista-entrega.csv`), `alumnos.csv` y `autores.csv` por tarea, y `decisiones-docente.json`. Son
  datos de identificación y decisiones, **no** código ni notas. No agregues ahí nada más sensible.

## 3. Obtener la data del trimestre (en tu máquina)

```powershell
# 1. Trae/actualiza los repos de los equipos (clona si faltan, fetch si ya existen). Sale de trimestre-actual/estado.json
python correcciones/calificador_corte.py --update

# 2. Genera las notas
python correcciones/calificador.py                       # Tarea 1: todos los estudiantes
python correcciones/calificador.py --team G1             # un solo equipo
python correcciones/calificador_corte.py                 # Corte de preguntas 1
```

Los resultados quedan en `correcciones/resultados/<trimestre>/<tarea>/`:
`notas-sheets.csv` (la columna `Nota` se pega tal cual en Google Sheets), `notas.csv` e `informe.md`.

> `calificador.py --update` depende de `tareas/verify_submissions.py`, que hoy tiene el trimestre `2627-1` y un CSV de
> invitaciones fijos en el código. Para refrescar clones en otra máquina usa el paso 1 de arriba.

Tareas futuras: ver [correcciones/tarea-2/README.md](correcciones/tarea-2/README.md) y
[correcciones/tarea-3/README.md](correcciones/tarea-3/README.md) (configuración y directrices ya dejadas; los
correctores están pendientes).

## 4. Convenciones ya probadas (Tarea 1): se siguen, no se reinventan

- **Tarea nueva = carpeta `correcciones/tarea-N/`** con `tarea.json`, `alumnos.csv`, `entregas-tardias.csv` y
  `decisiones-docente.json`. Los gates la descubren **por disco**; no se registra en ningún lado.
- **Entrega tardía individual, −2 puntos** (`late_penalty_points`): se evalúa igual el último commit, y el estudiante
  recibe la **mejor** nota entre la versión al cierre y la tardía menos 2. Un commit tardío nunca perjudica. Cierre en
  `tarea.json` (`cutoff`, con zona `-04:00`). `entregas-tardias.csv` solo para excepciones.
- **Orden alfabético por apellido**, fuente `trimestre-actual/lista-entrega.csv`. Consola, `informe.md`, `notas.csv` y
  `notas-sheets.csv` salen siempre en ese orden, nunca por equipo ni por archivo.
- **Asignación provisional:** un archivo sin nombre en la cabecera se asigna por equipo y sale marcado **provisional**;
  confirmar a mano.
- **Decisiones docentes** (`decisiones-docente.json`): atadas a `team + file + commit` exactos, con `reason`
  obligatorio. Si el estudiante pushea otro commit, caducan y el corrector avisa. Nunca un `if team == ...` en el código.
- **Nota mínima 1**, escala 1–20; la plantilla sin tocar saca la mínima (no "pasa por vacuidad").
- **Tests/gates:** descubren sujetos por disco, fallan si no encuentran ninguno, y se verifican **en rojo** (romper algo a
  propósito y comprobar que el mensaje nombra al culpable) antes de darlos por buenos. Se corren con:

  ```powershell
  python -m pytest repo-template/tests correcciones/tests
  ```

  Esa es la suite que debe quedar en verde antes de pedir el Pull Request.
- **Idioma:** inglés en código (variables, comentarios, claves de JSON, logs); español en `.md`, texto que lee el
  estudiante, commits y ramas.
- **Archivos nuevos que los estudiantes llenan** (como `perceptron_multicapa_N.py`) se agregan a `$PreservedFiles` en
  `scripts/actualizar-repos-trimestre.ps1`, o el siguiente sync les pisa el trabajo.
- **Cambios en `repo-template/`** no llegan a los estudiantes hasta que el profe corre
  `scripts/actualizar-repos-trimestre.ps1` (usa `-DryRun` primero).

## 5. Checklist antes de pedir el Pull Request

- [ ] `git pull origin develop` al día, sin conflictos.
- [ ] `python -m pytest repo-template/tests correcciones/tests` en verde.
- [ ] `git diff main..develop --name-only` no muestra notas, informes, evidencia ni código de estudiantes.
- [ ] Todo gate nuevo lo viste fallar en rojo al menos una vez.
- [ ] Commits con prefijo `feat:`/`docs:`/`infra:`/`fix:`/`ref:` y descripción en español.
