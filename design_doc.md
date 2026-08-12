# INSTITUT DE MYOLOGIE

Pipeline IRM — Architecture logicielle  
Design Document

# Pipeline de traitement IRM

**PACS → Rapport médical**

| | |
|---|---|
| **Statut** | Draft (v2) |
| **Auteur** | Inès Benziane |
| **Relecteur** | Pierre-Yves Baudin |
| **Créé le** | 2026-06-16 |
| **Dernière maj** | 2026-07-09 |

---

## Table des matières

- 1. Context & background
- 2. Goals
- 3. Non-goals
- 4. User stories
  - Must (la v1)
  - Should
  - Could
  - Won't
- 5. Design principles
- 6. Proposed design — vue d'ensemble
- 7. Detailed design
  - 7.1 Runner interne (coordination)
  - 7.2 Anatomie d'un stage (hexagonal)
  - 7.3 Brique de calcul (migration `mutools`)
  - 7.4 Intégration de la segmentation (frontière asynchrone)
  - 7.5 Contrôle qualité (QC gate)
  - 7.6 Génération du rapport
  - 7.7 Contrats de données et provenance
    - Contrats par couture
    - Structure du manifest (un fichier JSON par étude)
- 8. Alternatives considered
- 9. Security & privacy
- 10. Testing strategy
- 11. Deployment & operations
- 12. Rollout / milestones
- 13. Open questions

---

## 1. Context & background

L'outil dispose aujourd'hui de quatre briques logicielles disjointes, sans chaînage commun :

- `dicom` — recherche, récupération et anonymisation/pseudonymisation de fichiers DICOM.
- `mutools` — algorithmes (et leur plomberie) produisant les cartographies (un type par biomarqueur : T2, FF, etc.) à partir des DICOM → artefact work/.
- Segmentation automatique — exécutée sur une station de calcul distante ; code externe, maintenu par Louis. Reçoit work/, produit les masques de muscles (roi_museg/).
- `medical_report` — contient get_result (lit work/ + roi_museg/, produit les fichiers JSON json_output/) et section_generator (lit json_output/, génère le rapport PDF). get_result est un bout d'algo de mutools à extraire (voir §7.3).

Chaque brique fonctionne isolément, avec une plomberie manuelle, peu de contrôle qualité intégré et une traçabilité limitée. L'objectif de ce document est de définir l'architecture d'un système unifié, fiable, reproductible et débogable, qui chaîne ces briques tout en permettant de n'en exécuter qu'une partie.

Politique de dépendances : tout est écrit en interne (pas de framework de workflow externe = pas de mises à jour subies).

## 2. Goals

- Décorréler complètement le pipeline des méthodes. Le pipeline ignore tout des algorithmes mutools et de la segmentation, il ne considère à présent que 3 briques : dicom, methods, medical_report (voir paragraphe concerné).
- Permettre l'exécution partielle : entrer dans le pipeline à partir de dicoms déjà acquis, ou à partir des résultats de get_results pour générer le report.

| Ce qu'on a déjà | Ce qu'on saute | Ce qu'on lance |
|---|---|---|
| rien | — | dicom → mutools.dixon + mutools.t2 → segmentation → get_result → medical_report |
| DICOMs | dicom | methods → medical_report |
| Les résultats (from json or DB) | Dicom and methods | medical_report |

- Garantir la reproductibilité : tout résultat est rattachable à une méthode, une version et des algos connus.
- Rendre les runs débogables : logs structurés et données intermédiaires inspectables à chaque étape, sur demande.
- Intégrer un contrôle qualité adapté au mode d'usage (lot vs quelques patients) : un rapport de QC est généré systématiquement ; son caractère bloquant dépend du contexte.
- Garantir la comparabilité longitudinale de façon explicite : chaque méthode porte les critères qui déterminent si deux examens sont comparables.
- Valider les méthodes de façon reproductible : chaque méthode dispose de données de référence rejouées à chaque changement.
- Permettre de réintégrer les informations du patient de manière cadrée lors de la génération du compte-rendu.
- Respecter les Good Clinical Practices : audit trail, garantie sur les méthodes, mesures prise pour vérifier que l'on fait bien ce que l'on veut et croit faire. Traçabilité sur les interventions automatiques et manuelles. Enregistrement des changements de paramètres.
- Offrir une interface en ligne de commande claire et prédéfinie.

