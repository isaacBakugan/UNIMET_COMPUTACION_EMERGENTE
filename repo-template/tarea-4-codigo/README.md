# Tarea 4 — Algoritmo genético

## Enunciado

El propósito de esta tarea es practicar **adaptar a un algoritmo genético dos
representaciones diferentes de la población**.

Escriba un programa de Python que permita encontrar el **valor óptimo de una función**
usando un **algoritmo genético**. Luego, úselo para encontrar:

**a.** El valor de `x` entre **-10 y 10** que produce el valor **más alto** de `y` para la
función:

```
y = sin²(x) / x
```

**b.** Los valores de `x` e `y` entre **-10 y 10** que producen el valor **más alto** de `z`
para:

```
z = 20 + x − 10·cos(2π·x) + y − 10·cos(2π·y)
```

> En la función **a**, `x = 0` no está definida (0/0); su límite es 0. Tu código no debe
> fallar si un miembro de la población cae exactamente en 0.

### Requerimientos funcionales

Al igual que las tareas 2 y 3, el programa debe permitir **guardar una población o cargarla
de un archivo**. Al **crearla**, el usuario tendrá la opción de especificar:

| Parámetro | Por defecto |
|---|---|
| Tamaño de la población | **10** |
| Umbral de diferencia | **0.05** |
| Número máximo de generaciones | **500** |
| Variabilidad de la mutación | **1** |

- **La función se especifica en un archivo de Python separado**, el cual **debe poderse
  cambiar** (el programa debe poder correr con la función `a`, con la `b` o con cualquier
  otra sin tocar el código del algoritmo).
- El programa debe ir **mostrando en pantalla** los valores encontrados (**máximo, mediana y
  mínimo**) **al final de cada iteración**, junto con el **número de la generación**.
- Al **terminar el número de generaciones** — o **al cargar de un archivo** — se deben
  mostrar **todos los parámetros** (población, umbral, generaciones transcurridas y mutación)
  y **todos los miembros de la población, ordenados de mejor a peor, junto con su función**
  (el valor de la función para cada uno).

> El enunciado no define con precisión qué hace el **umbral de diferencia**. Documenta en un
> comentario al inicio de tu `.py` cómo lo interpretas y úsalo de forma coherente (por
> ejemplo, como criterio de parada o de convergencia).

### Requerimientos técnicos

- Debe entregar su código de Python, el cual debe poder **ejecutarse en cualquier
  computadora**: nada de rutas absolutas (`C:\Users\...`), dependencias del sistema ni
  archivos que no estén en el repo. Solo la librería estándar de Python (y, si quieres,
  `numpy`).
- Debe entregar **dos poblaciones entrenadas sobre cada función**: una con **baja
  variabilidad de mutación (menor que 1)** y otra con **alta variabilidad de mutación (mayor
  que 1)**. Son **cuatro poblaciones** en total.

### Rúbrica

| Criterio | Peso | Adecuada para sus parámetros y el problema | Inadecuada para sus parámetros, pero obedece al problema | Inadecuada para el problema | No carga |
|---|---|---|---|---|---|
| Población con **baja** variabilidad, función **a** | 20% | 20 | 14 | 7 | 0 |
| Población con **alta** variabilidad, función **a** | 20% | 20 | 14 | 7 | 0 |
| Población con **baja** variabilidad, función **b** | 30% | 30 | 20 | 10 | 0 |
| Población con **alta** variabilidad, función **b** | 30% | 30 | 20 | 10 | 0 |

## Cómo se entrega

Cada integrante entrega **sus** archivos, identificados con su número `N` (`1`, `2` o `3`),
en esta misma carpeta (`tarea-4-codigo/`):

| Archivo | Contenido |
|---|---|
| `algoritmo_genetico_N.py` | **El programa** (un solo `.py`). Recuerda colocar tu **nombre y cédula** en las dos primeras líneas |
| `funcion_a_N.py` | La función **a** (archivo separado, ver contrato) |
| `funcion_b_N.py` | La función **b** (archivo separado, ver contrato) |
| `population_N_a_low.json` | Población entrenada sobre la función **a**, variabilidad **< 1** |
| `population_N_a_high.json` | Población entrenada sobre la función **a**, variabilidad **> 1** |
| `population_N_b_low.json` | Población entrenada sobre la función **b**, variabilidad **< 1** |
| `population_N_b_high.json` | Población entrenada sobre la función **b**, variabilidad **> 1** |

Tu programa debe poder **cargar tus propios archivos de población**.

### Contrato del archivo de función

La corrección no ejecuta tu programa: evalúa tus poblaciones directamente. Para que tu
programa y la corrección hablen de lo mismo, cada archivo de función define:

```python
BOUNDS = (-10, 10)        # limits of every variable
VARIABLE_COUNT = 1        # 1 for function a, 2 for function b

def fitness(*variables):  # higher is better
    ...
```

### Contrato del archivo de población

JSON con claves en inglés. La **representación interna** de cada miembro es **libre** (binaria,
real, lo que elijas), pero el archivo **siempre** trae los valores ya decodificados:

```json
{
  "function": "funcion_a_1.py",
  "parameters": {
    "population_size": 10,
    "difference_threshold": 0.05,
    "max_generations": 500,
    "mutation_variability": 0.5,
    "generations_elapsed": 500
  },
  "members": [
    {"variables": [1.1656], "fitness": 0.7246, "genes": "free-form"},
    {"variables": [1.1702], "fitness": 0.7245, "genes": "free-form"}
  ]
}
```

- `members` va **ordenado de mejor a peor** y su largo es igual a `population_size`.
- `variables` son los valores **ya decodificados** (1 número para la función a, 2 para la b)
  y `fitness` es el valor de la función en ese punto.
- `genes` es opcional y de formato libre (lo usa tu programa para continuar el entrenamiento).
- `mutation_variability` debe ser **< 1** en los archivos `low` y **> 1** en los `high`.
- `generations_elapsed` se **actualiza** si sigues entrenando una población cargada.

## Reglas

- La tarea es **individual**: cada quien trabaja en sus propios archivos, aunque compartan repo.
- Código en **inglés** (nombres, comentarios, claves de JSON, mensajes de log); el texto que lee
  el usuario en el menú y los `.md`, en **español**.
