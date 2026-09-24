# Repositorio Central de Evaluación Emergente

**Fuente de verdad única** para la evaluación y corrección automática de actividades estudiantiles. Persiste entre trimestres, escalable a N grupos.

## Arquitectura

```
┌─────────────────────────────────────────────────────┐
│  Repo Central (este)                                │
│  - Formatos de pregunta                             │
│  - Esquemas de evaluación                           │
│  - Guías por tarea / trimestre                      │
│  - Scripts de corrección                            │
│  - GitHub Actions: corrección paralela + reportes   │
│  - Guards: detección de copias entre equipos        │
└─────────────────────────────────────────────────────┘
                          │
                  [Trimestre T]
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
    Repo Grupo 1      Repo Grupo 2     ... Repo Grupo N
   (estudiantes)     (estudiantes)    (estudiantes)
   - Preguntas       - Preguntas      - Preguntas
   - Tests locales   - Tests locales  - Tests locales
   - Commits         - Commits        - Commits
```

## Componentes principales

### 1. **Repo Central** (`este`)
Fuente de verdad que persiste. Contiene:

- **`/formatos`**: esquemas de pregunta (V/F, selección múltiple, respuesta corta), validadores JSON (Python)
- **`/correcciones`**: lógica de evaluación, rúbricas, scripts que califican (Python)
- **`/guias`**: instrucciones por tarea, rubrica de evaluacion, criterios de validación
- **`/.github/workflows`**: 
  - `correcciones-paralelas.yml`: trigueá manualmente o en schedule, corre tests en todos los repos de grupos, genera informe
  - `guards-copias.yml`: detecta similitud anómala entre respuestas, reporta sospechas
- **`/repo-template`**: estructura inicial que se clona/sincroniza a cada repo de grupo

### 2. **Repos de Grupo** (1 por grupo, públicos)
Clonados desde este repo al inicio del trimestre. Contienen:

- Copia del `/repo-template` y esquemas de validación
- `preguntas.json` o similar: respuestas del grupo (generadas por ellos)
- `tests/` locales: validadores que pueden correr con `pytest`
- Historial de commits: quién escribió qué, cuándo

## Flujo de trabajo por trimestre

### Fase 1: Setup inicial

No se conocen de antemano los usernames de GitHub de todo el curso, así que el modelo es
**un delegado por equipo**: se invita solo al delegado con permiso `push`, y es él quien
agrega al resto de su equipo como colaborador directamente desde GitHub (los conoce, tú no).

```json
// trimestre-actual/equipos.json
[
  { "equipo": "grupo-lecturas-1", "delegados": ["username-delegado-1"] },
  { "equipo": "grupo-lecturas-2", "delegados": ["username-delegado-2"] }
]
```

```powershell
& ./scripts/crear-repos-trimestre.ps1 -Trimestre "2026-2"
```

El script:
- Lee todos los equipos de `trimestre-actual/equipos.json` (un solo archivo, contrato en
  `trimestre-actual/README.md`)
- Crea el repo público (bajo tu cuenta, nunca en organización) y le empuja `/repo-template` —
  **solo si el repo no existe ya** (idempotente, no pisa trabajo de estudiantes)
- Invita a los `delegados` de cada equipo como colaboradores con permiso `push` ("editor")
- Genera `invitaciones-<trimestre>.csv` con el link de invitación por equipo, para
  compartirlo con el delegado (lo abre logueado con su cuenta y acepta)
- Deja `trimestre-actual/estado.json` con los repos activos (equipo, repo, owner, url,
  delegados, fecha de creación)

### Actualizar el template en repos ya creados

Cuando cambias algo en `/repo-template` (un test nuevo, una guía) a mitad de trimestre:

```powershell
& ./scripts/actualizar-repos-trimestre.ps1
```

Lee `trimestre-actual/estado.json`, clona/actualiza cada repo activo, sincroniza el
template **preservando `preguntas.json`** (nunca pisa las respuestas ya subidas) y solo
commitea/pushea si hay diferencias reales (idempotente). Corre local con `gh`/`git`, no
como GitHub Action, para no tener que guardar un token de escritura amplio como secret en
el repo central.

### Fase 2: Trabajo de estudiantes (4-6 semanas)
- Clonan su repo de grupo
- Agregan preguntas en el formato requerido
- Corren `pytest` localmente para validar
- Hacen commits y push
- GitHub guarda todo: timestamps, autores, contenido

