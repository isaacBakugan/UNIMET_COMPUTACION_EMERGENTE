# Forward Propagation paso a paso: vectorizado y muestra por muestra

Guía de resolución de la pregunta **Forward Propagation 1**
([parciales/banco/propias/forward-propagation-1.json](../parciales/banco/propias/forward-propagation-1.json)).
Las dos formas de resolverla dan **el mismo resultado**: `A[2] = [3, 6]`.

## Datos del problema

| Elemento | Valor |
|---|---|
| Arquitectura | 2 entradas → 2 neuronas ocultas (ReLU) → 1 salida (lineal) |
| `W[1]` | `[[1, -1], [2, 1]]` (2×2) |
| `b[1]` | `[[0], [-1]]` (2×1) |
| `W[2]` | `[[2, 1]]` (1×2) |
| `b[2]` | `[[-1]]` (1×1) |
| `X = A[0]` | `[[1, 2], [3, 0]]` (2×2, una muestra por columna) |

Muestras: `x(1) = (1, 3)` y `x(2) = (2, 0)`.

Activaciones: `ReLU(z) = max(0, z)` en la capa oculta, `g(z) = z` (identidad) en la salida.

Fórmulas de cada capa:

```
Z[l] = W[l] · A[l-1] + b[l]
A[l] = g[l](Z[l])
```

## Antes de empezar: chequear las dimensiones

Regla: `(n_l × n_{l-1}) · (n_{l-1} × m) = (n_l × m)`, donde `m` es el número de muestras.

| Paso | Operación | Dimensiones |
|---|---|---|
| `Z[1]` | `W[1] · X` | (2×2)·(2×2) = **2×2** |
| `A[1]` | `ReLU(Z[1])` | **2×2** |
| `Z[2]` | `W[2] · A[1]` | (1×2)·(2×2) = **1×2** |
| `A[2]` | `g(Z[2])` | **1×2** → una salida por muestra |

Si al final `A[2]` no es 1×2, algo se multiplicó mal.

---

## Método 1: vectorizado (todo el batch de una vez)

### Paso 1: `Z[1] = W[1] · X + b[1]`

Primero el producto matricial. Cada elemento es (fila de `W`) · (columna de `X`):

```
W[1] · X = [[1, -1],   ·  [[1, 2],
            [2,  1]]       [3, 0]]

fila 1 · col 1 = 1·1 + (-1)·3 = -2
fila 1 · col 2 = 1·2 + (-1)·0 =  2
fila 2 · col 1 = 2·1 +  1·3   =  5
fila 2 · col 2 = 2·2 +  1·0   =  4

W[1] · X = [[-2, 2],
            [ 5, 4]]
```

Ahora se suma `b[1]` **a cada columna** (broadcasting): el `0` va a toda la fila 1 y el `-1` a toda la fila 2.

```
Z[1] = [[-2 + 0,  2 + 0],     = [[-2, 2],
        [ 5 - 1,  4 - 1]]        [ 4, 3]]
```

### Paso 2: `A[1] = ReLU(Z[1])`

`max(0, z)` elemento por elemento: los negativos pasan a 0.

```
A[1] = [[max(0,-2), max(0,2)],     = [[0, 2],
        [max(0, 4), max(0,3)]]        [4, 3]]
```

### Paso 3: `Z[2] = W[2] · A[1] + b[2]`

```
W[2] · A[1] = [[2, 1]] · [[0, 2],
                          [4, 3]]

col 1: 2·0 + 1·4 = 4
col 2: 2·2 + 1·3 = 7

W[2] · A[1] = [[4, 7]]
```

Se suma `b[2] = -1` a cada columna:

```
Z[2] = [[4 - 1, 7 - 1]] = [[3, 6]]
```

### Paso 4: `A[2] = g(Z[2])`

La salida es lineal, así que no cambia nada:

```
A[2] = [[3, 6]]
```

**Respuesta: `A[2] = [3, 6]`**

---

## Método 2: muestra por muestra (el que hicimos en clase)

Es exactamente la misma cuenta, pero con **un vector columna por vez**. Cada columna de `X` es una muestra, y cada columna de `A[2]` es su salida. Aquí `Z` y `A` son vectores, no matrices.

### Muestra 1: `x(1) = (1, 3)`

