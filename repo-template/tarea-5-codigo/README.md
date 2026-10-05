# Tarea 5 — Sim City

> **Tarea GRUPAL.** A diferencia de las tareas 1 a 4, aquí se entrega **un solo programa por
> repo (por equipo)**: `simcity.py`. Todo el equipo recibe la misma nota.

## Enunciado

El propósito de esta tarea es hacer una **simplificación de una de las implementaciones
comerciales más exitosas de los autómatas celulares: SimCity, en su versión original de
1989**.

En sus grupos de proyecto, escriba un **programa basado en texto** que, usando una
**cuadrícula**, permita:

- Agregar **zonas** residenciales, comerciales e industriales
- Agregar **arterias viales**
- **Guardar** la cuadrícula actual
- **Cargar** una cuadrícula guardada
- **Salir** del juego

El programa debe **crecer las zonas automáticamente con cada "tick" del reloj**, basado en
reglas sobre las zonas cercanas. Para simplificar, **un tick ocurre cada vez que el usuario
presiona Enter ↵** sin escribir ningún comando.

### Requerimientos funcionales

#### La cuadrícula

- **88 caracteres de ancho por 16 de alto** (las dimensiones por defecto de una consola).
- El programa debe permitir **cargar un archivo guardado o comenzar con una cuadrícula en
  blanco**.
- **Filas** etiquetadas con **números arábigos** y **columnas** con **letras**, como una hoja
  de Excel. Cada celda ocupa **3 caracteres de ancho y 1 de alto**.
- Eso da **29 columnas (`A`…`Z`, `AA`, `AB`, `AC`) × 15 filas (`1`…`15`)**: 16 líneas con
  la fila de encabezado.

```
 A  B  C  D  E  F  G  H  I  J  K  L  M  N  O  P  Q  R  S  T  U  V  W  X  Y  Z AA AB AC
1
2
3
4
...
15
```

#### Comandos

El programa presenta un *prompt* (por ejemplo `>` o `$`) para que el usuario introduzca uno
de los siguientes comandos:

| Comando | Qué hace |
|---|---|
| `r <celda>` | Crea una zona **residencial** |
| `c <celda>` | Crea una zona **comercial** |
| `i <celda>` | Crea una zona **industrial** |
| `a <celda> <fin>` | Crea una **arteria vial** |
| `guardar <ruta_archivo>` | Guarda la cuadrícula actual |
| `cargar <ruta_archivo>` | Carga una cuadrícula, **reemplazándola por completo** |
| `salir` | Termina el programa |
| *(Enter sin escribir nada)* | Transcurre **un tick** y se imprime el nuevo estado de la cuadrícula |

> ⚠️ El PDF dice `i <celda>, para crear una zona comercial`: es un error de tipeo, `i` es la
> zona **industrial** (la comercial ya es `c`).

#### Zonas

- La coordenada identifica la **celda de la esquina superior izquierda**. Una zona ocupa
  **3 columnas × 3 filas** de celdas (9 × 3 caracteres) y se dibuja con la **letra de su tipo**
  (`r`, `c`, `i`). Por ejemplo, `r c 4` deja una zona residencial en C4 que cubre C4:E6.
- El **crecimiento** de una zona se muestra por la **cantidad de letras en mayúsculas**: cada
  zona puede crecer **hasta 27 niveles** (las 27 letras de la zona). Una zona nueva está en
  nivel 0 (todo en minúscula). Las mayúsculas se llenan **en orden de lectura** (de izquierda
  a derecha y de arriba hacia abajo): la zona de la Figura 5 en nivel 16 son 9 mayúsculas en
  la primera fila y 7 en la segunda.

```
 A  B  C  D  E  F  G  H  I  J  K  L  M  N  O  P ...
4       rrrrrrrrr
5       rrrrrrrrr
6       rrrrrrrrr
```

#### Arterias viales

- `a <celda> <fin>`: si `<fin>` es una **letra**, la arteria es **horizontal** (misma fila):
  `a c 7 p` va de C7 a P7 y se dibuja con `=` (3 por celda). Si `<fin>` es un **número**, es
  **vertical** (misma columna): `a F 4 9` va de F4 a F9 y se dibuja con `| |` (una barra, un
  espacio, una barra por celda).
