# second-brain

MCP server + skill pour un **second cerveau** : la connaissance validée vit dans des
fiches MD et des skills, tout ce qui n'est **pas encore validé** vit dans des **cases**
(dossiers d'investigation JSON). Un case résolu se promeut en fiche ou en skill via le MCP.

```
source de vérité (fichiers)                      index dérivé (regénérable)
────────────────────────────────────             ────────────────────────────
<data_dir>/
  cases/<case-id>/case.json          ──→   chromadb/ (vector, gitignoré)
  cases/<case-id>/evidence/*.log           + recherche lexicale (fallback)
  kb/fiches/*.md
  kb/skills/<slug>/SKILL.md
```

## Stack

- Python 3.12+, `uv`
- [FastMCP](https://github.com/jlowin/fastmcp) (stdio)
- ChromaDB + fastembed (index vectoriel, *optionnel* : `[vector]`)
- jsonschema (validation des cases)

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

## Installer le skill globalement

Le skill est versionné dans ce repo (`skill/second-brain/SKILL.md`). Pour le rendre
disponible à tous les agents opencode :

```bash
ln -s /opt/second-brain/skill/second-brain ~/.agents/skills/second-brain
```

> Sur une autre machine, cloner le repo puis créer le même lien pointant vers le checkout.

## Outils MCP

### Cases
| Outil | Rôle |
|-------|------|
| `case_create` | Créer une investigation (sujet non validé) |
| `case_get` / `case_list` | Lire / lister (filtres status, tag) |
| `case_search` | Recherche sémantique (cases + KB) |
| `case_update` | Ajouter findings / steps / hypothèses / conclusion |
| `case_add_evidence` | Attacher une preuve (log, sortie, note) |
| `case_set_status` | open / in_progress / resolved / abandoned |
| `case_promote` | Promouvoir un case résolu → fiche ou skill |

### KB
| Outil | Rôle |
|-------|------|
| `fiche_list` / `fiche_read` / `fiche_write` | CRUD des fiches validées |
| `skill_list` / `skill_read` | CRUD des skills validés |
| `index_rebuild` | Reconstruire l'index vectoriel depuis les fichiers |

## Schéma des cases

Défini dans [`schema/case.schema.json`](schema/case.schema.json) — source de vérité.
Tout case écrit via le MCP est validé contre ce schéma.

## Tests

```bash
uv run pytest tests/ -v
uv run ruff check src/ tests/
```
