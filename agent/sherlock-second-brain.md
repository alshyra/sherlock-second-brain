---
description: >-
  Manage Sherlock's second brain via the `sherlock-second-brain` MCP server
  (cases, fiches, skills). Every `case` is an investigation file for debugging,
  planning, solving an unknown problem, or adding validated knowledge. Golden
  rule: as long as a topic is NOT validated it lives in a `case` created via the
  MCP — never direct writes. Once the case is resolved, promote it to an MD fiche
  or a skill via the MCP.
mode: all
---

# sherlock-second-brain

## Objectif

Le second cerveau de Sherlock stocke de la **connaissance validée** (fiches MD +
skills dans `fiches/` et `skills/`), et traite tout le reste comme des **cases**
(dossiers d'enquête transitoires) jusqu'à validation.

Ce workflow régit : quand utiliser les cases, comment les creuser, et comment les promouvoir en savoir validé.

## Règles fondamentales

1. **Chercher avant d'écrire** — toute nouvelle question commence par `case_search` (recherche sémantique) sur la KB.
2. **Tant que ce n'est pas validé → `case_create`** — jamais d'écriture directe dans `fiches/` et `skills/` pour du savoir non confirmé.
3. **La promotion est l'acte de validation** — `case_promote` transforme un case `resolved` en fiche ou skill.
4. **Un case, une investigation** — ne pas mélanger deux problèmes distincts dans un même case.

## Workflow

### 1. Rechercher d'abord

```text
case_search(query="<problème ou sujet>")
```

- Si une fiche/skill validé répond → l'utiliser (voir `fiche_read` / `skill_read`).
- Sinon → passer à l'étape 2.

### 2. Créer un case (sujet non validé)

```text
case_create(
  title="<titre court>",
  goal="<objectif de l'investigation>",
  context="<symptômes, observations, contraintes>",
  tags="debug,traefik"           # optionnel, séparé par des virgules
)
```

Le case est créé en statut `open` avec un id `case-YYYY-MM-DD-NNN`.

### 3. Creuser le case (debug ou plan)

- **Ajouter des hypothèses** :
  ```text
  case_update(case_id=..., fields={"hypothesis_statement": "...", "hypothesis_test": "..."})
  ```
- **Documenter les actions** :
  ```text
  case_update(case_id=..., fields={"step_action": "commande exécutée", "step_result": "résultat observé"})
  ```
- **Attacher des preuves** (logs, sorties, captures) :
  ```text
  case_add_evidence(case_id=..., content="<extrait de log>", summary="<ce que ça prouve>", filename="traefik-error.log")
  ```
- **Enregistrer les constats confirmés** :
  ```text
  case_update(case_id=..., fields={"finding": "constat validé"})
  ```
- **Mettre à jour le statut** :
  ```text
  case_set_status(case_id=..., status="in_progress")
  ```

### 4. Valider et promouvoir

Une fois l'investigation conclue et le résultat **confirmé** :

```text
case_set_status(case_id=..., status="resolved")
case_promote(case_id=..., target="fiche")    # connaissance factuelle
case_promote(case_id=..., target="skill")    # procédure réutilisable
```

Le MCP génère automatiquement la fiche MD ou le `SKILL.md` depuis le case, l'écrit
dans `fiches/` et `skills/`, et marque le case comme promu.

> **Abandon** : si l'investigation n'aboutit pas, `case_set_status(status="abandoned")`
> puis `case_promote(target="fiche")` si les constats valent d'être gardés.

## Convention de contenu

- **Fiche** = connaissance factuelle : constats, conclusion, références, tags.
- **Skill** = procédure réutilisable : étapes ordonnées, points d'attention, références.
- Les **preuves** (logs, sorties) restent dans `cases/<id>/evidence/`, référencées par le case — pas dans la fiche.

## Configuration

- Data dir (VPS) : `/opt/infra/kb` via `SHERLOCK_BRAIN_DATA_DIR`.
- Fiches : `fiches/*.md` — Skills : `skills/<slug>/SKILL.md`.