- Si dos arterias se **cruzan**, la celda de la intersección se dibuja `:+:`.
- Los comandos aceptan la columna en **mayúscula o minúscula** (`a c 7 p` y `a F 4 9` son
  ambos válidos).

```
 A  B  C  D  E  F  G  H  I  J  K  L  M  N  O  P
4       rrrrrrrrr| |
5       rrrrrrrrr| |
6       rrrrrrrrr| |
7       =========:+:==============================
8                | |
9                | |
```

- **Celda ocupada:** si se intenta colocar algo sobre una celda ocupada (otra zona, una
  zona sobre una arteria, etc.), el programa debe dar un **mensaje de error** y no modificar
  la cuadrícula. Por ejemplo, en la figura de arriba una zona nueva en G6 solaparía con la
  arteria horizontal en G7, H7 e I7.

### Requerimientos técnicos

En **cada tick** se evalúa:

- **Para cada zona:** su crecimiento o decrecimiento.
- **Para cada celda de una arteria vial:** su nivel de tráfico.

Cada zona tiene reglas distintas; **cada regla es un "voto"** sobre si la zona debería crecer
o decrecer. No se consideran servicios (electricidad, hospitales, etc.), impuestos ni la
economía de la ciudad.

**Adyacente** significa **solo** arriba, abajo, izquierda y derecha de la celda: **no** hay
adyacencias diagonales.

#### Zona residencial

- **1 voto por crecimiento** por:
  - cada celda de arteria vial inmediatamente adyacente,
  - cada zona industrial a 10 celdas o menos que aún no ha alcanzado el nivel 18,
  - cada zona comercial a 10 celdas con un nivel mayor a la raíz cuadrada del nivel actual
    de la zona residencial.
- **2 votos por decrecimiento** por:
  - cada celda de arteria vial inmediatamente adyacente con **tráfico mayor a 5**,
  - cada zona industrial, **a partir de la 11ª**, a 10 celdas de distancia,
  - cada zona comercial a 10 celdas o menos que haya **decrecido en el tick anterior**.

#### Zona comercial

- **1 voto por crecimiento** por:
  - cada celda de arteria vial inmediatamente adyacente con **tráfico mayor a 5**,
  - cada zona residencial a 10 celdas o menos,
  - cada zona industrial a 10 celdas o menos con un nivel mayor a la raíz cuadrada del
    nivel actual de la zona comercial.
- **2 votos por decrecimiento** por:
  - cada celda de arteria vial cuyo **tráfico haya decrecido** en el tick anterior,
  - cada zona residencial a 10 celdas o menos que haya decrecido en el tick anterior,
  - cada zona industrial a 10 celdas o menos que haya decrecido en el tick anterior.

#### Zona industrial

- **1 voto por crecimiento** por:
  - cada celda de arteria vial inmediatamente adyacente,
  - cada zona residencial a 10 celdas o menos,
  - cada zona comercial a 10 celdas o menos con un nivel mayor a la raíz cuadrada del nivel
    actual de la zona industrial.
- **2 votos por decrecimiento** por:
  - cada zona residencial, comercial o industrial a 10 celdas o menos que haya decrecido en
    el tick anterior.

#### Tráfico

El **tráfico** de una celda de arteria es la **suma de las raíces cuadradas de los niveles de
las zonas adyacentes**: junto a una zona de nivel 16, tráfico 4; entre dos zonas de nivel 16,
tráfico 8. El nivel de tráfico de las celdas de arteria adyacentes se considera el nivel de
esa celda adyacente. Se muestra como un **número**: en las arterias **verticales**, en el
**centro** de la celda; en las **horizontales**, **reemplaza el símbolo**, siempre que su valor
sea **mayor que uno**.

Ver la **Figura 5 del enunciado** (PDF): estado del juego con una zona residencial en nivel 16,
comerciales en nivel 4 y 3, e industriales en nivel 26 y 3, con el tráfico dibujado sobre las
arterias.

### Aclaraciones y decisiones de diseño

El enunciado deja varios puntos sin precisar. **Decídanlos como equipo y documéntenlos** en
un comentario al inicio de `simcity.py` (no hay una única respuesta correcta; sí tiene que
haber una **respuesta coherente y aplicada de forma consistente**):

