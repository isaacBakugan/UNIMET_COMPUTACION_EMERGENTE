# Actualización del template a mitad de trimestre

`scripts/actualizar-repos-trimestre.ps1` sincroniza cambios de `/repo-template` (un test
nuevo, una guía, un esquema) hacia los repos de grupo ya creados. Corre a mitad de
trimestre, con los equipos ya trabajando.

## La invariante

**El script nunca pisa el trabajo real del estudiante.** Dos categorías, protegidas por
dos mecanismos distintos:

1. **Archivos que el template trae como placeholder y el estudiante llena**
   (`preguntas.json`, en cualquier entregable: `preguntas.json` de la raíz,
   `corte-preguntas-1/preguntas.json`, y cualquier `corte-preguntas-N/preguntas.json` que
   se agregue después).

   Se protegen por **nombre de archivo**, no por path exacto (`$PreservedFiles` en el
   script, matcheado contra el *leaf* del path relativo). Así, un `corte-preguntas-2/` que
   se agregue el próximo trimestre queda protegido sin tener que tocar la lista — el
   error que se busca evitar es justo el de acordarse de agregar el path nuevo cada vez.

2. **Código que el estudiante escribe desde cero** (`perceptron.py` en
   `tarea-1-codigo/`, y análogos en tareas futuras).

   Estos archivos **no existen en el template** — el script solo copia archivos que
   encuentra bajo `/repo-template`, así que un archivo que el template nunca trae jamás
   es candidato a copiarse. No hace falta declararlo en ninguna lista; es una propiedad
   estructural del algoritmo de sync.

Si una tarea futura agrega al template un *stub* de código (por ejemplo, un
`perceptron.py` con un `TODO` en vez de no traerlo), esa categoría pasa a comportarse como
la 1: hay que agregar su nombre a `$PreservedFiles` el día que eso pase.

## Por qué importa

El script nunca hace `push --force`, y solo hace `git reset --hard` si se lo pides con
`-ResolveDivergence` (ver abajo), siempre después de respaldar los commits locales en una
rama. El historial de commits del equipo en GitHub nunca se borra. Pero pisar el
*archivo* en el working tree y commitear ese pisado sí destruye el estado que se va a
corregir: para el flujo de corrección automática, un `preguntas.json` reseteado al
placeholder es indistinguible de un equipo que no entregó nada.

## Cuando un equipo reescribe su historial (force push)

El script no usa `git pull`: hace `fetch` y compara el clon local con `origin`.

| Estado del clon | Qué hace el script |
|---|---|
| Al día, o solo adelantado | Nada que integrar; el push de la sync sigue su flujo normal |
| Atrasado (el equipo pushó commits nuevos) | `merge --ff-only`, nunca crea un merge commit |
| **Divergido** (el equipo hizo force push) | Salta ese repo sin tocar nada y avisa: lista los commits que solo existen en local y no son syncs del template (los que el force push dejó huérfanos) |

Para seguir adelante con un repo divergido, revisa esa lista (¿hay entregas que quieres
conservar como evidencia?) y vuelve a correr:

```powershell
pwsh -File scripts/actualizar-repos-trimestre.ps1 -ResolveDivergence
```

Con ese switch, los commits locales quedan en `backup/diverged-<fecha>` (solo en tu
máquina), el clon se alinea con `origin` y la sync se aplica encima de lo que el equipo
tiene hoy. `preguntas.json` se sigue preservando: es el del equipo, no el del backup.

**Ojo con las correcciones:** el corrector evalúa el historial de `origin/main`. Si un force
push posterior al cierre elimina el commit de la entrega a tiempo, esa entrega ya no es
alcanzable desde el remote; si la necesitas como evidencia, fija el commit del backup con
un tag antes de seguir.

## Cómo se garantiza (no solo se documenta)

`scripts/actualizar-repos-trimestre.Tests.ps1` corre estos casos:

- Preserva `corte-preguntas-1/preguntas.json` (no solo el de la raíz).
- No toca `preguntas.json` ni un `perceptron.py` de ejemplo en una sync real (sin
  `-DryRun`), contra un repo git local.
- Divergencia, con git real (un `origin` bare + el clon del script + el clon del equipo):
  salta sin merge ni push y nombra los commits en riesgo; con `-ResolveDivergence` respalda,
  alinea y pushea la sync; y el atraso simple se resuelve con fast-forward sin merge commit.

```powershell
Invoke-Pester scripts\actualizar-repos-trimestre.Tests.ps1
```

Verificado en rojo (revirtiendo el match por nombre a match por path exacto) antes de
darse por bueno: sin el fix, el test falla mostrando el `preguntas.json` real reemplazado
por el placeholder del template.