## 3. Non-goals

- Flexibilité maximale de paramétrage : on privilégie un jeu de méthodes prédéfinies à paramètres figés plutôt qu'un paramétrage libre.
- Appliquer le pipeline à des données traitées ultérieurement : tout ce qui est utilisé par le pipeline est généré par le pipeline (hors segmentation manuelle).
- Reprise en cours de route en cas d'échec : si ça plante on recommence de zéro.
- Conserver les artéfacts systématiquement : on ne les conserve que dans une approche de débogage ou aux points de suspensions (segmentation auto, QC gate).
- Indexer le pipeline sur le patient : le pseudo du patient n'est pas une clé interne. Le pipeline s'articule autour de l'examen ; l'association examen <-> patient est traitée via une requête Télémis.

## 4. User stories

### Must (la v1)

- En tant qu'utilisateur, le pipeline s'enchaîne automatiquement jusqu'à la cible demandée sans intervention manuelle entre les étapes, hors QC et hors segmentation manuelle.
- En tant qu'utilisateur, je peux lancer le traitement sur un lot d'études.
- En tant qu'utilisateur, je peux exécuter le pipeline complet sur une étude.
- En tant qu'utilisateur, je peux exécuter dicom seul pour récupérer et anonymiser des DICOM, afin d'y appliquer ensuite mes propres calculs.
- En tant qu'utilisateur, je peux exécuter le pipeline à partir de DICOM déjà anonymisés que je possède.
- En tant qu'utilisateur, je peux générer un rapport médical à partir de données déjà traitées, sans rejouer les étapes en amont.
- En tant qu'utilisateur, je peux substituer la segmentation automatique par une segmentation manuelle (en fournissant mes propres masques) et lancer le pipeline depuis ce point ; cette substitution implique un point de suspension.
- En tant qu'ingénieure, je peux déboguer un run échoué en inspectant les données intermédiaires et les logs de chaque étape.
- En tant que chercheur, je peux choisir une méthode de calcul dans une liste prédéfinie (paramètres figés) pour produire les cartographies.

### Should

L'architecture v1 est conçue pour accueillir modes, rôles et QC ; leur implémentation est déférée.

- Modes d'usage (définis il y a qqs mois — déterminent le traitement des identifiants) :
  - RESEARCH — anonymisation irréversible ; pseudonyme à usage unique, l'ID n'importe pas.
  - CLINICS — pseudonymisation ; ID unique par patient + table pseudo↔patient ; centré patient ; rapport médical.
  - STUDY — pseudonymisation ; ID défini par l'étude ; centré cohorte.
- En tant qu'utilisateur, un QC report (image de synthèse + paramètres clés + flags) est généré systématiquement pour chaque exam, que je choisisse ou non de le consulter, ou que cela me soit imposer (voir §7.5).
- En tant qu'utilisateur en mode recherche, je bénéficie d'un QC advisory (fail-open) : les artéfacts de QC sont produits mais le pipeline s'exécute quand même, et je peux les consulter à ma convenance.
- En tant qu'utilisateur en cadre d'essai clinique, je bénéficie d'un QC bloquant (fail-closed) : le run se met en pause à chaque gate et attend un sign-off humain avant de poursuivre.
- En tant qu'utilisateur d'un lot, je dispose d'un QC par lot : un tableau agrège les rapports par étude et fait remonter les flags, pour un parcours en un coup d'œil.
- En tant qu'ingénieur, je dispose pour chaque méthode d'un jeu de données de référence que je peux rejouer afin de détecter les dérives et de documenter la validation de méthode (voir §10).
- En tant qu'ingénieur, j'ai accès aux audit_logs : manifest + fichier audit_log.json — qui accumule tous les runs sans écraser.
- Mettre en place un server (queue non bloquante)

