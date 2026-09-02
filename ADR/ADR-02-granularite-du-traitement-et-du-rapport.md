# ADR-002 — Granularité du traitement et du rapport

**Statut :** accepté
**Version :** 2
**Date :** 2026-07-21 (révisé 2026-09-02)
**Contexte projet :** pipeline IRM, milestone M1 (squelette ambulant)

> **Révision 2026-09-02 (D3) :** le dossier partagé de résultats passe de `data/results/`
> (racine du projet) à `workdirs/results/`. Voir §2 D3 et §6.

---

## 1. Contexte

Jusqu'à cette décision, l'architecture était décrite comme une chaîne linéaire :

```
dicom → méthode → medical_report
```

Le câblage de bout en bout du squelette ambulant a montré que **ce schéma est faux**. `medical_report` ne travaille pas à la même granularité que les briques amont :

- Son point d'entrée prend un **patient** et un **dossier**, pas un fichier ni un examen.
- Son fichier de configuration déclare plusieurs **sections** (segment × méthode × biomarqueur). Un rapport complet requiert donc plusieurs fichiers de résultats.
- Sa fonction `find_antecedents` recherche les examens **antérieurs** du même patient pour le suivi longitudinal — donc des résultats produits lors d'exécutions passées, potentiellement des mois plus tôt.

Le rapport n'est donc pas la troisième étape d'un traitement : c'est une opération distincte, portant sur un ensemble de résultats accumulés dans le temps.

Cette lecture est cohérente avec les notes de réunion du 9 juillet : *« je veux générer un report avec les jambes du 1er examen et les cuisses du second »*, et *« il faut prévoir des mécanismes pour agréger les résultats quantitatifs »*.

---

## 2. Décision

### D1 — Deux opérations de granularités différentes

| Opération | Unité | Entrée | Sortie |
|---|---|---|---|
| **Traitement** | 1 examen × 1 segment × 1 méthode | DICOM | 1 fichier de résultats |
| **Rapport** | 1 patient | N fichiers de résultats | 1 PDF |

Un traitement produit **exactement un** fichier de résultats. Un rapport en consomme **plusieurs**, éventuellement issus d'examens et de dates différents.

### D2 — Le couplage se fait par la donnée, pas par le code

Les deux opérations ne se connaissent pas. Elles se rencontrent en un seul point : un **dossier partagé de résultats**, dont le contenu est indexé par une **convention de nommage**.

```
workdirs/results/{patient_id}_{exam_date}_{segment}_{method}_{version}_{acquisition}.json
```

Le nom de fichier n'est pas décoratif : il est l'index. C'est lui qui permet à `medical_report` de découvrir les résultats disponibles et de retrouver les antécédents d'un patient sans base de données.

**Conséquence :** le nom de fichier doit être construit **à partir des métadonnées du contenu**, et jamais fourni de l'extérieur. C'est la seule garantie que nom et contenu ne divergent pas.

### D3 — Le dossier de résultats n'appartient à aucune brique

Le dossier partagé est situé dans la zone interne du runner (`workdirs/results/`), et non à l'intérieur de `medical_report/` où il se trouvait historiquement.

**Principe :** une donnée partagée par deux briques ne vit chez aucune des deux. Placer le dossier chez le consommateur créerait une dépendance implicite des producteurs vers `medical_report`.

