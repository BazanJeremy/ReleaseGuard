# ReleaseGuard

**Verrou de release explicable — fusionne résultats de tests, couverture et flakiness
en un verdict GO / NO GO argumenté, prêt à bloquer un pipeline.**

[![CI](https://github.com/BazanJeremy/ReleaseGuard/actions/workflows/ci.yml/badge.svg)](https://github.com/BazanJeremy/ReleaseGuard/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

> 🇬🇧 [English version](README.en.md)

---

## Le problème QA

Des tests verts ne suffisent pas à autoriser une mise en production. La décision de
release agrège en réalité plusieurs signaux : le rapport de tests, le tableau de bord
de couverture, la connaissance tribale des échecs « habituellement flaky ». Cette
synthèse vit dans la tête d'un release manager — non auditable, non répétable, perdue
quand la personne est absente.

ReleaseGuard transforme cette synthèse en **quality gate déterministe et explicable**,
posée sur des artefacts CI standard : JUnit XML (tests), Cobertura XML (couverture),
rapport [FlakySense](https://github.com/BazanJeremy/flakysense) JSON (flakiness).

## L'approche : verrous durs d'abord, score ensuite

**Jamais de moyenne pure.** Moyenner est l'anti-pattern classique du release gate :
une excellente couverture peut masquer arithmétiquement un smoke test qui échoue. Un
blocant ne doit pas être compensable ([ADR-001](docs/adr/ADR-001-release-gate-model.md)).

| Étage | Règle |
|---|---|
| **G1** — échec réel | ≥ 1 test en échec *non identifié comme flaky* ⇒ `NO GO` |
| **G2** — plancher de couverture | couverture ligne < 60 % ⇒ `NO GO` |
| **Score** (si aucun verrou déclenché) | `0.50·tests + 0.25·couverture + 0.25·flakiness` — ≥ 0.80 ⇒ `GO`, sinon `CONDITIONAL GO` |

Trois engagements structurent le modèle :

- **La règle inter-signaux.** Un test en échec que FlakySense identifie comme flaky ne
  déclenche pas G1 : l'échec est *excusé nominativement* dans les conditions du verdict,
  plafonné à `CONDITIONAL GO`. Aucun parseur seul ne peut produire cette décision —
  elle n'existe que dans la fusion. La jointure repose sur les node ids pytest complets
  ([ADR-002](docs/adr/ADR-002-test-identity-join.md)) ; un raté de jointure ne peut que
  durcir le verdict, jamais excuser un échec à tort. Le design rejeté (jointure par nom
  court) aurait laissé passer un faux GO par collision de noms — contrefactuel vérifié
  et rejoué en test de régression ([bug evidence #2](docs/bug-evidence.md)).
- **`NO GO` exige un blocant nommé.** Le score seul ne peut jamais opposer un veto : un
  score bas sans blocant identifiable est une livraison conditionnelle avec risques
  listés, pas un blocage au ressenti.
- **Le verdict ne dépend jamais d'un LLM.** La couche IA (optionnelle, activée par
  `ANTHROPIC_API_KEY`) rédige le rationale des `CONDITIONAL GO` — rien d'autre. Elle ne
  peut modifier ni le verdict, ni le score, ni les conditions : c'est verrouillé par des
  tests. Sans clé API, tout fonctionne à l'identique en mode déterministe.

## Un verdict rendu

Sortie réelle sur le scénario d'exemple `scenario_conditional` :

```
$ releaseguard --junit junit.xml --coverage coverage.xml --flaky flakysense-report.json

ReleaseGuard verdict: CONDITIONAL GO (score 0.62)

Gates:
  [pass ] G1 real failure: no non-flaky failure
  [pass ] G2 coverage floor: line coverage 72% vs floor 60%

Signals:
  tests      1.00 (weight 0.50) 9/9 non-excused tests passed
  coverage   0.48 (weight 0.25) line coverage 72% on the 60%-85% ramp
  flakiness  0.00 (weight 0.25) 2 flaky of 10 executed tests

Conditions:
  - excused flaky failure: tests/test_search.py::test_search_pagination (source: flakysense)
  - weakest signal: flakiness at 0.00 (2 flaky of 10 executed tests)

Rationale (system1):
  No blocker; score 0.62 below GO threshold 0.80. [...]
```

Code de sortie `1` — un pipeline verrouille directement dessus : `0` GO,
`1` CONDITIONAL GO, `2` NO GO, `3` erreur ([ADR-003](docs/adr/ADR-003-cli-contract.md)).
Sortie JSON complète disponible via `--json`.

## Démo locale

```bash
git clone https://github.com/BazanJeremy/ReleaseGuard.git
cd ReleaseGuard
python -m venv .venv && source .venv/bin/activate   # Windows : .\.venv\Scripts\Activate.ps1
pip install -e .[dev]
python -m pytest        # 89 tests — aucune clé API requise

# les trois scénarios canoniques (codes de sortie attendus : 0, 2, 1)
releaseguard --junit data/samples/scenario_go/junit.xml --coverage data/samples/scenario_go/coverage.xml --flaky data/samples/scenario_go/flakysense-report.json
releaseguard --junit data/samples/scenario_no_go/junit.xml --coverage data/samples/scenario_no_go/coverage.xml --flaky data/samples/scenario_no_go/flakysense-report.json
releaseguard --junit data/samples/scenario_conditional/junit.xml --coverage data/samples/scenario_conditional/coverage.xml --flaky data/samples/scenario_conditional/flakysense-report.json
```

Narration System 2 optionnelle : `pip install -e .[llm]` et définir
`ANTHROPIC_API_KEY`. Tout ce qui précède fonctionne à l'identique sans.

## Intégration CI

ReleaseGuard s'insère dans n'importe quelle CI par ses codes de sortie — GitHub
Actions, GitLab CI, Azure DevOps :

```bash
# bloque le pipeline sur NO GO, laisse passer GO et CONDITIONAL GO
releaseguard --junit reports/junit.xml --coverage coverage.xml || test $? -le 1
```

Ce dépôt le prouve sur lui-même : à chaque push, la CI exécute la suite de tests puis
**ReleaseGuard évalue les artefacts de son propre build** et publie le verdict dans le
job summary ([.github/workflows/ci.yml](.github/workflows/ci.yml)). L'outil n'est pas
une démo posée à côté du projet — il est le verrou de release du projet.

## Stack technique

| Couche | Choix |
|---|---|
| Langage | Python 3.12+ |
| Modèles de données | Pydantic v2 |
| Couche IA (optionnelle) | Anthropic Claude — narration System 2 uniquement |
| Framework de test | pytest — 89 tests, zéro clé API requise |
| CI | GitHub Actions — verrou dogfood bloquant |
| Décisions d'architecture | 3 ADRs ([docs/adr/](docs/adr/)) + [journal de bugs](docs/bug-evidence.md) |

## Limites

Des choix assumés, documentés dans les ADRs :

- **Trois parseurs seulement** (JUnit, Cobertura, FlakySense). Tout nouveau type de
  signal est un point d'extension, pas du périmètre v1.
- **Les pondérations ne sont pas réglables en ligne de commande.** Les seuils le sont ;
  changer les poids est une décision de gouvernance qui passe par un ADR remplaçant,
  pas par un flag de pipeline ([ADR-003](docs/adr/ADR-003-cli-contract.md)).
- **Pas de conteneurisation.** L'histoire de déploiement de ce dépôt est son propre
  verrou CI (dogfood) ; le packaging conteneur est démontré ailleurs dans le portfolio.
- **Narration IA conditionnelle à une clé.** Sans `ANTHROPIC_API_KEY`, le rationale
  System 1 déterministe est rendu — le verdict est identique dans les deux cas.

## Positionnement dans le portfolio

P5 d'un portfolio de 6 projets AI Test Engineering. À ne pas confondre avec
[anomaly-sentinel](https://github.com/BazanJeremy/anomaly-sentinel) : là-bas, l'IA est
le **système sous test** — on valide un classifieur LLM comme composant critique. Ici,
le **processus de livraison** est l'objet : ReleaseGuard verrouille la décision de
livrer n'importe quel build, et l'IA n'y décide rien.
[FlakySense](https://github.com/BazanJeremy/flakysense) (P4) fournit l'un des trois
signaux d'entrée — aucun couplage à l'exécution, un rapport JSON suffit.

## Auteur

**Jérémy Bazan** — Ingénieur QA / Lead Tech QA, spécialisation AI-driven Quality.
ISTQB Foundation v4. Intégration de LLM (Claude, GPT) dans des pipelines QA de
production au sein d'un grand groupe du secteur de l'énergie.

[LinkedIn](https://www.linkedin.com/in/jeremy-bazan/) · [GitHub](https://github.com/BazanJeremy)