### Could

- En tant qu'utilisateur, je dispose d'une interface graphique au-dessus de la CLI.
- En tant qu'utilisateur, je peux lancer un "dry run" pour afficher le plan d'exécution sans l'exécuter, pour indiquer ce que l'on fait et ce que l'on saute lors de l'exécution du pipeline et modifier si besoin.

### Won't

- En tant qu'utilisateur, je ne peux pas appliquer le pipeline à des données qu'il n'a pas générées (hors segmentation manuelle).

## 5. Design principles

- **Stages composables** : chaque brique est une unité indépendante, avec un contrat d'entrée/sortie explicite.
- **Hexagonal par stage** : logique métier au cœur, isolée de l'I/O par des ports et adapters. État actuel : medical_report dispose déjà des fondations (ports reader/writer, domain models Pydantic) ; dicom et la couche de génération PDF de medical_report seront refactorisés pour atteindre cet objectif.
- **Fail fast** : chaque stage valide son entrée contre un schéma et refuse bruyamment toute donnée invalide.
- **Reproductibilité d'abord** : méthodes à paramètres figés, provenance tracée.
- **Persistance éphémère par défaut** : en fonctionnement nominal, les artéfacts intermédiaires ne sont pas conservés. La persistance sur disque est activée en mode débug, ou aux points de suspension délibérés qui doivent persister leur artefact-frontière (voir §7.1)
- **Suspension délibérée is not reprise après échec** : un checkpoint planifié (QC gate, segmentation manuelle) suspend proprement le run et persiste sa frontière ; un échec, lui, repart de zéro.
- **Politique attachée à la méthode** : une méthode transporte, en plus de son algorithme et de sa version, ses critères de comparabilité et ses données de référence.
- **Stockage abstrait (location transparency)** : les briques accèdent aux données via une interface de stockage, sans connaître l'emplacement réel (mémoire, disque local, stockage ou réseau partagé). L'emplacement est un adapter configurable.
- **Différer les décisions d'infra** : les coutures permettent d'ajouter un serveur plus tard sans toucher au cœur.

## 6. Proposed design — vue d'ensemble

L'utilisateur lance une commande en précisant sa cible (ex. : "je veux le rapport médical de cette étude"). Le système traite l'étude du début à la fin en une seule passe, sans intervention manuelle entre les étapes (hors QC humain et segmentation manuelle). Traitement par lot (batch) : les données arrivent en unités discrètes (une acquisition = une étude), les calculs sont lourds, et l'on veut pouvoir rejouer n'importe quelle étude de façon déterministe.

L'outil est installé localement par chaque utilisateur ; chaque utilisateur travaille sur ses propres données en local, sans coordination nécessaire entre machines. En v1, l'exécution est locale et bloquante, un mode server (queue non bloquante) est différé (voir §11). Le pipeline est indexé sur l'examen (patient_id sur Télémis = exam_id dans le code et dans l'esprit)

- ① Récupération DICOM : en une commande, l'utilisateur indique le degré de pseudo/ano et les series demandées.
- ② Calcul des cartographies : mutools exécute un algorithme par biomarqueur. Ces étapes sont indépendantes entre elles — les cartographies Dixon/FF et les cartographies T2 peuvent être calculées dans n'importe quel ordre. Les sorties ne sont pas persistance (hors debug) et sont passées au stage suivant
- ③ Segmentation : la station distante segmente les muscles à partir des séries Dixon/VIBE uniquement (dixon_mag/ actuellement, quelle nouvelle sortie à déterminer). Elle produit les masques partagés (roi_museg/), utilisés ensuite par tous les biomarqueurs. Elle ne peut démarrer qu'une fois les cartographies Dixon disponibles. (Possible sur T2 si on a que ça mais pas top)
- ④ Extraction des résultats (get_result) : combine les cartographies de chaque biomarqueur avec les masques de segmentation pour produire les fichiers JSON.
- ⑤ Rapport : medical_report lit l'ensemble des fichiers JSON et génère un seul rapport PDF.

