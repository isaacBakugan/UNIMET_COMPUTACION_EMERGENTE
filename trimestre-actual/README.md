# Trimestre actual

Insumos del trimestre en curso, consumidos por `scripts/crear-repos-trimestre.ps1` y
`scripts/actualizar-repos-trimestre.ps1`.

## Convención

```
trimestre-actual/
├── equipos.json   # insumo: vos lo editás con los equipos reales
└── estado.json    # generado por crear-repos-trimestre.ps1, no editar a mano
```

### `equipos.json` — contrato

Un solo archivo con todos los equipos del trimestre:

```json
[
  { "equipo": "grupo-lecturas-1", "delegados": ["username-delegado-1"] },
  { "equipo": "grupo-lecturas-2", "delegados": ["username-delegado-2"] }
]
```

- `equipo`: nombre del equipo, se usa para armar el nombre del repo (`<equipo>-<trimestre>`).
- `delegados`: usernames de GitHub (normalmente uno solo) del/los delegado(s) del equipo.
  Es la única persona que el script invita directamente con permiso `push`; ese delegado
  agrega al resto de su equipo como colaborador desde GitHub, porque él sí conoce a sus
  compañeros.
- Un equipo con `"delegados": []` se salta (no crea repo ni invita) — así se puede dejar
  declarado sin activar, como el `grupo-ejemplo` de este archivo.

`estado.json`: ledger de los repos activos del trimestre (equipo, repo, owner, url,
delegados, fecha de creación). Lo mantiene el script creador; `actualizar-repos-trimestre.ps1`
lo lee para saber a qué repos pushear cambios de template.

## Al cerrar el trimestre

Mueve o renombra esta carpeta (ej. a `../guias/trimestre-2026-2/insumos` o similar) antes de
vaciarla para el siguiente trimestre, si quieres conservar el histórico de qué delegados y
repos estuvieron activos.
