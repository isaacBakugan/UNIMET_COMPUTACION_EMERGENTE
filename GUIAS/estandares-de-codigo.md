# Estándar de código de este repo

Regla simple: **el código va en inglés, los documentos van en español.**

## Qué va en inglés

Todo lo que es código o esquema de datos, en cualquier lenguaje del repo (Python, JSON,
PowerShell):

- Nombres de variables, funciones, parámetros
- Comentarios y docstrings dentro del código
- Claves de JSON (`team`, `delegates`, `reading`, `statement`, `options`, `correct_option`,
  `difficulty_level`, `status`, ...) y los valores que funcionan como identificadores/enum
  (`true_false`, `multiple_choice`, `tuesday-week-1`, `active`, ...)
- Mensajes de log/consola de los scripts (`Write-Host`, `Write-Warning`, mensajes de
  `assert` en los tests)

## Qué se queda en español

- Todo `.md`: READMEs, guías, este mismo documento
- El **contenido** que leen o escriben personas hispanohablantes: el texto de las
  preguntas (`statement`), nombres de equipo (`"grupo-lecturas-1"`), instrucciones para
  estudiantes
- Mensajes de commit de git (formato `[PREFIJO] Se hace tal cosa`, ver convención del
  autor) y nombres de rama
- Nombres de carpetas y archivos ya establecidos (`formatos/`, `correcciones/`, `guias/`,
  `corte-preguntas-1/`, `crear-repos-trimestre.ps1`, `equipos.json`, ...) — son la
  arquitectura del repo, renombrarlos rompe todas las referencias sin aportar nada

## Por qué esta línea y no otra

La distinción no es "todo lo nuevo en inglés" — es **estructura vs. contenido**:

- La *estructura* (cómo se llama un campo, una función, una variable) es la parte que
  cualquier ingeniero, en cualquier país, tiene que poder leer sin traducir. Es el estándar
  de facto de la industria.
- El *contenido* (qué dice una pregunta, cómo se llama un equipo, qué le explico a un
  estudiante) es para personas que trabajan en español. Traducirlo no aporta nada y le
  agrega fricción a quien realmente lo usa.

## Ejemplo concreto

```json
{
  "team": "grupo-lecturas-1",
  "questions": [
    {
      "id": "tue1-tf-1",
      "reading": "tuesday-week-1",
      "type": "true_false",
      "statement": "La fotosíntesis solo ocurre durante el día.",
      "options": ["Verdadero", "Falso"],
      "correct_option": "Falso",
      "difficulty_level": 3
    }
  ]
}
```

Las claves (`team`, `reading`, `type`, `statement`, ...) y los valores tipo enum
(`true_false`, `tuesday-week-1`) están en inglés. El texto real de la pregunta
(`statement`) y las opciones visibles al estudiante (`Verdadero`/`Falso`) están en
español, porque eso es lo que lee un estudiante hispanohablante.

## Al agregar código nuevo

Antes de escribir un test, un script o un esquema nuevo en este repo:

1. Nombres de campos/variables/funciones → inglés.
2. Comentarios de código y mensajes de error/log → inglés.
3. El README que explica ese código a estudiantes o al profesor → español.
4. Si el campo es contenido que lee un humano hispanohablante (texto de pregunta, nombre
   de equipo, instrucción) → se queda en español aunque esté dentro de un JSON.