## 7. Detailed design

### 7.1 Runner interne (coordination)

- **Séquence linéaire ordonnée.** Le pipeline est une séquence ordonnée d'étapes (dicom -> mutools -> segmentation -> get_resullt -> medical_report). Les seules étapes mutuellement indépendantes (mutools.dixon et mutools.t2) sont exécutées séquentiellement en v1, sans parallélise local.
- **Résolution par cible.** Pour un output demandé, le runner découpe cette séquence entre le point d'entrée disponible et la cible et exécute les étapes du segment retenu. Cette même résoltuion sert aussi à reprendre après un point de suspension : « reprendre depuis l'artéfact-frontière jusqu'à la cible » est une cible comme une autre.
- **Points de suspension délibérés.** Un point de suspension arrête proprement le run à un checkpoint, persiste son artefact frontière et sort avec un statut explicite (ex. awaiting_qc). Une invocation ultérieure reprend via la résolution par cible. Aucune machinerie de checkpoint/resume n'est requise : la QC gate (fail-closed) et la segmentation manuelle partage ce même mécanisme.
- **Politique de persistance**
  - Nominal : les artéfacts intermédiaires sont éphémères : produits en mémoire (array produits par les algorithmes) ou sur disque (local ou partagé, pour les DICOM et les artéfacts-frontière). Les artéfacts-frontière (sauf Dicom) sont supprimés après atteinte de la cible.
  - Débug : les artéfacts intermédiaires sont persistés pour inspection, dans un emplacement explorable et identifiable (manifest à côté, chemin lisible par le développeur).
  - Points de suspension : l'artefact-frontière est persisté pour permettre la reprise (QC-gate en fail-closed, segmentation manuelle).
  - Support par couture : Les coutures internes (entre nos briques) transitent en mémoire ; les coutures qui touchent l'extérieur (DICOM, segmentation) sont matérialisées dans un fichier. En v1 ce fichier est sur le disque local et plus tard on ajoute RMN files.
- **Détection de péremption.** Deux cas concrets à couvrir :
  - Relance sur étude déjà traitée. On relance depuis le début (sauf récupération des DICOM) : les artéfacts n'étant pas conservés (voir Non-goals), la reprise du début est obligée.
  - Cohérence longitudinale. Un patient a deux examens à des dates différentes. Il existe toute une nuance entre « aucun changement » et « changement complet » : de petits changements sont insignifiants et considérés comme comparables, mais modifier par exemple les temps d'écho peut avoir un impact majeur sur le T2 mesuré.
  - Critères de comparabilité attachés à la méthode. À chaque méthode est attaché un ensemble de critères définissant une marge de manœuvre qui valide (ou non) la comparaison : si le critère A1 change, la comparaison reste valide ; si B2 change, elle ne l'est plus. Lorsqu'un algorithme est défini, un fichier associé fige son numéro de version et ses critères.
