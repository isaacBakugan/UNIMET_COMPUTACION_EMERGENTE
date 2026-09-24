# Entregable 1 — Corte de preguntas 1

## Qué hay que hacer

1. Lean las lecturas de **martes y jueves** de la **semana 1** y la **semana 2** (guía de
   lecturas en el repo central: `guias/<trimestre-actual>/tarea-1-lecturas.md`). Son
   **4 lecturas** en total.
2. Como equipo, generen **10 preguntas por cada lectura**:
   - **5 preguntas de Verdadero/Falso**
   - **5 preguntas de selección simple** (una sola opción correcta)

   Eso da **10 preguntas × 4 lecturas = 40 preguntas en total** para este corte
   (20 de Verdadero/Falso y 20 de selección simple).
3. Completen `preguntas.json` con sus 40 preguntas — **ese es el archivo que se corrige**.
   `ejemplo-preguntas.json` es solo referencia de formato (no trae las 40, solo un ejemplo
   por lectura), no se evalúa.
4. Corran los tests localmente antes de subir: `pytest corte-preguntas-1/tests/`
5. Si los tests pasan, hagan commit y push.

## Formato de cada pregunta

| Campo              | Tipo                              | Descripción                                                            |
|---------------------|-----------------------------------|-------------------------------------------------------------------------|
| `id`                | string                             | Identificador corto y único (`m1-vf-1`, `j1-ss-3`, ...)                 |
| `lectura`           | string                             | A qué lectura pertenece: `martes-semana-1`, `jueves-semana-1`, `martes-semana-2` o `jueves-semana-2` |
| `tipo`              | `"verdadero_falso"` \| `"seleccion_simple"` | Tipo de pregunta                                              |
| `enunciado`         | string                             | El texto de la pregunta, no puede estar vacío                          |
| `opciones`          | array de strings                  | 2 opciones si es V/F (`Verdadero`/`Falso`), 3 o más si es selección simple |
| `opcion_correcta`   | string                             | Debe ser **exactamente igual** a una de las `opciones`                 |
| `nivel_dificultad`  | entero, 1 a 10                    | Qué tan difícil creen que es la pregunta (1 = muy fácil, 10 = muy difícil) |

Vean `ejemplo-preguntas.json` para un ejemplo completo por cada lectura.

## Cómo se valida

`tests/test_validar_entregable_1.py` revisa, sobre `preguntas.json`:

- Que exista y sea JSON válido
- Exactamente **40 preguntas en total**
- Exactamente **10 preguntas por cada una de las 4 lecturas** (5 V/F + 5 selección simple)
- Todos los campos requeridos presentes, incluyendo `lectura` con un valor válido
- Enunciados no vacíos y no duplicados dentro del equipo
- `opcion_correcta` está entre las `opciones`
- V/F tiene exactamente las opciones `Verdadero`/`Falso`
- Selección simple tiene 3 o más opciones
- `nivel_dificultad` es un entero entre 1 y 10

Que los tests pasen en verde **no significa que las preguntas estén bien hechas** — solo
que el formato es correcto. El contenido lo evalúa la rúbrica del repo central.
