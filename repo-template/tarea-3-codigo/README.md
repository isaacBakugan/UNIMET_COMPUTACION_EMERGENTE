# Tarea 3 — PyTorch

## Enunciado

El propósito de esta tarea es aprender a utilizar una **librería especializada para redes
neuronales** para generalizar y escalar lo realizado en la Tarea 2.

Desarrolle un programa con **PyTorch** que permita crear redes neuronales para clasificar el
conjunto de imágenes **Fashion MNIST** y cree con él **cuatro redes neuronales**.

### Requerimientos funcionales

Las redes neuronales deben tener **784 neuronas de entrada**, cada una correspondiendo a un
píxel de una imagen de 28×28, y **10 neuronas de salida**, cada una correspondiendo a una de
las clases de Fashion MNIST:

| # | Clase | # | Clase |
|---|---|---|---|
| 1 | T-shirt/top (franela) | 6 | Sandal (sandalia) |
| 2 | Trouser (pantalón) | 7 | Shirt (camisa) |
| 3 | Pullover (sweater) | 8 | Sneaker (zapato deportivo) |
| 4 | Dress (vestido) | 9 | Bag (mochila) |
| 5 | Coat (chaqueta) | 10 | Ankle boot (bota hasta los tobillos) |

> En la clasificación simplificada (ver "Requerimientos técnicos") la capa de salida tiene
> **4 neuronas**, no 10.

Al igual que la Tarea 2, el programa debe permitir **crear una nueva red** o **cargarla de un
archivo**. Al crearla, el usuario tendrá la opción de especificar:

- El **número de capas ocultas** (por defecto: **2**)
- Si es **convolucional** o **rectangular** (por defecto: **rectangular**)
  - En caso de ser **rectangular**, el **número de neuronas por capa** (por defecto: **512**)
  - En caso de ser **convolucional**, el programa deberá **calcular el número de neuronas por
    capa usando interpolación lineal** entre la capa de entrada (784) y la de salida (10), de
    modo que cada capa sucesiva disminuya en la misma cantidad de neuronas.

#### Interpolación lineal (red convolucional)

Para `L` capas ocultas, la capa oculta `i` (con `i = 1..L`) lleva:

```
neurons(i) = round(784 + (10 - 784) * i / (L + 1))
```

Con los valores por defecto (`L = 2`), la primera capa oculta queda **un tercio del camino**
entre 784 y 10 (526 neuronas) y la segunda **dos tercios** (268), como en la Figura 1.

> ⚠️ El PDF del enunciado dice 258 para la segunda capa oculta, pero 258 no cumple "cada capa
> disminuye en la misma cantidad" (526 → 258 baja 268; 258 → 10 baja 248). La fórmula de
> arriba es la que manda: da 268.

```
 Rectangular                    Convolucional
 784 → 512 → 512 → 10           784 → 526 → 268 → 10
```

Una vez creada, el programa debe permitir:

1. **Entrenar** la red por un número de épocas.
2. **Probarla** contra el conjunto de prueba.
3. **Guardar** la red en un archivo `*.pth`.

Luego de la primera opción (entrenar) debe mostrarse el **gráfico de la pérdida (*loss*) en
cada época** en un gráfico de línea. Luego de la segunda (probar) debe mostrarse la **matriz
de confusión** y las métricas de **precisión (*precision*), *accuracy* y *recall***.

Este **menú debe volver a presentarse** luego de terminar cualquiera de estas acciones,
permitiendo seguir entrenando.

### Requerimientos técnicos

Deberá entregar **el programa y cuatro redes**:

| # | Red | Clasificación |
|---|---|---|
| 1 | Rectangular | Fashion MNIST original (10 clases) |
| 2 | Convolucional | Fashion MNIST original (10 clases) |
| 3 | Rectangular | Clases simplificadas (4 clases) |
| 4 | Convolucional | Clases simplificadas (4 clases) |

La clasificación **simplificada** tiene cuatro clases, compuestas de las clases de Fashion
MNIST así:

| Clase simplificada | Clases de Fashion MNIST |
|---|---|
| **Top** | T-shirt (franela), Pullover (sweater), Coat (chaqueta), Shirt (camisa) |
| **Footwear** (calzado) | Sandal (sandalia), Sneaker (zapato deportivo), Ankle boot (bota) |
| **Bottom** | Trouser (pantalón), Dress (vestido) |
| **Bag** | Bag (mochila) |