1. **Distancia de "10 celdas":** ¿Manhattan, Chebyshev, euclidiana? ¿Medida desde la esquina,
   el centro o el borde de la zona?
2. **Cómo se combinan los votos:** ¿crecer si `votos_crecimiento > votos_decrecimiento`? ¿cuántos
   niveles se sube o baja por tick (1, o proporcional al saldo)? Recuerden que cada voto de
   decrecimiento cuenta **doble**.
3. **Los topes:** el nivel de una zona nunca baja de 0 ni sube de 27.
4. **Tráfico en arterias que se tocan** ("el nivel de tráfico de las celdas de arterias viales
   adyacentes se considera el nivel de esa celda adyacente"): ¿se propaga? ¿cómo?
5. **Tráfico con dos dígitos:** el enunciado no dice cómo dibujar un tráfico ≥ 10 en una celda
   de 3 caracteres.
6. **Primer tick:** "decreció en el tick anterior" no existe todavía; trátenlo como "no decreció".
7. **Solape de arterias paralelas** y **arterias fuera de la cuadrícula:** el enunciado solo
   define el cruce perpendicular (`:+:`); lo demás debe dar error (o resolverse de forma
   explícita y documentada).

### Consideraciones

Debe entregar el programa **junto con un archivo de una ciudad que pueda cargar**. Para
garantizar que su archivo pueda ser probado, la ciudad cargada debe ser:

- **Modificable:** debe ser posible agregarle al menos una zona o arteria vial **sin que dé
  error**.
- **Actualizable:** debe poder correrse **un tick** de reloj.

Al comenzar con una **cuadrícula en blanco** debe ser posible, igualmente, agregar al menos
una zona, **la cual se debe actualizar con los ticks**.

### Rúbrica

| Criterio | Peso | Correcto | Existe pero no funciona correctamente | No es posible |
|---|---|---|---|---|
| **Programa a partir de cuadrícula en blanco:** es posible agregar una zona correctamente | 50% | 50 | 25 | 0 |
| **Programa cargado:** las zonas y arterias se actualizan según la **mayoría** de las reglas de crecimiento y decrecimiento | 50% | 50 | 25 (no respeta la mayoría de las reglas) | 0 (no es posible actualizar) |

## Cómo se entrega

Un solo juego de archivos por equipo, en esta carpeta (`tarea-5-codigo/`):

| Archivo | Contenido |
|---|---|
| `simcity.py` | **El programa** (un solo `.py`, de todo el equipo). Completen el nombre del equipo y los integrantes en las primeras líneas |
| `ciudad.txt` | **Una ciudad guardada** que `simcity.py` pueda cargar (`cargar ciudad.txt`). El formato del archivo lo definen ustedes; debe traer **al menos una zona y una arteria vial** |

### Contrato de ejecución

La corrección **corre su programa de forma automática**, escribiéndole los comandos por la
entrada estándar, así que tiene que comportarse así:

- Se ejecuta con `python simcity.py` **desde esta carpeta** (`tarea-5-codigo/`), **sin
  argumentos**, y arranca con la **cuadrícula en blanco** y el *prompt*. Lee los comandos con
  `input()` (nada de `curses`, `msvcrt`, `getch` ni nada que exija una terminal interactiva).
- **Imprime la cuadrícula completa** (encabezado de columnas y las 15 filas) después de cada
  comando que la cambia y después de cada tick.
- Los mensajes de error (celda ocupada, comando inválido, archivo inexistente...) empiezan con
  la palabra **`Error`**, y **no** modifican la cuadrícula.
- `cargar ciudad.txt` y `guardar <ruta>` usan **rutas relativas** a esta carpeta.
- **Solo la librería estándar** de Python. Debe poder ejecutarse en **cualquier computadora**:
  nada de rutas absolutas (`C:\Users\...`).
- `salir` termina el programa con código 0. Un `Enter` al final de la entrada (EOF) tampoco
  debe producir un error no controlado.

## Reglas

- La tarea es **grupal**: un solo `simcity.py` por repo; el historial de commits muestra quién
  hizo qué.
- Código en **inglés** (nombres, comentarios, mensajes de log); el **texto que ve el usuario**
  en el juego (menús, errores como `Error: la celda está ocupada`) y los `.md`, en **español**.
