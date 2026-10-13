# Parciales por Google Forms

Flujo: banco de Moodle → template → examen resuelto → Google Form. Todo lo que lleva respuestas
correctas (`banco/`, `specs/*.local.json`, `apps-script/ExamData.gs`) está ignorado por git.

```
Moodle XML ─ banco.py ─► banco/banco.json + catalogo.csv
template ─ armar.py ─► specs/<nombre>.resuelto.local.json   (revisable y editable a mano)
resuelto ─ formulario.py ─► apps-script/ExamData.gs ─ clasp push ─► createExam() ─► Google Form
```

## Uso

```powershell
python parciales/banco.py                                   # normaliza el export (task: import-bank)
Copy-Item parciales\examen.ejemplo.json parciales\specs\parcial-1.local.json
python parciales/armar.py parciales/specs/parcial-1.local.json            # sortea (task: build-exam)
python parciales/formulario.py parciales/specs/parcial-1.resuelto.local.json   # task: build-form
clasp push                                                  # sube Code.gs y ExamData.gs
```

Después se ejecuta `createExam` en el editor de Apps Script y el log trae el link de edición y el
publicado. `createExam` es idempotente (misma data = no crea otro Form); `createExamAgain` crea una copia.

- **Template**: cada `pick` es `{"category", "count"}` (sorteo con la seed, una pregunta por familia de
  variantes) o `{"id"}` (fija una pregunta; los ids están en `banco/catalogo.csv`). Las preguntas con
  imagen, pseudocódigo con sangría o LaTeX se saltan salvo `"include_review": true`.
- **Puntos**: Google Forms solo admite puntos enteros por pregunta. Si el template usa 0.5, todo se escala
  (×2) y la descripción del Form lo explica; volver a la escala de 20 lo hace el corrector.
- **Modos**: `practice` (secciones, feedback con la respuesta correcta, sin login) y `real` (preguntas y
  opciones barajadas, un intento por usuario, correo obligatorio, sin feedback). Un examen `real` con
  imágenes se rechaza: en Forms la imagen es un ítem aparte y el barajado la separaría de su pregunta.

## Preparación única del lado de Google

1. Activar la **Google Apps Script API** en https://script.google.com/home/usersettings con la cuenta
   dueña de los Forms.
2. `npm install -g @google/clasp` y `clasp login`.
3. Desde la raíz del repo: `clasp create --type standalone --title "Parciales Forms" --rootDir parciales/apps-script`
   (escribe `.clasp.json`, ignorado por git). Comprobar que `appsscript.json` conserva `enabledAdvancedServices`.
4. Primera ejecución de `createExam`: autorizar los permisos. Una app propia sin verificar muestra
   "Google no verificó esta app": Avanzado → Ir a "Parciales Forms" (no seguro).

## Qué verificar en la prueba de humo

La API no documenta todo; esto se comprueba mirando el Form creado:

- [ ] Es un quiz con puntaje (total 4 en la prueba de humo).
- [ ] El Form está publicado y acepta respuestas (la REST API crea los Forms despublicados desde jun-2026; confirmar que `FormApp` no).
- [ ] Feedback de práctica: al responder aparece "La respuesta correcta es: ...".
- [ ] El log dice `Option shuffle: applied ...`; si dice `NOT APPLIED`, anotar el error.
- [ ] En Configuración → Pruebas, ver cuándo se liberan las notas (inmediato o tras revisión): no es configurable por API.
- [ ] En modo `real`: preguntas barajadas, un intento por usuario y correo obligatorio.