Para lograr este cometido deberá **variar el número de capas ocultas** (y, en la red
rectangular, los **nodos por capa**) hasta encontrar una cantidad que produzca una **buena
precisión** sobre el conjunto de prueba **sin tener demasiadas neuronas ni requerir demasiadas
épocas**. Puede ser necesario introducir **otras optimizaciones** (por ejemplo: otro
optimizador, *learning rate*, *dropout*, *batch normalization*, *weight decay*, *early
stopping*...). **Estas deben poderse habilitar como opciones en el menú.**

### Rúbrica

Cada criterio vale 25% y se mide con el *accuracy* de la red entregada sobre el conjunto de
prueba:

| Criterio | La gran mayoría de las veces | La mayoría de las veces | Mejor que al azar | Peor que al azar | No ejecuta |
|---|---|---|---|---|---|
| La red **rectangular** (10 clases) clasifica correctamente el conjunto de prueba | 25% | 15% | 10% | 5% | 0% |
| La red **convolucional** (10 clases) clasifica correctamente el conjunto de prueba | 25% | 15% | 10% | 5% | 0% |
| La red **rectangular** (clases simplificadas) clasifica correctamente el conjunto de prueba | 25% | 15% | 10% | 5% | 0% |
| La red **convolucional** (clases simplificadas) clasifica correctamente el conjunto de prueba | 25% | 15% | 10% | 5% | 0% |

Umbrales de *accuracy*:

| Nivel | 10 clases (originales) | 4 clases (simplificadas) |
|---|---|---|
| La gran mayoría de las veces | **> 75%** (más de tres cuartas partes) | **> 80%** (más de cuatro quintos) |
| La mayoría de las veces | > 50% | > 50% |
| Mejor que al azar | > 10% | > 25% |
| Peor que al azar | < 10% | < 25% |
| No ejecuta esta red | — | — |

## Cómo se entrega

- El programa va en **un Jupyter Notebook**: **`pytorch_fashion_1.ipynb`**,
  **`pytorch_fashion_2.ipynb`** o **`pytorch_fashion_3.ipynb`**, dependiendo de tu elección,
  en esta misma carpeta (`tarea-3-codigo/`) — **uno por integrante**. Recuerda colocar tu
  **nombre y cédula** en la primera celda.
- Junto al notebook, las **cuatro redes entrenadas** en archivos `*.pth`, con este nombre
  (donde `N` es el número de tu notebook):

  | Archivo | Red |
  |---|---|
  | `pytorch_fashion_N_original_rectangular.pth` | Rectangular, 10 clases |
  | `pytorch_fashion_N_original_convolutional.pth` | Convolucional, 10 clases |
  | `pytorch_fashion_N_simplified_rectangular.pth` | Rectangular, 4 clases |
  | `pytorch_fashion_N_simplified_convolutional.pth` | Convolucional, 4 clases |

- **El notebook debe ejecutarse de arriba hacia abajo** (*Restart & Run All*) sin errores y
  terminar en el **menú**. Antes de hacer commit, corre *Restart & Run All* una vez y
  comprueba que todo funciona desde cero.
- Tu programa debe ser capaz de **cargar tus propios archivos `.pth`**. Para que eso sea
  posible sin depender de variables del notebook, **guarda junto a los pesos los datos
  necesarios para reconstruir la red** (por ejemplo, un `dict` con `state_dict` y los
  hiperparámetros: tipo de red, capas ocultas, neuronas por capa, épocas acumuladas,
  clasificación original/simplificada y las opciones de optimización activas).

### Dataset

Fashion MNIST se descarga con `torchvision.datasets.FashionMNIST(..., download=True)`. **No
lo subas al repo**: descárgalo en la carpeta `data/` de esta misma carpeta, que ya está en el
`.gitignore`.

### Dependencias

```
pip install torch torchvision matplotlib numpy notebook
```

(`scikit-learn` es opcional, solo si quieres usarlo para la matriz de confusión y las
métricas; también puedes calcularlas a mano con PyTorch/NumPy.)

## Reglas

- La tarea es **individual**: cada quien trabaja en su propio notebook, aunque compartan repo.
- Código en **inglés** (nombres, comentarios, mensajes de log); el texto que lee el usuario
  en el menú y las celdas de Markdown, en **español**.
