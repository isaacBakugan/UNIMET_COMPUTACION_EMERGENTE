# Corrección de la Tarea 2 — Perceptrón multicapa

El flujo del profesor tiene dos pasos: ejecutar `scripts/traer-repos-trimestre.ps1` para traer los repos a `.repos-trimestre-<trimestre>/` y ejecutar `python correcciones/tarea-2/corregir.py` para regenerar las notas y el análisis. Las entregas y los resultados se trabajan localmente y están ignorados por Git. El corrector no modifica los repositorios estudiantiles.

## Paso a paso

1. `git switch develop` y `git pull origin develop` antes de trabajar.
2. En Ubuntu/WSL, instalar una vez: `sudo apt install bubblewrap python3-matplotlib python3-numpy python3-pandas`.
3. Revisar `tarea.json`: cierre **11 de octubre de 2026, 23:59:59, Caracas** (incluye el minuto de las 11:59 p. m.), confirmado por la preparadora. `--cutoff` permite otra fecha ISO con zona horaria. Antes del cierre el reporte se marca PRELIMINAR.
4. Ejecutar desde la raíz primero el script del profesor y después la corrección:

   ```powershell
   pwsh -NoProfile -File scripts/traer-repos-trimestre.ps1
   python correcciones/tarea-2/corregir.py
   # Un comando: llama al mismo script del profesor antes de corregir
   python correcciones/tarea-2/corregir.py --update
   # Opcional: un equipo y un límite de ejecución mayor
   python correcciones/tarea-2/corregir.py --team G1 --timeout 180
   ```

   Alternativas con taskipy: `task fetch-repos`, `task grade-tarea-2` y `task grade-tarea-2-update`. `--update` respeta `--clones` y `--team`; si el script del profesor falla, la corrección se detiene antes de generar notas con datos incompletos.

   El punto de entrada está en esta carpeta (`corregir.py`) y reutiliza el motor `correcciones/calificador_tarea_2.py` y los módulos compartidos. El comando anterior sigue funcionando por compatibilidad, con la misma actualización oficial.
5. Revisar `needs_review` en `notas.csv` y el detalle de `informe.md`. Las matrices y las gráficas son evidencia capturada del programa: las notas automáticas son **propuestas**, sujetas a la interpretación docente de «clasifica correctamente». En particular, el corrector propone 25 solo cuando toda la matriz de prueba es diagonal; propone 15 si hay clasificaciones erróneas. No inventa un umbral porcentual. Si el docente considera correcta una clasificación con errores, debe registrar su decisión.
6. Para confirmar o corregir un criterio, registrar una entrada en `decisiones-docente.json` con `team`, `file`, `commit` exacto, `reason` y `cases` (ver ejemplo abajo). Volver a ejecutar el mismo comando. La decisión caduca al cambiar el commit y aparece una advertencia.
7. Para otra actualización estudiantil, repetir `python correcciones/tarea-2/corregir.py --update`. Las versiones al cierre y tardías se vuelven a evaluar; una nota tardía nunca reduce la nota al cierre.

## Resultados privados

Se guardan en `correcciones/resultados/<trimestre>/tarea-2/`, ignorado por Git:

| Archivo | Contenido |
|---|---|
| `notas.csv` | Nota propuesta por archivo, commit, cuatro criterios, descuento, revisión y análisis individual |
| `notas-sheets.csv` | Apellido, Nombre, Equipo, Nota, Observación; orden alfabético para Sheets |
| `informe.md` | Resumen, advertencias y explicación de los cuatro criterios por estudiante, con gráficas |
| `evidence/` | Una carpeta por estudiante, commit y caso: consola, errores, traza, resultado y gráficas |
| `sources/` | Exportación inmutable del commit evaluado mediante `git archive` |
| `inputs/` | Copia de los datasets oficiales y los casos de corrección utilizados |
| `ejecucion.json` | Cierre, semilla, versiones, hashes de configuración/casos/corrector y estado de revisión |

Una ejecución filtrada con `--team` reemplaza los CSV de esa carpeta con el subconjunto. Usar `--output correcciones/resultados/<trimestre>/tarea-2-equipo` para conservar aparte un reporte parcial.

Nunca subir notas, informes, evidencia ni fuentes de estudiantes al repositorio público. Se comparten con el profesor por un canal privado.

## Redes y menús de los estudiantes

`redes-entregadas.csv` relaciona cada programa con sus **dos redes individuales**. Las asociaciones actuales proceden de los nombres de carpeta/archivo, las cabeceras del código y el historial de creación de los CSV. Esta tabla describe dónde está el entregable; no asigna puntajes. Se mantiene al actualizar pesos o código; solo cambiarla si cambia la ruta o pertenencia del archivo. No se presta una red de otro integrante a quien no entregó la suya.

Cuando no hay asociación explícita se buscan `red_2d_2clases_N.csv` y `red_3d_4clases_N.csv` junto a `perceptron_multicapa_N.py`. Esta es una convención del corrector para nuevas entregas; no reemplaza retroactivamente los nombres que ya usaron los estudiantes. Una ruta ausente sale con 0 propuesto y **Revisar**; verificar primero si falta el entregable o su asociación.

