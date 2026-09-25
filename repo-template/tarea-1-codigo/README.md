# Tarea 1 — Perceptrón

## Enunciado

El propósito de esta tarea es explorar las potencialidades y limitaciones de un
perceptrón.

Escriba un programa de Python que permita a un usuario interactuar con un perceptrón. El
programa debe recibir un archivo CSV con `n` columnas — el cual contiene los valores a
predecir — y mostrarlos en un gráfico de dispersión. Los `n-1` pesos de entrada y la
función de activación deben ser escogidos por el usuario.

Al terminar, el programa debe permitirle al usuario probar con otros pesos.

### Requerimientos funcionales

El programa debe iniciar cargando los valores del archivo CSV. Cada línea del archivo
constituye un vector donde las primeras `n-1` columnas son los valores de entrada, y la
`n`-ésima columna es la salida esperada.

El programa debe, entonces, leer del usuario los pesos para:

- el sesgo,
- cada una de las `n-1` columnas, y
- la función de activación.

A este fin, debe implementar **dos** de las funciones de activación vistas en clase.

El programa debe entonces crear tres gráficos con `matplotlib.pyplot.scatter` que
muestren, para cada vector de entrada:

- el valor esperado,
- el valor predicho por el perceptrón,
- si los valores anteriores coinciden, como su color (**verde** si coinciden, **rojo** si
  no coinciden).

> Nota: si `n > 3`, solo deben graficar las primeras dos dimensiones del vector de
> entrada.

### Requerimientos técnicos

- Debe escribir el programa **desde cero**: la función suma, la función de activación, y
  el procedimiento de ejecución.
- El programa debe correr por consola.
- **No se permite el uso de otras librerías excepto `matplotlib`.**
- **No se permite consultar a ChatGPT o sus derivados.**

### Rúbrica

| Criterio | Correctamente | Incorrectamente | No hace nada |
|---|---|---|---|
| Separa el ejemplo linealmente separable dado | 25% | 15% | 0% |
| No separa el ejemplo linealmente no-separable dado | 25% | 15% | 0% |
| Separa un ejemplo linealmente separable no visto | 25% | 15% | 0% |
| No separa un ejemplo linealmente no-separable no visto | 25% | 15% | 0% |

Los ejemplos "no vistos" no están en este repo — los aplica la corrección del repo
central.

## Cómo se entrega

- El programa va en **`perceptron_1.py`, `perceptron_2.py`, o `perceptron_3.py`**, dependiendo de tu elección, en esta misma carpeta — esos son los archivos que se corrigen (uno por integrante).
- `assets/` trae los datasets reales (columnas `x1,x2,y`, con encabezado) con los que
  deben correr su perceptrón:
  - `no_separables.csv`
  - `fuzzy_separables.csv`

  Son los mismos datos sobre los que corre la evaluación automática.
- Necesitan `matplotlib` instalado para correr su programa: `pip install matplotlib`.

## Cómo se valida

Hay dos pruebas de validación que chequean el formato localmente (la correctitud la evalúa la rúbrica):

- **Validación del equipo**: Chequea que existan los 3 archivos y compilen.
  Para correrla: `pytest tarea-1-codigo/tests/test_validar_tarea_equipo.py`
- **Validación individual**: Chequea exclusivamente tu archivo.
  Para correrla en PowerShell, debes indicar qué archivo validar usando una variable de entorno. Por ejemplo:
  `$env:PERCEPTRON_FILE="perceptron_1.py"; pytest tarea-1-codigo/tests/test_validar_tarea_individual.py`

En ambos casos se revisa:
- Que exista el archivo correspondiente
- Que sea Python válido (compila)
- Que no importe ninguna librería fuera de `matplotlib`
