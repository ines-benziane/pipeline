# CLI du pipeline — spécification

*Mise à jour du 21/07/2026, après examen du module `dicom` existant.*

---

## 1. Principe

Deux briques, et tout en découle.

**Les sélecteurs** répondent à *« de quel(s) examen(s) parle-t-on ? »*
**Les commandes** répondent à *« qu'est-ce qu'on en fait ? »*

Les mêmes sélecteurs fonctionnent avec toutes les commandes portant sur des examens. On apprend à désigner un examen **une seule fois**.

**Règle transverse : la CLI ne pose jamais de question.** Aucune saisie interactive, aucune confirmation. Une commande qui attend une réponse humaine ne fonctionne ni en script, ni en traitement par lot, ni derrière une API. Voir ADR-001 D3.

**Outil : `click`.** Le module `dicom` l'utilise déjà — deux bibliothèques d'interface dans un même projet serait incohérent. `@click.group()` gère les sous-commandes.

---

## 2. Sélecteurs

| Sélecteur | Signification | Exemple |
|---|---|---|
| `--name` + `--date` | un patient, une date d'examen | `--name DUPONT --date 2021-05-04` |
| `--name` seul | tous les examens de ce patient | `--name DUPONT` |
| `--exam-id` | un examen précis | `--exam-id 1.2.840...4521` |
| `--related-to` | tous les examens du **même patient** que cet examen | `--related-to 1.2.840...4521` |
| `--file` | une liste d'identifiants dans un CSV ou XLSX | `--file exams.csv` |
| `--dicom-dir` | un dossier DICOM local, hors Télémis | `--dicom-dir /data/lyon/exam_042` |
| `--study` | une cohorte de recherche | `--study DMD_2024` |

**`--related-to`** part d'un `exam_id` et remonte aux antécédents du patient. En interne : `dicom` cherche l'examen, en tire le patient, relance une recherche par patient.

**`--file`** reprend le format déjà utilisé par les scripts `dicom` existants : une colonne d'identifiants, en-tête sur la première ligne, CSV ou XLSX. Même forme, même habitude pour l'utilisateur. C'est la réponse au traitement par lot.

---

## 3. Commandes

### `search` — voir ce qui existe

Liste les examens correspondant au sélecteur. **Ne lance rien.**

```bash
pipeline search --name DUPONT --date 2021-05-04
pipeline search --related-to 1.2.840...4521
pipeline search --file exams.csv
```

```
EXAM_ID              DATE        DESCRIPTION           SEGMENTS      TRAITÉ
1.2.840...1102       2016-11-04  MR CUISSES/JAMBES     legs,thighs   oui
1.2.840...3390       2019-03-12  MR CUISSES/JAMBES     legs          non
1.2.840...4521       2021-05-04  MR CUISSES/JAMBES     legs,thighs   oui
```

La colonne **TRAITÉ** croise Télémis et `data/results/` : elle évite de relancer un calcul déjà fait.