**Révision 2026-09-02 :** initialement à la racine (`data/results/`). Consolidé sous `workdirs/` pour ne garder que trois emplacements sur disque : `source_dir` (DICOM en entrée), `workdirs/` (tout l'interne serveur, non exposé à l'utilisateur — traces par job, données de reprise, pool de résultats JSON), et `output_dir` (livrables destinés à l'utilisateur : PDF et fichiers QC). Le pool de résultats reste un dossier *cross-job* stable — il ne peut pas vivre dans `workdirs/<job_id>/` puisque le rapport agrège plusieurs examens — d'où `workdirs/results/` à plat.

### D4 — Deux commandes distinctes dans l'interface

La séparation des granularités impose deux points d'entrée utilisateur distincts :

- une commande de **traitement**, qui prend un examen, un segment et une méthode, et rend un identifiant de travail ;
- une commande de **rapport**, qui prend un patient et compose à partir de ce qui est disponible.

Il n'existe pas de commande unique « de bout en bout ». Un utilisateur qui veut un rapport complet lance plusieurs traitements, puis un rapport.

### D5 — Le contrat de méthode inclut le segment

Un même examen contient plusieurs régions anatomiques (jambes, cuisses). La méthode **ne peut pas** déduire laquelle traiter : c'est une instruction de l'utilisateur, pas une propriété des données.

En conséquence, la signature du contrat devient `run(source_dir, workdir, segment)`, et l'objet `Job` porte un champ `segment`.

> *Nuance importante :* la méthode reste autonome pour identifier les **rôles de séries** (quelles séries sont les Dixon, quelles séries sont les msme) — cette information est déductible des en-têtes DICOM. Elle ne l'est pas pour la région anatomique demandée.

---

## 3. Conséquences

### Positives

- Les deux opérations évoluent indépendamment. Modifier la composition d'un rapport n'affecte aucune méthode.
- Un rapport peut combiner des résultats produits à des dates différentes, sans retraitement — c'est ce qui rend possible le suivi longitudinal et la composition à la carte.
- Un traitement qui échoue n'invalide que son propre fichier ; les autres restent utilisables.
- Le remplacement futur de la découverte par fichiers par une base de données ne touchera qu'une seule couche (la lecture côté rapport), sans impacter le contrat de méthode ni le runner.

### Contraintes

- **Rien ne garantit mécaniquement** qu'un fichier produit par une méthode soit conforme au schéma attendu par `medical_report`. Le couplage étant par la donnée, la validation doit être assurée par un test qui vérifie la sortie d'une méthode contre le modèle de données (`Exam`).
- La convention de nommage repose sur un découpage par `_`. Un champ contenant ce caractère casserait l'index. À surveiller, et à supprimer lors du passage en base.
- L'information de provenance existe actuellement **en triple** : dans le nom du fichier, dans le bloc `metadata` du contenu, et dans le champ `provenance` du résultat. Redondance assumée à ce stade, à rationaliser ultérieurement.

### Différé

- **Composition fine du rapport** — la sélection explicite de résultats individuels (*« ce résultat cuisse de telle date, cet antécédent de telle autre »*) évoquée dans les notes du 9 juillet. À ce stade, le rapport est composé par un modèle nommé.
- **Notion de lot** — le regroupement de N traitements soumis ensemble (mode recherche, QC par lot). Pas nécessaire tant que les traitements sont soumis un à un.
- **Remplacement de l'index fichier par une base de données.**

---

## 4. Alternatives écartées

**Chaîne linéaire unique (`dicom → méthode → medical_report` en une opération).** C'était le modèle initial. Écarté parce qu'il est incapable de produire un rapport multi-sections ou d'intégrer des antécédents : il faudrait retraiter tous les examens à chaque rapport.

**Dossier de résultats à l'intérieur de `medical_report/`.** État historique. Écarté : les méthodes écriraient dans le territoire d'une autre brique, créant une dépendance qui contredit l'architecture hexagonale.

**Passage direct du résultat en mémoire de la méthode au générateur de rapport.** Écarté : rendrait impossible le suivi longitudinal (les antécédents ne sont pas en mémoire), et couplerait les deux briques.

---

## 5. Références

- Notes de réunion du 9 juillet 2026 — agrégation des résultats, composition à la carte
- Design doc pipeline IRM v2, §5 (architecture hexagonale)
- ADR-001 — Déploiement et mode d'accès utilisateur (décision D2, échanges asynchrones)

---

## 6. Révisions

### 2026-09-02 — Consolidation des emplacements disque (D3)

Le dossier partagé de résultats passe de `data/results/` à `workdirs/results/`, et le dossier `data/` est supprimé. Objectif : réduire la dispersion à trois emplacements seulement.

| Emplacement | Rôle | Exposé utilisateur |
|---|---|---|
| `source_dir` | DICOM en entrée | — |
| `workdirs/` | interne serveur : `workdirs/jobs/` (fiches job), `workdirs/<job_id>/` (traces, `run.log`, `crash/`, données de reprise), `workdirs/results/` (pool de résultats JSON) | non |
| `output_dir` | livrables : PDF, `<job_id>/` de fichiers QC | oui |

La décision D2 (couplage par la donnée via convention de nommage) et le principe D3 (la donnée partagée ne vit chez aucune brique) sont inchangés ; seul le chemin bouge. Le pool reste un dossier *cross-job* à plat car le rapport agrège plusieurs examens.

Impact code : `RESULT_DIR` dans `runner/job_runner.py` ; `runner/job_store.py` (`JOBS_DIR = workdirs/jobs`). `--output-dir` est requis sur `process` **et** `resume`, donc les fichiers QC vont dans `<output_dir>/<job_id>/` dans les deux cas. `adapters/file_result_index.py` et `runner/pipeline.py` importent `RESULT_DIR` et suivent automatiquement.