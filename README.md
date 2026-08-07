# second-brain

MCP server + skill pour un **second cerveau** : la connaissance validée vit dans des
fiches MD et des skills, tout ce qui n'est **pas encore validé** vit dans des **cases**
(dossiers d'investigation JSON). Un case résolu se promeut en fiche ou en skill via le MCP.

```
source de vérité (fichiers)                      index dérivé (regénérable)
────────────────────────────────────             ────────────────────────────
<data_dir>/
  cases/<case-id>/case.json          ──→   vector/ (chromadb, gitignoré)
  cases/<case-id>/evidence/*.log           + recherche lexicale (fallback)
  fiches/*.md
  skills/<slug>/SKILL.md
```

## Stack

- Python 3.12+, `uv`
- [FastMCP](https://github.com/jlowin/fastmcp) (stdio)
- ChromaDB + fastembed (index vectoriel, *optionnel* : `[vector]`)
- jsonschema (validation des cases)
- jinja2 (rendu des fiches / skills promues)
- Architecture hexagonale : `domain/` (pydantic pur) · `application/` (cas d'usage + ports) · `adapters/` (filesystem, chroma, DTO MCP, templates)

## Installation (dans un projet)

```bash
uv init
uv add "second-brain[vector]"          # ou sans [vector] pour le fallback lexical
```

Ou depuis le repo :

```bash
cd second-brain
uv sync --extra vector
```

## Configuration

| Variable | Rôle | Défaut |
|----------|------|--------|
| `SECOND_BRAIN_DATA_DIR` | Dossier racine des données (cases + kb + vector) | `~/second-brain-data` |

## Câbler le serveur MCP dans opencode

Ajouter à `~/.config/opencode/opencode.json` :

```json
{
  "mcp": {
    "second-brain": {
      "type": "local",
      "command": ["/opt/second-brain/.venv/bin/python", "-m", "second_brain.server"],
      "enabled": true,
      "environment": {
        "SECOND_BRAIN_DATA_DIR": "/opt/infra/kb"
      }
    }
  }
}
```

## Installer l'agent globalement

L'agent est versionné dans ce repo (`agent/second-brain.md`). Pour le rendre
disponible à tous les agents opencode :

```bash
ln -s /opt/second-brain/agent/second-brain.md ~/.config/opencode/agent/second-brain.md
```

> Sur une autre machine, cloner le repo puis créer le même lien pointant vers le checkout.
> Redémarrer opencode après l'installation.

## Outils MCP

### Cases
| Outil | Rôle |
|-------|------|
| `case_create` | Créer une investigation (sujet non validé) |
| `case_get` / `case_list` | Lire / lister (filtres status, tag) |
| `case_search` | Recherche sémantique (cases + KB) |
| `case_update` | Ajouter findings / steps / hypothèses / conclusion / résultat d'hypothèse |
| `case_add_evidence` | Attacher une preuve (log, sortie, note) |
| `case_set_status` | open / in_progress / resolved / abandoned |
| `case_delete` | Supprimer un case et ses preuves |
| `case_promote` | Promouvoir un case résolu → fiche ou skill |

### KB
| Outil | Rôle |
|-------|------|
| `fiche_list` / `fiche_read` / `fiche_write` / `fiche_delete` | CRUD des fiches validées |
| `skill_list` / `skill_read` / `skill_write` / `skill_delete` | CRUD des skills validés |
| `index_rebuild` | Reconstruire l'index vectoriel depuis les fichiers |

## Schéma des cases

Défini dans [`schema/case.schema.json`](schema/case.schema.json) — source de vérité.
Tout case écrit via le MCP est validé contre ce schéma.

## Tests

```bash
uv run ruff check src/ tests/        # lint
uv run ty check                      # type checking
uv run pytest tests/ -v              # tests
```
