# Tarea 2 — Perceptrón multicapa

## Enunciado

El propósito de esta tarea es tener la experiencia de desarrollar una red neuronal desde
cero y observar las diferencias entre fijar los pesos manualmente (como se hizo en la
Tarea 1) y el aprendizaje de máquina.

Escriba un programa que permita **entrenar, guardar, cargar y correr** un perceptrón
multicapa.

### Requerimientos funcionales

El programa debe iniciar dando dos opciones: **crear un nuevo perceptrón multicapa** o
**cargarlo de un archivo**. Al crearlo, se le debe pedir al usuario:

- Número de neuronas de entrada
- Número de neuronas de salida
- Número de capas ocultas
- Número de neuronas por capa

El programa debe entonces darle al usuario la opción de:

1. **Entrenar** la red con **retropropagación** con un conjunto de datos de entrenamiento;
   en cuyo caso se pedirá:
   - El archivo de datos de entrenamiento
   - El número de épocas
2. **Probarla** con **alimentación hacia delante** con un conjunto de datos de prueba;
   en cuyo caso se pedirá:
   - El archivo de datos de prueba
3. **Guardar** la red
4. **Salir**

Luego de cualquiera de las dos primeras opciones (entrenar o probar), deben mostrarse
**tres gráficos** con:

- Los datos del archivo graficados con `matplotlib.pyplot.scatter`. Si hay tres o más
  valores de entrada, deberán graficarse los **primeros tres** usando una
  [proyección 3D](https://matplotlib.org/stable/gallery/mplot3d/scatter3d.html).
- Si la salida predicha por la red neuronal para cada vector es **correcta o incorrecta**.
- El **error de la red**:
  - Si se estaba **entrenando**, debe mostrarse el error de cada época en un
    [gráfico de línea](https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.plot.html).
  - Si se estaba **probando**, debe mostrarse la **matriz de confusión** con
    [`matplotlib.pyplot.matshow`](https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.matshow.html).

Adicionalmente, deben **imprimirse los hiperparámetros**. El número de épocas debe estar
actualizado con respecto al entrenamiento inicial si la red recibió entrenamiento
posterior.

Una vez que se ha concluido el entrenamiento, la prueba o el guardado, debe volvérsele a
presentar al usuario este menú para permitirle seguir entrenando.

### Formatos de archivo

#### Archivos de datos

El archivo de datos de entrenamiento y el de prueba tienen el **mismo formato**: archivos
CSV con una línea por vector, donde las primeras `n-1` columnas son los valores de entrada
y la `n`-ésima es la clase de salida. Es el mismo formato que los archivos de la Tarea 1.

Si el número de neuronas de entrada y salida de la red no se corresponde con el archivo,
el programa debe dar un **mensaje de error indicando cómo debe configurarse la red**.

#### Archivos de perceptrón multicapa

El archivo del perceptrón multicapa también es un archivo CSV, con **una línea por
neurona**:

| Columna | Contenido |
|---|---|
| 1ª | Tipo de neurona: `h` (*hidden*) u `o` (*output*) |
| 2ª | Capa de la neurona. La primera capa *hidden* es la número **1**; no es necesario almacenar la capa 0 (*input*) |
| 3ª | Posición de la neurona dentro de la capa. El índice **comienza en 0** |
| 4ª en adelante | Los `c` pesos de esa neurona: la 4ª columna es el peso de la entrada 0, la 5ª el de la entrada 1, y así sucesivamente |

Lo anterior aplica **de la sexta fila en adelante**. Las **primeras 5 filas** contienen los
hiperparámetros, identificados con las letras:

| Letra | Hiperparámetro |
|---|---|
| `u` | Tamaño del vector de entrada |
| `v` | Tamaño del vector de salida |
| `L` | Número de *layers* |
| `b` | Número de neuronas |
| `e` | Número de épocas |

Las columnas de la 3 a la `c+3` deben estar **vacías** para estas filas. Nótese que el
formato CSV aún requiere una **fila de encabezado** para la tabla, y que `c = max(u, b)`.

### Requerimientos técnicos

- Debe **partir del código de la Tarea 1** y adaptarlo a estos requerimientos.
- Puede usar librerías para la operación de datos en vectores o matrices como **NumPy** o
  **Pandas**.
- **No** puede usar librerías especializadas para redes neuronales como **PyTorch**,
  **TensorFlow** o similares.
- Debe entregar los **archivos correspondientes a las redes resultantes** a los ejemplos
  entregados (ver `assets/`). Su programa debe ser capaz de cargar sus propios archivos.

### Rúbrica

| Criterio | Correctamente | Incorrectamente | No hace nada |
|---|---|---|---|
| La primera red entregada clasifica el ejemplo de 2 dimensiones y 2 clases | 25% | 15% | 0% |
| La segunda red entregada clasifica el ejemplo de 3 dimensiones y 4 clases | 25% | 15% | 0% |
| Los hiperparámetros de la primera red entrenan una red capaz de clasificar un ejemplo no visto de 2 dimensiones y 2 clases | 25% | 15% | 0% |
| Los hiperparámetros de la segunda red entrenan una red capaz de clasificar un ejemplo no visto de 3 dimensiones y 4 clases | 25% | 15% | 0% |

Los ejemplos "no vistos" no están en este repo — los aplica la corrección del repo
central.

## Cómo se entrega

- El programa va en **`perceptron_multicapa_1.py`, `perceptron_multicapa_2.py`, o
  `perceptron_multicapa_3.py`**, dependiendo de tu elección, en esta misma carpeta
  (`tarea-2-codigo/`) — uno por integrante. Recuerda colocar tu nombre y cédula en la parte
  superior del archivo.
- Junto al programa, los **archivos de perceptrón multicapa** (formato descrito arriba)
  de las dos redes entrenadas: una para cada dataset de `assets/`.
- `assets/` trae los datasets con los que deben entrenar y probar sus redes (columnas
  `x1,x2,...,y`, con encabezado):

  | Archivo | Entradas | Clases |
  |---|---|---|
  | `2-d_2-class_train.csv` / `2-d_2-class_test.csv` | 2 | 2 (`-1`, `1`) |
  | `3-d_4-class_train.csv` / `3-d_4-class_test.csv` | 3 | 4 (`1`, `2`, `3`, `4`) |

- Necesitan `numpy` y `matplotlib` instalados para correr su programa:
  `pip install numpy matplotlib`.