**Capa oculta**

```
z[1] = W[1] · x(1) + b[1]
     = [[1, -1],  · [1]  + [ 0]
        [2,  1]]    [3]    [-1]

     = [1·1 + (-1)·3]  + [ 0]  = [-2]  + [ 0]  = [-2]
       [2·1 +   1·3 ]    [-1]    [ 5]    [-1]    [ 4]

a[1] = ReLU(z[1]) = [0, 4]
```

**Capa de salida**

```
z[2] = W[2] · a[1] + b[2]
     = [2, 1] · [0, 4] + (-1)
     = 2·0 + 1·4 - 1
     = 3

a[2] = 3
```

### Muestra 2: `x(2) = (2, 0)`

**Capa oculta**

```
z[1] = W[1] · x(2) + b[1]
     = [1·2 + (-1)·0]  + [ 0]  = [2]  + [ 0]  = [2]
       [2·2 +   1·0 ]    [-1]    [4]    [-1]    [3]

a[1] = ReLU(z[1]) = [2, 3]
```

**Capa de salida**

```
z[2] = W[2] · a[1] + b[2]
     = 2·2 + 1·3 - 1
     = 6

a[2] = 6
```

### Juntar las salidas

Cada salida va a su columna, en el mismo orden de las muestras:

```
A[2] = [a[2] de x(1), a[2] de x(2)] = [3, 6]
```

**Respuesta: `A[2] = [3, 6]`**

---

## Cómo se relacionan los dos métodos

Los números intermedios son los mismos; solo cambia cómo se agrupan:

| Intermedio | Muestra 1 (col 1) | Muestra 2 (col 2) | Matriz vectorizada |
|---|---|---|---|
| `Z[1]` | `[-2, 4]` | `[2, 3]` | `[[-2, 2], [4, 3]]` |
| `A[1]` | `[0, 4]` | `[2, 3]` | `[[0, 2], [4, 3]]` |
| `Z[2]` | `3` | `6` | `[[3, 6]]` |
| `A[2]` | `3` | `6` | `[[3, 6]]` |

La idea de la versión vectorizada: **la columna `j` de la matriz resultado es exactamente lo que daría procesar la muestra `j` sola**. Apilar las muestras en columnas permite que un solo producto `W · A` haga el trabajo de `m` productos `W · x`. Es lo que hace NumPy en el corrector, y por eso escala a miles de muestras sin un `for`.

Para el examen: si la cuenta es corta (2 muestras), muestra por muestra es más difícil de equivocar; con más muestras, vectorizado.

---

## De dónde salen los distractores (errores típicos)

Sirven para verificar el resultado: si tu número coincide con uno de estos, te saltaste un paso.

| Respuesta | Error cometido | Qué cambia |
|---|---|---|
| `[-1, 6]` | **Olvidar ReLU** | `A[1]` queda `[[-2, 2],[4, 3]]` y `W[2]·A[1]` col 1 = `2·(-2) + 4 - 1 = -1` |
| `[5, 8]` | **Olvidar `b[1]`** (o todos los bias) | `Z[1] = [[-2, 2],[5, 4]]` → `A[1] = [[0, 2],[5, 4]]` → `5, 8` (con `b[2]` ya restado) |
| `[4, 7]` | **Olvidar `b[2]`** | `W[2]·A[1] = [[4, 7]]` sin restar el `-1` |
| **`[3, 6]`** | Ninguno | Correcta |

## Checklist de errores comunes

1. **Orden de la multiplicación:** es `W · A`, no `A · W`. Con las dimensiones de arriba, el otro orden ni siquiera es multiplicable.
2. **Filas de `W` = neuronas:** la fila `i` de `W[l]` son los pesos de la neurona `i`. Se multiplica fila × columna.
3. **El bias se suma por neurona (fila), a todas las muestras (columnas).** No se suma un bias distinto por muestra.
4. **ReLU va entre capas, antes de usar `A[1]`.** `Z[1]` nunca entra a la segunda capa directamente.
5. **Capa de salida lineal:** no se aplica ReLU al final. Si salieran negativos, se quedan negativos.
6. **No mezclar columnas:** al apilar, la muestra 1 es la columna 1. Si tu `A[2]` sale con el orden cambiado, transpusiste algo.