### Fase 3: Corrección automática (manual trigger desde central)
```bash
# Desde el central, trigueás el action
gh workflow run correcciones-paralelas.yml

# El action:
# 1. Itera los 7 repos en paralelo
# 2. Clona cada uno
# 3. Corre los tests (validación de formato)
# 4. Ejecuta la lógica de corrección (rúbrica, puntuación)
# 5. Genera un informe JSON/CSV por grupo
# 6. Detecta copias anómalas (similaridad de respuestas)
# 7. Reporta todo en un artefacto descargable
```

### Fase 4: Reporte a Moodle
- Descargas el informe del action
- Opcionalmente: script que parsea el JSON e inserta calificaciones directamente en Moodle vía API

## Guards de detección de copias

Dos mecanismos:

### 1. **Guards estáticos** (en cada repo)
Los tests validan:
- Formato correcto de preguntas (estructura JSON)
- Que no haya preguntas vacías o duplicadas dentro del mismo grupo
- Que cada pregunta tenga la metadata requerida

Fallan en rojo si hay violación.

### 2. **Guards dinámicos** (en el central, durante corrección)
El action `guards-copias.yml`:
- Clona los 7 repos
- Extrae todas las preguntas de todos los grupos
- Computa similitud entre respuestas (cosine similarity, token overlap, etc.)
- Si detecta 80%+ de similitud entre dos grupos → **reporta con contexto** (qué preguntas, qué porcentaje)
- **No falla el build**, pero marca en el informe como "⚠️ Similitud anómala"

Así vos ves:
- Quién copió de quién (por timestamps de commit)
- Qué partes son idénticas
- Puedes decidir si es accidental o no

## Composición de un trimestre

Cada trimestre reutiliza este repo, agrega:
- Nueva rama o carpeta `/trimestre-2026-2` con guías y lecturas específicas
- N nuevos repos de grupo (mismo patrón)
- Histórico de correcciones anterior sirve como referencia

**El repo central crece**, pero la estructura es inmutable.

## Estructura de directorios

```
.
├── README.md (este)
├── .gitignore
├── formatos/
│   ├── pregunta-vf.schema.json
│   ├── pregunta-multiple.schema.json
│   └── validador.py
├── correcciones/
│   ├── rubrica.py
│   ├── calificador.py
│   └── exportar_moodle.py
├── guias/
│   ├── trimestre-2026-2/
│   │   ├── tarea-1-lecturas.md
│   │   ├── tarea-2-preguntas.md
│   │   └── criterios.md
│   └── trimestre-2026-3/
│       └── ...
├── repo-template/
│   ├── preguntas.json (structure)
│   ├── requirements.txt (deps para correr tests, pytest)
│   └── tests/
│       ├── test_validar_formato.py
│       └── test_validar_duplicados.py
├── trimestre-actual/
│   ├── README.md (contrato de equipos.json)
│   ├── equipos.json (insumo: equipos + delegados del trimestre)
│   └── estado.json (repos activos, lo mantiene crear-repos-trimestre.ps1)
├── .github/workflows/
│   ├── correcciones-paralelas.yml
│   ├── guards-copias.yml
│   └── exportar-moodle.yml (opcional)
└── scripts/
    ├── crear-repos-trimestre.ps1
    ├── actualizar-repos-trimestre.ps1
    ├── clonar-todos.sh
    └── reportar_infracciones.py
```

## Comandos comunes

### Crear repos para un nuevo trimestre
```powershell
& ./scripts/crear-repos-trimestre.ps1 -Trimestre "2026-2"
# equipos leídos de trimestre-actual/equipos.json
```

### Pushear cambios de template a los repos activos
```powershell
& ./scripts/actualizar-repos-trimestre.ps1
# lee trimestre-actual/estado.json, preserva preguntas.json de cada equipo
```

### Corregir todos los grupos
```bash
gh workflow run correcciones-paralelas.yml
```

### Descargar informe
```bash
gh run download <run-id> --name results-all
```

## Ventajas de esta arquitectura

1. **Escalable**: agregar un grupo es una línea en el script
2. **Auditable**: cada commit en cada repo tiene autor, timestamp, diff
3. **Segura contra copias**: los guards detectan similitud automáticamente
4. **Reutilizable**: cada trimestre reutiliza la misma infra, solo agrega guías nuevas
5. **Local-first**: estudiantes validan localmente antes de pushear
6. **Transparente**: todos los repos públicos, no hay "caja negra" de corrección

## Próximos pasos

- [ ] Definir formato exacto de `preguntas.json` (V/F vs múltiple)
- [ ] Escribir validadores en `/formatos`
- [ ] Definir rúbrica de evaluación en `/correcciones`
- [ ] Armar el script `crear-repos-trimestre.ps1`
- [ ] Implementar `correcciones-paralelas.yml`
- [ ] Implementar `guards-copias.yml`
- [ ] Test con un grupo piloto
