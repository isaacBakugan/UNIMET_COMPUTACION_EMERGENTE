# Entregable 2 — Corte de preguntas 2

## Qué hay que hacer

1. Lean las lecturas de **martes y jueves** de la **semana 3** y la **semana 4**, más la del
   **martes de la semana 5** (guía de lecturas en el repo central: `guias/<trimestre-actual>/`).
   Son **5 lecturas** en total.
2. Como equipo, generen **10 preguntas por cada lectura**:
   - **5 preguntas de Verdadero/Falso**
   - **5 preguntas de selección simple** (una sola opción correcta)

   Eso da **10 preguntas × 5 lecturas = 50 preguntas en total** para este corte
   (25 de Verdadero/Falso y 25 de selección simple).

   Entre las 50, deben repartir la dificultad: **al menos 10 preguntas fáciles** (`difficulty_level`
   1 a 3), **al menos 10 intermedias** (4 a 6) y **al menos 10 difíciles** (7 a 10).
   Las 20 restantes pueden ir en la banda que quieran.
3. Completen `preguntas.json` con sus 50 preguntas — **ese es el archivo que se corrige**.
   `ejemplo-preguntas.json` es solo referencia de formato (no trae las 50, solo un ejemplo
   por lectura), no se evalúa.
4. Corran los tests localmente antes de subir: `pytest corte-preguntas-2/tests/`
5. Si los tests pasan, hagan commit y push.

> Este corte tiene **5 lecturas y 50 preguntas** (a diferencia del corte 1, que tuvo 4 y 40), y es **independiente** del corte 1: su archivo es `corte-preguntas-2/preguntas.json`
> y no se mezcla con `corte-preguntas-1/preguntas.json`. No reutilicen preguntas del corte anterior.

## Formato de cada pregunta

| Campo               | Tipo                                    | Descripción                                                            |
|----------------------|------------------------------------------|-------------------------------------------------------------------------|
| `id`                 | string                                    | Identificador corto y único (`tue3-tf-1`, `thu3-mc-3`, ...)             |
| `reading`            | string                                    | A qué lectura pertenece: `tuesday-week-3`, `thursday-week-3`, `tuesday-week-4`, `thursday-week-4` o `tuesday-week-5` |
| `type`               | `"true_false"` \| `"multiple_choice"`     | Tipo de pregunta                                                       |
| `statement`          | string                                    | El texto de la pregunta, no puede estar vacío                          |
| `options`            | array de strings                         | 2 opciones si es V/F (`Verdadero`/`Falso`), **exactamente 4** si es selección simple |
| `correct_option`     | string                                    | Debe ser **exactamente igual** a una de las `options`                  |
| `difficulty_level`   | entero, 1 a 10                           | Qué tan difícil creen que es la pregunta (1 = muy fácil, 10 = muy difícil) |
| `source_quote`       | string, mínimo 20 caracteres             | Fragmento **copiado literalmente** de la lectura que justifica la respuesta correcta |

Vean `ejemplo-preguntas.json` para un ejemplo completo por cada lectura.

## Cómo se valida

`tests/test_validar_entregable_2.py` revisa, sobre `preguntas.json`. Es **el mismo archivo** con el que
se califica: si pasa en su máquina, pasa en la corrección.

**Cantidad**
- Exactamente **50 preguntas en total**
- Exactamente **5 de cada tipo (V/F y selección simple) por cada una de las 5 lecturas**

**Formato**
- Que exista y sea JSON válido; todos los campos requeridos presentes, incluido `source_quote`
- Que no quede **ninguna pregunta con el texto de la plantilla** (`PONGAN AQUÍ ...`, `(edítenla)`): una
  pregunta sin editar cuenta como una pregunta que falta, y un `preguntas.json` vacío o sin editar no
  pasa ninguna prueba
- `reading` y `type` con valores válidos
- Enunciados de **al menos 5 palabras**, sin duplicados ni casi-duplicados (similitud ≥ 85 %): la misma
  pregunta reescrita con otras palabras cuenta como duplicada
- `correct_option` está entre las `options`
- V/F tiene exactamente las opciones `Verdadero`/`Falso`
- Selección simple tiene **exactamente 4 opciones**, sin opciones repetidas ni una opción idéntica al enunciado
- **Sin "todas las anteriores" ni "ninguna de las anteriores"** (ni variantes como "todas las opciones")
- `difficulty_level` es un entero entre 1 y 10
- `source_quote` de al menos 20 caracteres

**Dificultad**
- Al menos **10 preguntas en cada banda**: fáciles (1 a 3), intermedias (4 a 6) y difíciles (7 a 10)

**Balance** (que la respuesta correcta no se pueda adivinar sin leer)
- En V/F, entre el **40 % y el 60 %** de las respuestas correctas son `Verdadero` (con 25 V/F: entre 10 y 15)
- En selección simple, **ninguna posición (A, B, C o D) concentra más del 50 %** de las respuestas
  correctas (con 25: como máximo 12 en la misma posición)

Que los tests pasen en verde **no significa que las preguntas estén bien hechas** — solo que el formato
y la distribución son correctos. La calidad del contenido se evalúa en una fase posterior.

## Cómo se califica

La nota (1 a 20) sale de ejecutar **estas mismas pruebas** sobre el `preguntas.json` del último commit
anterior al cierre. Cada criterio suma puntos proporcionales a las pruebas que pasan:

| Criterio     | Puntos | Qué se mide |
|--------------|-------:|-------------|
| Cantidad     |   11   | Las 50 preguntas: 5 V/F y 5 selección simple por cada lectura |
| Formato      |    3   | Estructura de cada pregunta, sin placeholders, sin duplicados, 4 opciones, `source_quote` |
| Dificultad   |    3   | Al menos 10 preguntas en cada banda (1–3, 4–6 y 7–10) |
| Balance      |    3   | Respuestas V/F y posiciones de selección simple sin patrón predecible |

Los commits posteriores al cierre no se evalúan salvo por la regla de entrega tardía del curso.
