# Parciales por Google Forms

Flujo: banco de Moodle → template → examen resuelto → Google Form. Todo lo que lleva respuestas
correctas (`banco/`, `specs/*.local.json`, `apps-script/<target>/`) está ignorado por git.

```
Moodle XML ─ banco.py ─► banco/banco.json + catalogo.csv   (+ banco/propias/*.json, preguntas escritas a mano)
template ─ armar.py ─► specs/<nombre>.resuelto.local.json   (revisable y editable a mano)
publicacion.json ─ publicar.py ─► apps-script/practica/ExamData.gs ─ clasp push ─► createExam() ─► Form de la práctica
                                  apps-script/parcial/ExamData.gs  ─ clasp push ─► createExam() ─► Form del parcial
```

Dos proyectos de Apps Script conviven (`practica` y `parcial`), cada uno con su `ExamData.gs`. Qué examen resuelto va
en cada uno lo dice [publicacion.json](publicacion.json) (versionado, sin respuestas).

## Uso

```powershell
python parciales/banco.py                                   # normaliza el export (task: import-bank)
Copy-Item parciales\examen.ejemplo.json parciales\specs\parcial-1.local.json
python parciales/armar.py parciales/specs/real-1-practica.local.json     # sortea (task: build-exam); la práctica primero
python parciales/armar.py parciales/specs/parcial-1-real.local.json       # el real excluye la práctica
python parciales/publicar.py                                # genera ExamData.gs de los dos proyectos (task: build-form)
python parciales/publicar.py --push                         # ... y clasp push en cada uno (task: publish-forms)
python parciales/publicar.py --only parcial --push          # un solo proyecto
```

Después se ejecuta `createExam` en el editor de Apps Script **de cada proyecto** (`clasp open` dentro de su carpeta) y el
log trae el link de edición y el publicado. `createExam` es idempotente (misma data = no crea otro Form);
`createExamAgain` crea una copia.

**Siguiente parcial:** resolver los dos exámenes nuevos, cambiar los dos nombres en `publicacion.json` y correr
`python parciales/publicar.py --push`. `Code.gs` y `appsscript.json` viven una sola vez en `apps-script/` y `publicar.py`
los copia a cada proyecto en cada corrida, así que los proyectos no pueden divergir. Si algún examen falla al construirse
no se escribe ningún proyecto (todo o nada).

- **Preguntas propias**: las que no existen en Moodle van en `banco/propias/*.json` (una por archivo:
  `category`, `name`, `stem`, `options` con una sola `correct`). `banco.py` las descubre por disco y las fusiona en cada
  import. Variantes de una misma pregunta = mismo nombre con número final (`Forward Propagation 1/2`): misma familia,
  distinta pregunta. En un template se fijan por `{"id"}` (ver `banco/catalogo.csv`); si el enunciado cambia, cambia el id
  y `armar.py` falla con "not in the bank" en vez de sortear otra cosa.

- **Template**: cada `pick` es `{"category", "count"}` (sorteo con la seed, una pregunta por familia de
  variantes) o `{"id"}` (fija una pregunta; los ids están en `banco/catalogo.csv`). Las preguntas con
  imagen, pseudocódigo con sangría o LaTeX se saltan salvo `"include_review": true`.
- **Puntos**: Google Forms solo admite puntos enteros por pregunta. Si el template usa 0.5, todo se escala
  (×2) y la descripción del Form lo explica; volver a la escala de 20 lo hace el corrector.
- **Modos**: `practice` (secciones, feedback con la respuesta correcta, sin login) y `real` (preguntas y
  un intento por usuario, correo, apellidos, nombres y cédula (solo números) obligatorios en una primera página, sin feedback). Un examen `real` con
  imágenes se rechaza: en Forms la imagen es un ítem aparte y el barajado la separaría de su pregunta.

## Directriz: examen de práctica vs examen real

La práctica ("Real 1 Práctica") y el parcial ("Parcial 1 Real") comparten estructura y modo `real`, para que
los estudiantes prueben todo el flujo antes. Regla de repetición:

- **La misma familia puede salir en ambos** (el estudiante practica el concepto), **nunca la misma pregunta**.
- El template del real declara `"exclude_exams": ["real-1-practica"]`. Si el sorteo cae en una pregunta ya
  usada en la práctica, un guard la sustituye por otra variante de su familia; si la familia no tiene más
  variantes, toma la siguiente familia de la categoría. Cada sustitución queda en `substitutions` del
  resuelto y se imprime al armar.
- **Orden**: se resuelve primero la práctica y después el real (el real lee el resuelto de la práctica).
- La puntuación 0.25 / 0.5 / 2.5 se escala x4 en Google (1 / 2 / 10 puntos, total 80); la nota sobre 20 es el puntaje / 4.

## Preparación única del lado de Google

1. Activar la **Google Apps Script API** en https://script.google.com/home/usersettings con la cuenta
   dueña de los Forms.
2. `npm install -g @google/clasp` y `clasp login`.
3. Un proyecto por carpeta de `publicacion.json`. Después de la primera corrida de `publicar.py` (que crea
   `apps-script/<target>/`), una sola vez por proyecto:
   ```powershell
   Set-Location parciales\apps-script\parcial
   clasp create --type standalone --title "Parciales Forms - parcial"
   ```
   (escribe `.clasp.json` dentro de esa carpeta, ignorado por git; `clasp create` puede sobrescribir `appsscript.json`, no
   importa: `publicar.py` lo vuelve a copiar desde el original en cada corrida). Hace falta `clasp push` completo: si
   falla, en Google se queda el `ExamData.gs` anterior y `createExam` solo devuelve el link del Form viejo
   ("Already created"); `publicar.py --push` corta y lo dice.
4. Primera ejecución de `createExam`: autorizar los permisos. Una app propia sin verificar muestra
   "Google no verificó esta app": Avanzado → Ir a "Parciales Forms" (no seguro).

## Qué verificar en la prueba de humo

La API no documenta todo; esto se comprueba mirando el Form creado:

- [ ] Es un quiz con puntaje (total 4 en la prueba de humo).
- [ ] El Form está publicado y acepta respuestas (la REST API crea los Forms despublicados desde jun-2026; confirmar que `FormApp` no).
- [ ] Feedback de práctica: al responder aparece "La respuesta correcta es: ...".
- [ ] El log dice `Option shuffle: off`. El barajado de opciones (`shuffle_options: true` en el template) no está implementado: Apps Script no lo expone y Forms no es un servicio avanzado; el log lo avisa con `NOT APPLIED`.
- [ ] En Configuración → Pruebas, ver cuándo se liberan las notas (inmediato o tras revisión): no es configurable por API.
- [ ] En modo `real`: los datos de identificación (apellidos, nombres, cédula de 6 a 9 dígitos) salen primero, en su propia página; las preguntas de la página 2 salen barajadas; un intento por usuario; correo obligatorio.