**Doublons de visite.** Une même visite peut exister sous plusieurs `exam_id` (interruption d'acquisition, patient revenu un autre jour). Ces examens sont **signalés visuellement** lorsqu'ils partagent patient et date, mais **jamais regroupés automatiquement** — rien ne permet de prouver qu'il s'agit de la même visite.

```
1.2.840...4521       2021-05-04  MR JAMBES             legs          oui   ⚠ même date
1.2.840...4598       2021-05-04  MR CUISSES            thighs        non   ⚠ même date
```

---

### `run` — lancer un traitement

Résout le sélecteur **et** lance. Commande principale.

```bash
pipeline run --exam-id 1.2.840...4521 --method dixon3pt-t2slice
→ 2 jobs créés : j7f3a1 (legs), j7f3a2 (thighs)
```

**Segments.** Par défaut, `run` traite **tous les segments disponibles** de l'examen, car un rapport complet en a besoin. Un job est créé par segment (granularité ADR-002).

```bash
pipeline run --exam-id X --method M                  # legs + thighs
pipeline run --exam-id X --method M --segment legs   # legs seul
```

**Règle de non-ambiguïté.** Le sélecteur doit désigner un unique examen, sauf intention explicite :

- **un seul examen correspond** → le traitement démarre ;
- **plusieurs correspondent** → rien n'est lancé, la liste s'affiche.

```bash
pipeline run --name DUPONT --method dixon3pt-t2slice

→ 3 examens correspondent. Précise --exam-id :
   1.2.840...1102  2016-11-04
   1.2.840...3390  2019-03-12
   1.2.840...4521  2021-05-04
```

**Sélecteurs explicitement pluriels : `--related-to`, `--file`, `--study`.** La pluralité y est l'intention, pas une ambiguïté. Un job est créé par examen et par segment.

```bash
pipeline run --related-to 1.2.840...4521 --method dixon3pt-t2slice
→ 6 jobs créés (3 examens × 2 segments)

pipeline run --file exams.csv --method dixon3pt-t2slice
→ 84 jobs créés
```

**`--dry-run`.** Affiche ce qui serait fait, sans rien créer. Remplace la confirmation interactive : fonctionne identiquement en CLI, en script et en API.

```bash
pipeline run --related-to X --method M --dry-run
→ 6 jobs seraient créés :
   1.2.840...1102  legs, thighs
   1.2.840...3390  legs
   1.2.840...4521  legs, thighs
```

---

### `fetch` — récupérer et anonymiser, sans traiter

```bash
pipeline fetch --name DUPONT --out /data/cohorte
pipeline fetch --file patients.csv --out /data/cohorte_dmd
pipeline fetch --study DMD_2024 --out /data/cohorte_dmd
```

Aucune méthode exécutée, aucun résultat produit. Sert à constituer une cohorte, ou à récupérer des données pour un traitement ultérieur. L'anonymisation est systématique — elle appartient à `dicom`.

C'est la fonctionnalité couverte aujourd'hui par les deux scripts autonomes du module `dicom`, qu'elle remplacera.

---

### `jobs` — voir les travaux

```bash
pipeline jobs
pipeline jobs --state suspended
pipeline jobs --state failed
```

```
JOB_ID    EXAM              SEGMENT  MÉTHODE            ÉTAT
j7f3a1    1.2.840...4521    legs     dixon3pt-t2slice   completed
j7f3a2    1.2.840...4521    thighs   dixon3pt-t2slice   suspended
j91c4b    1.2.840...3390    legs     dixon3pt-t2slice   failed
```

Le filtrage par état est la vue de travail principale : *« qu'est-ce qui attend ma validation ? »*, *« qu'est-ce qui a échoué ? »*

---

### `status` — détail d'un travail

```bash
pipeline status j7f3a1
```

```
job_id     j7f3a1
état       completed
examen     1.2.840...4521
segment    legs
méthode    dixon3pt-t2slice
résultat   data/results/pat002_20210504_legs_dixon3pt-t2slice_1.0_1.0.json
workdir    workdirs/j7f3a1
```

En cas d'échec, affiche la cause. Le `workdir` est conservé exprès pour permettre l'inspection.

---

### `show-methods` — méthodes disponibles

```bash
pipeline show-methods
```

```
NOM                 VERSION   SEGMENTS
dummy               1.1       legs, thighs
dixon3pt-t2slice    1.0       legs, thighs
```

Sans cette commande, l'utilisateur ne peut pas deviner quoi écrire après `--method`.

---

### `report` — générer le PDF

```bash
pipeline report pat002
pipeline report pat002 --template legs_only --lang en
```

Se compose à partir de **tout ce qui est disponible** dans `data/results/` pour ce patient, antécédents compris. Ne relance aucun traitement.

`--template` désigne un modèle de composition (quelles sections, quelles méthodes) — l'actuel `config.json` transformé en modèles nommés.

---

## 4. Récapitulatif

| Commande | Rôle | Dépend de |
|---|---|---|
| `search` | lister les examens correspondants | API `dicom` |
| `run` | lancer un traitement → job(s) | runner (+ `dicom` pour la récupération) |
| `fetch` | récupérer + anonymiser, sans traiter | API `dicom` |
| `jobs` | lister / filtrer les travaux | persistance |
| `status` | détail d'un travail | persistance |
| `methods` | lister les méthodes | registre |
| `report` | générer un PDF | `medical_report` |
| `validate` | valider un QC suspendu | **interface visuelle — différé** |

---

## 5. Prérequis techniques

### Persistance des jobs

`jobs` et `status` ne peuvent rien afficher tant qu'un job meurt avec le processus. Un stockage simple (un fichier JSON par job dans `data/jobs/`) est le prérequis du noyau.

### Extraction d'une API dans `dicom`

Le module `dicom` expose aujourd'hui deux scripts autonomes dont toute la logique vit à l'intérieur de fonctions décorées `@click.command()`. Elle est donc inappelable depuis le pipeline autrement qu'en lançant un sous-processus et en analysant sa sortie texte — inacceptable.

Les deux scripts font **la même chose** avec une porte d'entrée différente. Noyau commun : construire des critères → interroger Télémis → transférer → pseudonymiser → trier. Ce qui diffère : la source des critères (un CSV de `PatientID` d'un côté, des options CLI de l'autre), un filtre de séries en dur d'un côté, et le parallélisme présent d'un seul côté.

Trois capacités à extraire, retournant des **données** et non de l'affichage :

```python
search(criteria) -> list[ExamInfo]
fetch(criteria, out_dir) -> FetchResult
related_exams(exam_id) -> list[ExamInfo]
```

Les deux scripts actuels deviennent alors deux appels à `fetch` avec des critères construits différemment. Le parallélisme et la pseudonymisation sont écrits une seule fois (aujourd'hui la boucle de pseudonymisation existe en double, avec des gestions d'erreur inégales).

À corriger au passage : adresse IP et port en dur, chemin `output_dir/temp_transit` en dur, liste `BIOMARKERS` en dur (à passer en paramètre).

**Pour l'ADR déploiement :** `dicom` démarre un serveur DICOM en écoute pour recevoir les transferts. Cela implique un port ouvert sur la station, joignable depuis Télémis — à valider avec l'IT.

---

## 6. Bloqué

**`validate`** — valider un QC suppose de regarder des images de segmentation et de juger. Une CLI ne peut pas les afficher ; une validation à l'aveugle serait pire que rien en contexte médical. Attend l'interface visuelle (ADR-001 D4).

---

## 7. Questions ouvertes

1. **`fetch` crée-t-il un job ?** Il ne produit pas de résultat scientifique, mais sur 217 examens on veut savoir lesquels ont échoué. Sans trace, seuls les logs répondent.
2. **`run --dicom-dir`** — traitement de DICOM externes déjà sur disque. Le sélecteur existe, le comportement reste à préciser : comment nommer le résultat sans métadonnées Télémis ?
3. **Filtrage des séries par `dicom`** — le script actuel filtre sur cinq descriptions en dur. Est-ce une optimisation de transfert acceptable (la méthode affine ensuite), ou une fuite de responsabilité métier hors de la méthode ? Touche ADR-002 D5.










# Feuille de route

*État au 21/07/2026. Ordonné par dépendances.*

---

## Fait

| Étape | Livrable |
|---|---|
| Contrat de méthode | `Method` abstraite, `Result`, refus des implémentations incomplètes |
| Objet `Job` | dataclass + machine à états (`JobState`) |
| Registre de méthodes | choix par nom, sans que le cœur connaisse les méthodes |
| Runner | exécution, transitions d'état, gestion d'échec, `workdir` |
| Squelette ambulant | méthode → fichier conforme → `data/results/` → PDF |
| Projet installable | `pyproject.toml`, env conda dédié, dépendances déclarées |
| Tests | 5 tests figeant contrat, registre et transitions |
| ADR-001, ADR-002 | déploiement et accès ; granularité traitement / rapport |
| Spécification CLI | commandes, sélecteurs, règles |

---

## Étape 1 — Persistance des jobs

**Pourquoi maintenant :** c'est le seul prérequis dur du reste. Un job meurt aujourd'hui avec le processus, donc `status` et `jobs` ne peuvent rien afficher, et la forme asynchrone actée en ADR-001 D2 reste théorique.

**Périmètre :** un fichier JSON par job dans `data/jobs/`. Trois fonctions : sauvegarder, charger par identifiant, charger tous. Sérialisation de l'`Enum` et du `Path`.

**Ne pas faire :** SQLite, transactions, index. Le format de stockage est un détail derrière ces trois fonctions — il se remplacera sans toucher au reste.

**Estimation :** 1 h
**Bloque :** `status`, `jobs`, et tout le reste de la CLI

---

## Étape 2 — Noyau de la CLI

**Périmètre :** package `cli/` (adaptateur primaire, seul autorisé à importer `methods/`), avec `click` en `@click.group()`. Commandes `run`, `status`, `jobs`, `methods`.

À ce stade `run` ne branche pas `dicom` : l'`exam_id` est transmis tel quel, comme aujourd'hui.

**Livrable démontrable :** je soumets un traitement, je ferme le terminal, je consulte son état. C'est la preuve que l'asynchrone fonctionne.

**Estimation :** 2 h 30
**Dépend de :** étape 1

---

## Étape 3 — Commande `report`

**Périmètre :** appeler `medical_report` proprement depuis la CLI, au lieu de `python -m interface.orchestrator` depuis un dossier précis. Transformer `config.json` en modèles nommés (`--template`).

**Sous-tâche :** déclarer `medical_report` comme package dans `pyproject.toml`, ce qui supprimera la dépendance au répertoire de lancement et le `sys.path.insert` existant.

**Estimation :** 2 h
**Dépend de :** étape 2

---

## Étape 4 — Extraction d'une API dans `dicom`

**Pourquoi :** toute la logique vit dans des fonctions `@click.command()`, donc inappelable depuis le pipeline. C'est le blocage qui empêche `search`, `fetch`, et le branchement réel de `run`.

**Périmètre :**
- extraire `search()`, `fetch()`, `related_exams()` retournant des données, pas de l'affichage ;
- fusionner les deux scripts existants en un seul chemin (ils font la même chose avec des entrées différentes) ;
- sortir du code : IP, port, chemin temporaire, liste `BIOMARKERS` → configuration ;
- écrire la pseudonymisation une seule fois, en gardant la version la plus robuste des deux.

**Livrable démontrable :** `pipeline search --name X` interroge réellement Télémis.

**Estimation :** une demi-journée à une journée
**Dépend de :** rien techniquement — peut se faire en parallèle des étapes 1-3

---

## Étape 5 — Branchement complet de `run`

**Périmètre :** `run` récupère réellement les DICOM via `dicom` avant d'appeler la méthode. Le trou actuel (on passe un `exam_id` là où le contrat attend un `source_dir`) se referme.

**Estimation :** 2 h
**Dépend de :** étapes 2 et 4

---

## Étape 6 — Migration de mutools

**Pourquoi c'est ici et pas avant :** rien de tout ce qui précède n'en dépend. La dummy suffit à valider la plomberie. Et il vaut mieux migrer dans une architecture stabilisée.

**Périmètre :** extraire les fonctions de calcul (`bdixon3pt` et consorts) de leur plomberie — CLI, chargeur YAML, `batch.yml`. Les envelopper dans une vraie méthode signant le contrat.

**Critère de réussite :** l'algorithme extrait tourne sans qu'aucun `batch.yml` n'existe nulle part.

**Point à traiter :** la méthode doit identifier ses rôles de séries à partir des en-têtes DICOM, sans numéros fournis de l'extérieur.

**Estimation :** plusieurs jours
**Dépend de :** étape 5

---

## Étape 7 — Base de données

**Pourquoi ici :** l'index par nom de fichier fonctionne et suffit à valider l'architecture. Le remplacer plus tôt serait de l'optimisation prématurée.

**Périmètre :** remplacer la découverte par balayage de dossier par des requêtes. Ne touche qu'une couche : la lecture côté `medical_report`, et la persistance des jobs.

**Questions à trancher d'abord (notes du 9 juillet, non résolues) :** plusieurs bases possibles ? Que stocke-t-on en base et que laisse-t-on sur le système de fichiers ? Les JSON de résultats pèsent plusieurs Mo avec les polygones.

**Dépend de :** étape 5

---

## Étape 8 — Service et interface visuelle

**Pourquoi c'est le dernier et pourquoi c'est inévitable :** la validation du QC n'a pas de forme en ligne de commande. Sans interface, tout job suspendu est bloqué définitivement. C'est aussi la seule voie d'accès pour des médecins et des sites partenaires (ADR-001 D4).

**Périmètre :** un service exposant une API sur la station, un client visuel, l'affichage des overviews de QC et le recueil de la validation.

**Prérequis à valider avec l'IT :** processus permanent autorisé, coordination sur la charge (machine partagée), dépendances système de WeasyPrint, port DICOM ouvert.

**Dépend de :** étapes 1 à 7

---

## Ordre visuel des dépendances

```
1. Persistance ──> 2. CLI noyau ──> 3. report
                        │
4. API dicom ───────────┴──> 5. run complet ──> 6. mutools
                                     │
                                     └────────> 7. base de données
                                                      │
                                                      v
                                          8. service + interface QC
```

L'étape 4 est la seule qui peut se mener en parallèle. Tout le reste est séquentiel.

---

## Points de vigilance transverses

- **Portabilité** — `pathlib` partout, attention à la casse des noms sous Linux.
- **Rien en dur** — chemins, adresses, ports viennent de la configuration. Deux violations connues à ce jour : `WORKDIR_ROOT` et `RESULTS_DIR` dans le runner (isolées en constantes, acceptable pour l'instant), et l'IP/port dans `dicom`.
- **Le cœur ne parle pas** — pas de `print`, pas d'`input()` dans `runner/`. L'affichage appartient aux adaptateurs.
- **Provenance en triple** — nom de fichier, bloc `metadata`, champ `provenance`. À rationaliser lors de l'étape 7.
- **Fragilité du nommage** — l'index par `split("_")` casse si un champ contient un underscore. Disparaît à l'étape 7.