- **Manifest étendu.** La notion de manifest est étendue aux paramètres de processing, et non plus seulement d'acquisition : pour chaque stage complété, il enregistre les composantes qui définissent ce qui a été calculé — méthode, paramètres, version du package, critères de comparabilité, et taille/date de modification des fichiers d'entrée (ex. : métadonnées spécifiques à la méthode en sortie de T2 mapping, idem après la segmentation). Cela sert deux usages : au run suivant, le runner compare ces champs à l'état actuel — si tout correspond, il saute l'étape, sinon il relance ; et la comparaison longitudinale devient une comparaison de manifests, évaluée contre les critères de la méthode.
- **Idempotence.** Lancer la même étape deux fois avec les mêmes inputs donne le même résultat, sans effet de bord.
- **Logs structurés.** Chaque ligne de log porte : run_id (identifiant unique du run), stage (l'étape en cours), exam_id (l'étude traitée), level (INFO / WARNING / ERROR) et msg (le message ou l'erreur).
- **Audit.** Le manifest par étude constitue la trace d'audit principale : il enregistre pour chaque stage la méthode, la version, les paramètres, le statut et les timestamps. Ce qu'il ne couvre pas : l'historique des relances (un retraitement écrase le manifest précédent). Un fichier audit_log.jsonl append-only par étude — qui accumule tous les runs sans écraser — sera implémenté ultérieurement (Should).
- **Gestion d'échec.** Arrêt sur erreur avec message clair. Pour l'étape de segmentation (station distante), le runner réessaie automatiquement en cas de non-réponse, en espaçant les tentatives.

### 7.2 Anatomie d'un stage (hexagonal)

Chaque stage suit le même squelette :

- Valider l'entrée contre le contrat (fail fast).
- Exécuter la logique métier (cœur sans I/O).
- Valider la sortie contre le contrat (fail fast)
- Générer le QC report s'il y en a un (§7.5)
- Passer la QC gate s'il y en a une (§7.5) — bloquante selon la politique du mode.
- Écrire la sortie ; mettre à jour le manifest.

La validation de contrat répond à « la donnée est-elle bien formée ? » (shape, type, absence de NaN, présence des séries/masques) : elle est binaire, toujours exécutée, et fait partie du stage. Le contrôle qualité répond à « la donnée est-elle plausible / de bonne qualité ? » : il n'existe qu'à certaines coutures et relève de §7.5.

### 7.3 Brique de calcul (migration `mutools`)

Stratégie : On reprend les algorithmes de `mutools` et on réécrit la plomberie. La brique est décomposée en sous-étapes inspectables.

Registre de méthodes. Catalogue nom → (algorithme, paramètres figés, version, critères de comparabilité, données de référence).

L'utilisateur choisit une méthode par son nom ; pas de paramètres libres. Une variation d'algorithme = une nouvelle méthode nommée. La méthode utilisée est inscrite dans le manifest et le rapport. Ce même pattern de registre s'applique aux checks de QC (voir §7.5) : ajouter un check revient à enregistrer une entrée, sans toucher au runner.

### 7.4 Intégration de la segmentation (frontière asynchrone)

La station de segmentation est distante et n'est pas notre code : elle est traitée comme un service externe via un adapter dédié.

- **Pattern** : submit → poll → fetch.
- **Anti-race-condition** : Comment ne pas lire un résultat en cours d'écriture ? (Éviter : la seg crée roi_museg mais n'a pas fini d'écrire dessus et le runner voit roi_museg et le lit) (rename au bon moment ? nécessite une implémentation supp de museg-ai)
- **Robustesse** : retries avec backoff, timeout, comportement en cas de déconnexion.
- **Contrat à formaliser** : format/emplacement d'entrée, format/emplacement de sortie, signal de fin, comportement en cas d'échec.

Régime local (alternative). Si le pipeline s'exécute directement sur la station de calcul, la segmentation peut être appelée comme une librairie locale (museg-ai), ce qui supprime la frontière asynchrone. L'adapter permet de basculer entre régime distant (service externe) et régime local (librairie) sans toucher au cœur.

### 7.5 Contrôle qualité (QC gate)

Le QC se compose de deux responsabilités séparées — produire un report et tenir une gate — dont le caractère bloquant dépend du mode d'usage. La validation de contrat (schéma, fail-fast) n'en fait pas partie : elle est structurelle et vit dans le stage (§7.2).

Le QC intervient à deux coutures : après mutools et après la segmentation.

Report — l'artefact que l'utilisateur consulte, de nature différente selon la couture :

- Après mutools : un PNG de synthèse, pour repérer d'un coup d'œil une inversion eau/graisse.
- Après la segmentation : un stack scrollable (défilement coupe par coupe avec overlay, façon RadiAnt), pour juger visuellement les masques sur les 64 slices.

En produisant le report, le pipeline passe aussi quelques contrôles automatiques (valeurs hors plage, masque vide…) et signale ce qui paraît suspect. Ces contrôles ne font que lever des alertes : ils orientent le regard, sans jamais conclure si une segmentation est correcte — cette appréciation demande un œil humain.

Gate — le point où l'on décide, à partir du report, si le run continue, se met en pause ou s'arrête. Le comportement dépend du mode :

- Recherche (fail-open) : la gate laisse passer automatiquement. Le report reste consultable, mais le run n'attend rien ; le contrôle est indicatif.
- Clinique / essai (fail-closed) : à chaque couture, le run se met en pause et présente le report ; un utilisateur doit approuver ou rejeter avant de poursuivre. L'approbation relance le run là où il s'était arrêté ; le rejet l'arrête (marqué qc_failed). Cette validation — qui, quand, verdict — est enregistrée pour l'audit.

Le rejet est donc une décision humaine. Les problèmes purement mécaniques (masque vide, série absente, valeurs manquantes) ne relèvent pas de la gate : ce sont des données mal formées, refusées bien plus tôt par la validation de contrat (§7.2). Autrement dit : les contrôles automatiques signalent et l'humain tranche.

**Sévérité → comportement**

| Verdict | RESEARCH (fail-open) | CLINICS / STUDY (fail-closed) |
|---|---|---|
| PASS | continue | continue |
| WARN | log + continue | pause → sign-off humain requis |
| FAIL | log (arrêt optionnel) | arrêt, run marqué qc_failed |

**QC par lot**

Quand on traite un lot, on ne consulte pas les reports un par un : ils sont regroupés dans un tableau récapitulatif — une ligne par étude, l'état de chaque point de contrôle et une vignette d'aperçu — où les études à vérifier ou rejetées remontent en tête. On parcourt ainsi le lot entier d'un coup d'œil et on n'ouvre en détail que les études qui posent problème. Le QC par lot n'est pas obligatoire en recherche, mais doit rester possible.

**Provenance et accès aux originaux**

Le report, son résultat et l'éventuelle validation humaine sont référencés dans le manifest ; en clinique / essai, la validation est aussi ajoutée à l'audit_log. L'accès aux fichiers originaux, utile dans de rares cas particuliers, reste possible mais relève du mode debug — il n'est jamais nécessaire pour un QC normal.

### 7.6 Génération du rapport

medical_report lit les fichiers JSON produits par get_result et génère le rapport PDF de façon déterministe (mêmes données en entrée → même PDF en sortie).

La brique ne va pas chercher elle-même les fichiers à un emplacement fixe : les données d'entrée et la destination du PDF lui sont fournies de l'extérieur (via des ports). Elle peut ainsi être exécutée seule sur des données déjà traitées, et testée en isolation.

### 7.7 Contrats de données et provenance

Un contrat de couture décrit ce qui passe d'une brique à la suivante : la donnée échangée, sa forme, et le support par lequel elle transite.

Le support indiqué est celui du fonctionnement normal. En mode debug, toute couture interne est en plus matérialisée sur disque local pour inspection — cette règle vaut partout et n'est pas répétée ligne par ligne.

#### Contrats par couture

| # | Producteur | Consommateur | Donnée logique | Forme | Support |
|---|---|---|---|---|---|
| 1 | dicom | mutools.dixon + mutools.t2 | Séries DICOM (par série) | fichiers .dcm | fichier — disque local (v1) |
| 2 | mutools.dixon | segmentation | Carte magnitude VIBE | fichier imposé par la station (à confirmer, §13) | fichier — disque local (v1) |
| 3 | mutools.dixon | mutools.get_result | Cartes Dixon (dixon3pt, roi_dixon) | ndarray | mémoire |
| 4 | mutools.t2 | mutools.get_result | Carte T2 (t2map) | ndarray | mémoire |
| 5 | segmentation | mutools.get_result | Masque de segmentation (roi_museg) | fichier produit par la station (à confirmer, §13) | fichier — disque local (v1) |
| 6 | get_result | medical_report | Résultats par muscle | JSON | Disque et DB |

Deux types de coutures. Les coutures internes (entre nos briques) transitent en mémoire. Les coutures qui touchent l'extérieur — l'entrée DICOM et la segmentation (processus externe) — doivent être matérialisées dans un fichier ; cet emplacement peut être le disque local ou le stockage partagé RMN files. En v1, seul le disque local est implémenté ; RMN files est un extension point ajoutable derrière la même interface (voir §5).

#### Structure du manifest (un fichier JSON par étude)

```json
{
  "study_id": "CL..",
  "created_at": "…",
  "stages": {
    "mutools.dixon": {
      "status": "completed",
      "completed_at": "…",
      "method": "dixon3pt",
      "parameters": {},
      "version": "mutools==1.4.2",
      "artifacts": […],
      "input_files": [{ "path": "raw_data /", "size": 204800, … }],
      "qc": { "report": "qc/dixon.png", "verdict": "warn", "flags": ["…"] }
    },
    "segmentation": { "status": "failed", "failed_at": "...", "error": "station injoignable" },
    "medical_report": {
      "status": "pending",
      "sign_off": { "user": "…", "at": "…", "verdict": "approved" }
    }
  }
}
```

## 8. Alternatives considered

- Framework de workflow externe (Snakemake / Dagster). Rejeté : dépendance externe subie, mises à jour non maîtrisées, moins de contrôle sur la persistance et l'audit.
- Persistance systématique des intermédiaires (existant). Rejetée : en cas d'échec, les données problématiques persistent et l'erreur se propage aux relances ; le coût dépasse le gain, sauf en débogage (voir §7.1). Implique le point suivant :
- Transport interne sur disque. Ecarté : au profit du passage en mémoire pour les couures internes ; le disque n'est retenu que pour les frontières externes, le debug et les points de suspensions.
- Indexation sur le patient. Rejetée : le pipeline est indexé sur l'examen (aka le patient_id), un réel patient_id reste optionnel et externe (voir §9).
- Multithreading local (mutools). Rejeté en local : pénible à déboguer et sans intérêt pratique. Le parallélisme prend son sens en mode server, via une queue (voir §11).
- DAG explicite. Ecartée : le pipeline est une séquence linéaire (pas de dépendances non-linéaires)

## 9. Security & privacy

- **Authentification + audit trail.** Les utilisateurs sont identifiés ; les actions (qui, quel rôle, quelle étude pseudonymisée, quand) sont tracées dans un audit trail. La contrepartie est la lourdeur ajoutée : tracer impose d'authentifier, et l'authentification doit rester légère pour ne pas alourdir l'usage courant.
- **Indexation sur l'examen** : La clé interne est l'exam_id. Le pseudo par patient est un champ optionnel, non utilisé comme clé par le pipeline ; l'association examen <-> patient et la récupération d'un examen existant sont traités hors pipeline (idéalement côté PACS, maintenu interrogeable), avec un mode de recherche par exam_id.
- **Store partagé concurrency-safe** (petite base) pour l'identité/les rôles, la table de pseudonymes et l'audit.
- **Anonymisation / pseudonymisation** dès dicom, en gate d'entrée, avant que toute donnée descende dans le pipeline.

## 10. Testing strategy

Par stage :

- Tests unitaires (logique isolée).
- Tests de contrat aux coutures (la sortie respecte le schéma attendu en aval).
- Tests golden / régression (sortie comparée à une référence), base de la validation de méthode.
- Dépendances externes (station de seg, PACS) remplacées par des fakes en mémoire, pas des mocks ; tests hermétiques (sans GPU ni réseau).

Validation de méthode (problème récurrent et pénible à traiter) :

- Données de référence par méthode. Chaque méthode dispose d'un jeu de données de référence (input figé). A chaque changement, on rejoue ces données et on compare, ce qui détecte les dérives dans le temps et documente la validation. Cela répond directement à la question « êtes vous sûre que la méthode fonctionne ? »
- Emplacements dédiés. Un emplacement spécifique d'entrée et de sortie par méthode (mode test et mode demo), pertinent pour chaque méthode disponible dans le pipeline.
- Rapport de variabilité. Un diagnostic de variabilité des résultats est produit par méthode. Les QC associés peuvent être conservés avec les données de référence.

Tests spécifiques au runner interne (critiques) :

- Complétude atomique : simuler un crash en cours d'écriture et vérifier qu'aucun output partiel n'est jamais considéré comme valide.
- Détection de péremption (selon les réponses aux questions de cette partie).
- Idempotence : rejouer un run complet ne refait rien et ne corrompt rien.

## 11. Deployment & operations

- **Installation locale.** Chaque utilisateur installe et exécute le pipeline sur sa propre machine. Pas de serveur central de calcul, pas de stockage partagé en v1 — chaque utilisateur travaille sur ses propres données.
- **Exécution v1 locale et bloquante.** Le lot lance le pipeline de manière séquentielle et bloquante = simple, débogable. Pas de multithreading local.
- **Mode server (différé).** Les commandes se mettent en queue et sont traitées de manière non bloquante ; le parallélisme y prend son sens, contrairement au local. La segmentation automatique peut, si le pipeline tourne sur la station de calcul, être appelé comme librairie locale. 
- **Ressources externes paratagées (v1)** :
  - PACS : plusieurs utilisateurs peuvent l'interroger ; capacité à évaluer avec Telemis (normalement largement OK).
  - Station de calcul : service externe partagé ; contrat à formaliser.
  - Les coutures (driving adapters) permettent d'ajouter plus tard un stockage partagé ou une API sans toucher au cœur.

## 12. Rollout / milestones

- **M1 — Contrats + squelette ambulant.** Gèle les 6 contrats de couture (même si certains restent provisoires), un runner minimal et câble un end-to-end trivial sur une étude : DICOM → … → PDF, chemin heureux uniquement. Pas encore de péremption, d'idempotence, de dry-run. But : prouver que la colonne vertébrale et les contrats tournent.
- **M2 — Retirer le risque segmentation.** (Q2, race condition). Fige submit/poll/fetch et l'histoire de complétion.
- **M3 — Brique de calcul (migration mutools) avec UNE méthode + golden tests.** Le cœur scientifique et la validation de méthode
- **M4 — Durcir le runner.** Péremption, atomicité, idempotence, logs structurés, dry-run, tests critiques.
- **M5 — dicom + medical_report vers la cible hexagonale**
- **M6 — QC.** Report systématique (fail-open) d'abord, puis QC gate fail-closed + sign-off + index de lot.
- **M7 — Déféré (Should)** — rôles / modes / sécurité / store pseudonymes partagé, puis optimisation en dernier.

## 13. Open questions

- **Q1 — Stockage et bases de données ?**  
  Question non tranchée, à instruire avant implémentation. Besoins identifiés : séparer les gros lots de recherche des sorties cliniques (quand un user lance des dizaines de milliers de traitements, il n'est pas uutile de les mélanger aux json_output cliniques) ; mais pouvoir agréger à la demande (exporter tous les patients cliniques répondant à des critères, et y adjoindre des patients d'essai clinique pour augment une base). On ne conserve que ce qui est contenu dans le JSON ; à partir de ces sources, une fonction construit une table. Il faut d'abord anticiper l'usage cible des bases puis trancher avec PY.
- **Q2 — Contrat avec la station de segmentation.**  
  Comment le runner lui soumet les fichiers et récupère les résultats — via une API ? oui
- **Q3 — Définition et calibration du QC par courture.**  
  Catalogue les heuristiques par couture, seuils WARN, contenu du montage (vignettes utiles), et politique de lot en fail-closed (étude en échec retenue, le reste du lot continuant). Dimensionne les validateurs automatiques et le human-in-the-loop.
- **Q5 – Niveau d'authentification.**  
  Arbitrer entre l'exigence de traçabilité et la lourdeur ajoutée à l'usage courant
- Il faut pas oublier la gestion des lots 