Por defecto se usan las opciones del enunciado: crear=1, cargar=2; entrenar=1, probar=2, guardar=3, salir=4. La creación pregunta u,v,L,b, y el entrenamiento archivo y épocas. Menús distintos se documentan en `perfiles-consola.json`, atados al commit exacto y con motivo. Ya se registraron los menús actuales de Mario (selección «otro archivo») y Diego Mendez (confirmación de salida). Un perfil obsoleto avisa y no se aplica; el corrector intenta el menú estándar y marca para revisión si no obtiene evidencia.

Ejemplo de un perfil (usar un SHA real):

```json
[
  {
    "team": "Equipo",
    "file": "perceptron_multicapa_1.py",
    "commit": "SHA_COMPLETO",
    "reason": "El menú pide elegir Otro archivo antes de recibir la ruta.",
    "cases": {
      "given_network_2d_2class": {
        "answers": ["2", "{network}", "2", "5", "{test}", "4"]
      },
      "hidden_training_2d_2class": {
        "answers": ["1", "{u}", "{v}", "{L}", "{b}", "1", "5", "{train}", "{e}", "2", "5", "{test}", "4"]
      }
    }
  }
]
```

Los perfiles aceptan `network` como ruta relativa opcional. Nunca contienen código ejecutable ni reescriben el programa estudiantil. La traza registra todas las respuestas.

## Los cuatro criterios

- `given_network_2d_2class`: cargar la red entregada y probarla sobre el **test oficial** de 2D/2 clases.
- `given_network_3d_4class`: lo mismo con el test oficial de 3D/4 clases.
- `hidden_training_2d_2class`: extraer u,v,L,b,e de su red, crear una red nueva, entrenarla **e épocas** con el train no visto y probarla sobre el test no visto separado.
- `hidden_training_3d_4class`: lo mismo con 3D/4 clases.

Casos en `casos/`: 2D con relación XOR de signos y 3D con cuatro regiones según x1+x3 y x2-x3. Las filas de train y test no se repiten. Nunca se sincronizan hacia los repos estudiantiles; al estar en un central público son casos reservados para la corrección, **no secretos**. Se recomienda sustituirlos antes de una nueva cohorte si se necesita una evaluación no conocida.

Escala original: **25 / 15 / 0**, proporcional sobre 20, mínimo 1. Se reutiliza `rubrica.py`. El criterio automático exige una matriz de prueba no normalizada, con tamaño y soporte de clases iguales a los del CSV oficial. Se acepta orientación por filas o columnas. Una matriz incompleta, un timeout, una ruta/menú incompatible o un error no permiten concluir que la clasificación sea incorrecta: se informa 0 **propuesto**, con revisión necesaria. Una plantilla vacía sí obtiene la mínima sin ejecución.

Se leen los hiperparámetros de CSV con encabezado inicial y, para las entregas existentes, de CSV con encabezado después de u,v,L,b,e. El archivo original se entrega al cargador del estudiante sin repararlo; no se deduce la función de activación ni se ejecuta un modelo sustituto. El reporte permite revisar las diferencias de formato sin agregar penalizaciones ajenas a los cuatro criterios.

## Tardanzas, nombres y decisiones docentes

Se reutilizan `entregas.py`, `lista.py`, `rubrica.py` y la infraestructura bubblewrap de tarea 1. La selección usa la fecha del **commit**, no la hora del push (esta última requeriría el registro de recepción de GitHub).

Cada archivo es individual. Un cambio posterior al cierre en el programa o su red asociada activa la evaluación del último commit remoto con **−2**. Se conserva `max(nota al cierre, nota tardía − 2)`. `entregas-tardias.csv` solo registra excepciones con SHA y descuento explícitos. Cada versión tiene evidencia separada; el reporte conserva cualquier revisión pendiente de las versiones comparadas.

Los nombres vienen de la cabecera; también se reconocen comentarios con el nombre sin etiqueta cuando coinciden de forma única con la lista oficial del equipo. `alumnos.csv` completa cabeceras sin identidad. Se ordenan según `trimestre-actual/lista-entrega.csv`. Archivos sin nombre se asignan provisionalmente por equipo y deben confirmarse. No se agregaron cédulas de estudiantes a la configuración pública de esta tarea.

Ejemplo de decisión:

```json
[
  {
    "team": "Equipo",
    "file": "perceptron_multicapa_1.py",
    "commit": "SHA_COMPLETO",
    "reason": "Se revisaron código, matriz y gráficas.",
    "cases": {
      "given_network_2d_2class": {
        "outcome": "correct",
        "explanation": "La revisión docente confirma la clasificación del ejemplo."
      }
    }
  }
]
```

Outcomes válidos: `correct`, `incorrect`, `no_result`. Una decisión puede confirmar solo algunos criterios; los demás se ejecutan normalmente.

## Verificación y entrega al repositorio

```powershell
python -m pytest repo-template/tests correcciones/tests
```

Los gates descubren plantillas y casos por disco y fallan si no hay sujetos. Incluyen datos mal formados (con el nombre del archivo en el error), mínima para plantilla, cobertura de matrices, fecha centinela y política de mejor versión. Se comprobó el gate de datasets en rojo mediante una mutación temporal y luego se restauró el caso.

Trabajar en `develop`. Revisar `git status` y añadir archivos concretos; antes del commit, `git diff --cached --name-only` no debe mostrar resultados ni clones. Convención: `feat: Se agrega el corrector de la Tarea 2`. La publicación oficial requiere el flujo `develop → main` y revisión del profesor, conforme a `preparador.md`.
