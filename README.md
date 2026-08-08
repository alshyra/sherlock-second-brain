# sherlock-second-brain

> Le célèbre enquêteur de Baker Street qui a inspiré ce projet : à sa manière,
> on mène des enquêtes rigoureuses (symptômes, indices, hypothèses, preuves,
> conclusion) pour **debugger**, analyser du code et **mémoriser** ce qu'on
> apprend à travers plusieurs projets.

MCP server + skill pour le **second cerveau de Sherlock** : la connaissance validée
vit dans des fiches MD et des skills, tout ce qui n'est **pas encore validé** vit
dans des **cases** (dossiers d'enquête JSON pour le debug et l'investigation).
Un case résolu se promeut en fiche ou en skill via le MCP.

```
source de vérité (fichiers)                      index dérivé (regénérable)
────────────────────────────────────             ────────────────────────────
<data_dir>/
  cases/<case-id>/case.json          ──→   vector/ (chromadb, gitignoré)
  cases/<case-id>/evidence/*.log           recherche hybride : vectoriel (Chroma)
  fiches/*.md                                + lexical (RRF)
  skills/<slug>/SKILL.md
```

## Stack

- Python 3.12+, `uv`
- [FastMCP](https://github.com/jlowin/fastmcp) (stdio)
- ChromaDB + fastembed (index vectoriel, modèle multilingue MiniLM-L12)
- jsonschema (validation des cases)
- jinja2 (rendu des fiches / skills promues)
- Architecture hexagonale : `domain/` (pydantic pur) · `application/` (cas d'usage + ports) · `adapters/` (filesystem, chroma, lexical, hybride RRF, DTO MCP, templates)

## Installation (dans un projet)

```bash
uv init
uv add sherlock-second-brain
```

Ou depuis le repo :

```bash
cd sherlock-second-brain
uv sync
```

## Configuration

| Variable | Rôle | Défaut |
|----------|------|--------|
| `SHERLOCK_BRAIN_DATA_DIR` | Dossier racine des données (cases + kb + vector) | `~/sherlock-second-brain-data` |

## Câbler le serveur MCP dans opencode

Ajouter à `~/.config/opencode/opencode.json` :

```json
{
  "mcp": {
    "sherlock-second-brain": {
      "type": "local",
      "command": ["/opt/sherlock-second-brain/.venv/bin/python", "-m", "sherlock_second_brain.server"],
      "enabled": true,
      "environment": {
        "SHERLOCK_BRAIN_DATA_DIR": "/opt/infra/kb"
      }
    }
  }
}
```

## Installer l'agent globalement

L'agent est versionné dans ce repo (`agent/sherlock-second-brain.md`). Pour le rendre
disponible à tous les agents opencode :

```bash
ln -s /opt/sherlock-second-brain/agent/sherlock-second-brain.md ~/.config/opencode/agent/sherlock-second-brain.md
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

## Recherche hybride

`case_search` combine deux moteurs via **Reciprocal Rank Fusion** (`adapters/hybrid.py`) :

- **Vectoriel** (`adapters/chroma.py`) : embeddings **multilingues** (MiniLM-L12, ~0.22GB, français inclus), collection persistante dans `vector/`, régénérable via `index_rebuild`.
- **Lexical** (`adapters/lexical.py`) : chevauchement de tokens, zéro dépendance — un doc pertinent pour un terme exact mais raté par le vectoriel remonte quand même.

Fusion RRF : `score(d) = 1/(k + rang_vector) + 1/(k + rang_lexical)`, `k = 60`. Le premier `index_rebuild` télécharge le modèle.

## Schéma des cases

Défini dans [`schema/case.schema.json`](schema/case.schema.json) — source de vérité.
Tout case écrit via le MCP est validé contre ce schéma.

## Tests

```bash
uv run ruff check src/ tests/        # lint
uv run ty check                      # type checking
uv run pytest tests/ -v              # tests
```
