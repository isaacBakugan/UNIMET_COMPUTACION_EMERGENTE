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
- **`preguntas.json` nunca se sobreescribe** una vez que el equipo lo llenó — es la
  respuesta real, no el placeholder del template. Ver `PreservedFiles` en
  `actualizar-repos-trimestre.ps1`.
- **Repos siempre públicos, nunca en organización** (`gh repo create ... --public`, sin
  `--org`).
- Un test/gate nuevo que valide formato de un entregable debe fallar en rojo cuando no hay
  solución todavía (no asumir contenido que no existe) — así se comprobó con cada test de
  este repo antes de darlo por bueno.
