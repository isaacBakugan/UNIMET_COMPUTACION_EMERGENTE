# Trimestre actual

Insumos del trimestre en curso, consumidos por `scripts/crear-repos-trimestre.ps1` y
`scripts/actualizar-repos-trimestre.ps1`.

## Convención

Un subdirectorio por equipo. El nombre de la carpeta es el nombre del equipo:

```
trimestre-actual/
├── grupo-lecturas-1/
│   └── delegado.txt   # username de GitHub del delegado del equipo
├── grupo-lecturas-2/
│   └── delegado.txt
└── estado.json         # generado por crear-repos-trimestre.ps1, no editar a mano
```

`delegado.txt`: un username de GitHub por línea (normalmente uno solo). Es la única persona
que el script invita directamente; ese delegado agrega al resto de su equipo como
colaborador desde GitHub, porque él sí conoce a sus compañeros.

`estado.json`: ledger de los repos activos del trimestre (equipo, repo, owner, url,
delegados, fecha de creación). Lo mantiene el script creador; `actualizar-repos-trimestre.ps1`
lo lee para saber a qué repos pushear cambios de template.

## Al cerrar el trimestre

Mueve o renombra esta carpeta (ej. a `../guias/trimestre-2026-2/insumos` o similar) antes de
vaciarla para el siguiente trimestre, si quieres conservar el histórico de qué delegados y
repos estuvieron activos.
