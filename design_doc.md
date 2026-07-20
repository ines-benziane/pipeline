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
| **Dernière maj** | 2026-07-02 |

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

- Chaîner les quatre briques en un pipeline cohérent, exécutable de bout en bout.
- Permettre l'exécution partielle : entrer dans le pipeline à partir de dicoms ou de sauter la segmentation automatique en faveur de la segmentation manuelle et reprendre le cours du pipeline.

| Ce qu'on a déjà | Ce qu'on saute | Ce qu'on lance |
|---|---|---|
| rien | — | dicom → mutools.dixon + mutools.t2 → segmentation → get_result → medical_report |
| DICOMs | dicom | mutools.dixon + mutools.t2 → segmentation → get_result → medical_report |
| Work/ + roi_museg/ | dicom + mutools.dixon + mutools.t2 + segmentation | get_result → medical_report |
| json_output/ | tout sauf le rapport | medical_report |

- Garantir la reproductibilité : tout résultat est rattachable à une méthode, une version et des algos connus.
- Rendre les runs débogables : logs structurés et données intermédiaires inspectables à chaque étape.
- Intégrer un contrôle qualité adapté au mode d'usage (lot vs quelques patients).
- Permettre de réintégrer les informations du patient de manière cadrée lors de la génération du compte-rendu.
- Respecter les Good Clinical Practices : audit trail, garantie sur les méthodes, mesures prise pour vérifier que l'on fait bien ce que l'on veut et croit faire. Traçabilité sur les interventions automatiques et manuelles. Enregistrement des changements de paramètres.
- Offrir une interface en ligne de commande claire et prédéfinie.

## 3. Non-goals

- Flexibilité maximale de paramétrage : on privilégie un jeu de méthodes prédéfinies à paramètres figés plutôt qu'un paramétrage libre.
- Appliquer le pipeline à des données traitées ultérieurement : tout ce qui est utilisé par le pipeline est généré par le pipeline.
- Reprise en cours de route en cas d'échec : si ça plante on recommence de 0.
- Conserver les artéfacts systématiquement : on ne les conserve que dans une approche de débogage.

## 4. User stories

### Must (la v1)

- En tant qu'utilisateur (tout rôle), quel que soit le point d'entrée (DICOM, work/, roi_museg/, json_output/), le pipeline s'enchaîne automatiquement jusqu'à la cible demandée sans intervention manuelle entre les étapes, hors QC.
- En tant qu'utilisateur, je peux lancer le traitement sur un lot d'études.
- En tant qu'utilisateur, je peux exécuter le pipeline complet sur une étude.
- En tant qu'utilisateur, je peux exécuter dicom seul pour récupérer et anonymiser des DICOM, afin d'y appliquer ensuite mes propres calculs.
- En tant qu'utilisateur, je peux exécuter le pipeline à partir de DICOM déjà anonymisés que je possède.
- En tant qu'utilisateur, je peux générer un rapport médical à partir de données déjà traitées, sans rejouer les étapes en amont.
- En tant qu'utilisateur, je peux substituer la segmentation automatique par une segmentation manuelle (en fournissant mes propres masques) et lancer le pipeline depuis ce point.
- En tant qu'ingénieure, je peux déboguer un run échoué en inspectant les données intermédiaires et les logs de chaque étape.
- En tant que chercheur, je peux choisir une méthode de calcul dans une liste prédéfinie (paramètres figés) pour produire les cartographies.

### Should

L'architecture v1 est conçue pour accueillir modes et rôles ; leur implémentation est déférée.

- Modes d'usage (définis il y a qqs mois — déterminent le traitement des identifiants) :
  - RESEARCH — anonymisation irréversible ; pseudonyme à usage unique, l'ID n'importe pas.
  - CLINICS — pseudonymisation ; ID unique par patient + table pseudo↔patient ; centré patient ; rapport médical.
  - STUDY — pseudonymisation ; ID défini par l'étude ; centré cohorte.
- En tant qu'utilisateur, je bénéficie d'un QC automatique en mode lot et d'un QC humain pour un petit nombre de patients.
- En tant qu'ingénieur, j'ai accès aux audit_logs : manifest + fichier audit_log.json — qui accumule tous les runs sans écraser.
- Mettre en place un server
- En tant qu'utilisateur, je peux choisir de récolter mes résultats

### Could

- En tant qu'utilisateur, je dispose d'une interface graphique au-dessus de la CLI.
- En tant qu'utilisateur, je peux lancer un "dry run" pour afficher le plan d'exécution sans l'exécuter, pour indiquer ce que l'on fait et ce que l'on saute lors de l'exécution du pipeline et modifier si besoin.

### Won't

- En tant qu'utilisateur, je ne peux pas appliquer le pipeline à des données qu'il n'a pas généré (hors segmentation manuelle).

## 5. Design principles

- **Stages composables** : chaque brique est une unité indépendante, avec un contrat d'entrée/sortie explicite.
- **Hexagonal par stage** : logique métier au cœur, isolée de l'I/O par des ports et adapters. État actuel : medical_report dispose déjà des fondations (ports reader/writer, domain models Pydantic) ; dicom et la couche de génération PDF de medical_report seront refactorisés pour atteindre cet objectif
- **Fail fast** : chaque stage valide son entrée contre un schéma et refuse bruyamment toute donnée invalide.
- **Reproductibilité d'abord** : méthodes à paramètres figés, provenance tracée.
- **Différer les décisions d'infra** : les coutures permettent d'ajouter un serveur plus tard sans toucher au cœur.

## 6. Proposed design — vue d'ensemble

L'utilisateur lance une commande en précisant sa cible (ex. : "je veux le rapport médical de cette étude"). Le système traite l'étude du début à la fin en une seule passe, sans intervention manuelle entre les étapes (à part QC humain). Traitement par lot (batch) : les données arrivent en unités discrètes (une acquisition = une étude), les calculs sont lourds, et l'on veut pouvoir rejouer n'importe quelle étude de façon déterministe.

L'outil est installé localement par chaque utilisateur ; chaque utilisateur travaille sur ses propres données en local, sans coordination nécessaire entre machines.

- ① Récupération DICOM : en une commande, l'utilisateur indique le degré de pseudo/ano et les series demandées.
- ② Calcul des cartographies : mutools exécute un algorithme par biomarqueur. Ces étapes sont indépendantes entre elles — les cartographies Dixon/FF et les cartographies T2 peuvent être calculées dans n'importe quel ordre. Chaque algorithme produit sa sortie dans work/.
- ③ Segmentation : la station distante segmente les muscles à partir des séries Dixon/VIBE uniquement (dixon_mag/). Elle produit les masques partagés (roi_museg/), utilisés ensuite par tous les biomarqueurs. Elle ne peut démarrer qu'une fois les cartographies Dixon disponibles. (possible sur T2 si on a que ça mais pas top)
- ④ Extraction des résultats (get_result) : combine les cartographies de chaque biomarqueur avec les masques de segmentation pour produire les fichiers JSON.
- ⑤ Rapport : medical_report lit l'ensemble des fichiers JSON et génère un seul rapport PDF.

## 7. Detailed design

### 7.1 Runner interne (coordination)

- **DAG déclaré.** Le DAG est le graphe des étapes et leurs dépendances.
- **Résolution par cible.** Pour un output demandé, le runner calcule le sous-ensemble minimal d'étapes à exécuter (tri topologique sur le sous-DAG : fonction python) et commence dès le début de ce sous-ensemble.
- **Détection de péremption.** Deux cas concrets à couvrir — à voir avec PY :
  - Relance sur étude déjà traitée. On relance depuis le début (sauf récupération des DICOM). Vu en « No-goals » : on ne garde pas les artéfacts donc obligé de reprendre du début.
  - Cohérence longitudinale. Un patient a deux examens à des dates différentes. Si l'algorithme T2 a changé entre les deux, les résultats ne sont plus comparables. Faut-il forcer le recalcul du premier examen avec la nouvelle version ? (PY)
- **Méthode** : comparaison directe dans le manifest. Le manifest de chaque étude stocke, pour chaque stage complété, les composantes qui définissent ce qui a été calculé : méthode, paramètres, version du package, taille et date de modification des fichiers d'entrée. Au run suivant, le runner compare ces champs avec l'état actuel — si tout correspond, il saute l'étape ; sinon, il relance.
- **Complétude du nom.** Écriture de l'artefact dans un emplacement temporaire puis rename en cas de succès avec le nom définitif et analysable par le runner ; suppression des outputs tmp incomplets en cas d'échec. Aucun output partiel n'est jamais visible comme complet.
- **Idempotence.** Lancer la même étape deux fois avec les mêmes inputs donne le même résultat, sans effet de bord.
- **Logs structurés.** Chaque ligne de log porte : run_id (identifiant unique du run), stage (l'étape en cours), study_id (l'étude traitée), level (INFO / WARNING / ERROR) et msg (le message ou l'erreur).
- **Audit.** Le manifest par étude constitue la trace d'audit principale : il enregistre pour chaque stage la méthode, la version, les paramètres, le statut et les timestamps. Ce qu'il ne couvre pas : l'historique des relances (un retraitement écrase le manifest précédent). Un fichier audit_log.jsonl append-only par étude — qui accumule tous les runs sans écraser — sera implémenté ultérieurement (Should).
- **Gestion d'échec.** Arrêt sur erreur avec message clair. Pour l'étape de segmentation (station distante), le runner réessaie automatiquement en cas de non-réponse, en espaçant les tentatives.

### 7.2 Anatomie d'un stage (hexagonal)

Chaque stage suit le même squelette :

- Valider l'entrée contre un schéma (fail fast).
- Exécuter la logique métier (cœur sans I/O).
- Passer la QC gate s'il y en a (§7.5).
- Valider et écrire la sortie ; mettre à jour le manifest.

### 7.3 Brique de calcul (migration `mutools`)

Stratégie : On reprend les algorithmes de `mutools` et on réécrit la plomberie. La brique est décomposée en sous-étapes inspectables.

Registre de méthodes. Catalogue nom → (algorithme, paramètres figés, version).  
L'utilisateur choisit une méthode par son nom ; pas de paramètres libres. Une variation d'algorithme = une nouvelle méthode nommée. La méthode utilisée est inscrite dans le manifest et le rapport.

### 7.4 Intégration de la segmentation (frontière asynchrone)

La station de segmentation est distante et n'est pas notre code : elle est traitée comme un service externe via un adapter dédié.

- **Pattern** : submit → poll → fetch.
- **Anti-race-condition** : Comment ne pas lire un résultat en cours d'écriture ? (Éviter : la seg crée roi_museg mais n'a pas fini d'écrire dessus et le runner voit roi_museg et le lit) (rename au bon moment ? nécessite une implémentation supp de museg-ai)
- **Robustesse** : retries avec backoff, timeout, comportement en cas de déconnexion.
- **Contrat à formaliser** : format/emplacement d'entrée, format/emplacement de sortie, signal de fin, comportement en cas d'échec.

### 7.5 Contrôle qualité (QC gate)

- Mode lot → QC automatique.
- Petit nombre de patients → QC humain : le run se met en pause et attend une approbation avant de poursuivre.

### 7.6 Génération du rapport

medical_report lit les fichiers JSON produits par `get_result` puis génère le rapport de façon déterministe. La lecture des JSON et l'écriture du PDF se font via des interfaces (ports) — ni la source ni la destination ne sont câblées en dur dans le code. Cela permet d'exécuter medical_report seul sur des données déjà traitées, et de le tester sans accès au disque. La gestion des informations identifiantes du patient selon le rôle (médical vs pseudonyme) est déférée en Should.

### 7.7 Contrats de données et provenance

#### Contrats par couture

| # | Producteur | Consommateur | Artefact | Format |
|---|---|---|---|---|
| 1 | dicom | mutools.dixon + mutools.t2 | aw_data | Fichiers DICOM (.dcm), organisés par série |
| 2 | mutools.dixon | segmentation | work/dixon_mag/ | Cartographies magnitude VIBE (mag_1.mha, mag_2.mha) |
| 3 | mutools.dixon | mutools.get_result | work/dixon3pt/, work/roi_dixon/ | |
| 4 | mutools.t2 | mutools.get_result | work/t2map_3exp_dict/ | |
| 5 | segmentation | mutools.get_result | roi_museg/ | |
| 6 | get_result | medical_report | json_output/ | JSON |

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
      "artifacts": ["work/dixon_mag/", "work/dixon3pt/", "work/roi_dixon/"],
      "input_files": [{ "path": "raw_data /", "size": 204800, …}]
    },
    "segmentation": { "status": "failed", "failed_at": "...", "error": "station injoignable" },
    "medical_report": { "status": "pending" }
  }
}
```

## 8. Alternatives considered

- Framework de workflow externe (Snakemake / Dagster).

## 9. Security & privacy

- **Rôles (RBAC — role based access control).** Deux rôles : utilisateur (ingé/chercheur/étudiant) et médical (manip/médecin). Les deux peuvent lancer le pipeline et générer un rapport.
- **Ré-identification.** Seul le rôle médical accède aux informations identifiantes du patient et à la table de correspondance pseudonyme ↔ patient ; les autres rôles ne voient que le pseudonyme dans le rapport. La ré-identification n'est possible que pour des données pseudonymisées (CLINICS / STUDY) ; l'anonymisation RESEARCH est irréversible.
- **Authentification + audit trail.** Les utilisateurs sont identifiés ; les actions (qui, quel rôle, quelle étude pseudonymisée, quand) sont tracées dans un audit trail.
- **Store partagé concurrency-safe** (petite base) pour l'identité/les rôles, la table de pseudonymes et l'audit.
- **Anonymisation / pseudonymisation** dès dicom, en gate d'entrée, avant que toute donnée descende dans le pipeline.

## 10. Testing strategy

Par stage :

- Tests unitaires (logique isolée).
- Tests de contrat aux coutures (la sortie respecte le schéma attendu en aval).
- Tests golden / régression (sortie comparée à une référence), base de la validation de méthode.
- Dépendances externes (station de seg, PACS) remplacées par des fakes en mémoire, pas des mocks ; tests hermétiques (sans GPU ni réseau).

Tests spécifiques au runner interne (critiques) :

- Complétude atomique : simuler un crash en cours d'écriture et vérifier qu'aucun output partiel n'est jamais considéré comme valide.
- Détection de péremption (selon les réponses aux questions de cette partie).
- Idempotence : rejouer un run complet ne refait rien et ne corrompt rien.

## 11. Deployment & operations

- **Installation locale.** Chaque utilisateur installe et exécute le pipeline sur sa propre machine. Pas de serveur central de calcul, pas de stockage partagé en v1 — chaque utilisateur travaille sur ses propres données.
- **Ressources externes partagées (v1)** :
  - PACS : plusieurs utilisateurs peuvent l'interroger ; capacité à évaluer avec Telemis (normalement largement OK).
  - Station de calcul : service externe partagé ; contrat à formaliser.
- Les coutures (driving adapters) permettent d'ajouter plus tard un stockage partagé ou une API sans toucher au cœur.

## 12. Rollout / milestones

- **M1 — Contrats + squelette ambulant.** Gèle les 6 contrats de couture (même si certains restent provisoires), un runner minimal (DAG + résolution par cible + écriture disque), et câble un end-to-end trivial sur une étude : DICOM → … → PDF, chemin heureux uniquement. Pas encore de péremption, d'idempotence, de dry-run. But : prouver que la colonne vertébrale et les contrats tournent.
- **M2 — Retirer le risque segmentation.** (Q2, race condition). Fige submit/poll/fetch et l'histoire de complétion.
- **M3 — Brique de calcul (migration mutools) avec UNE méthode + golden tests.** Le cœur scientifique et la validation de méthode
- **M4 — Durcir le runner.** Péremption, atomicité, idempotence, logs structurés, dry-run, tests critiques.
- **M5 — dicom + medical_report vers la cible hexagonale**
- **M6 — QC gate** (auto + pause humaine).
- **M7 — Déféré (Should)** — rôles / modes / sécurité / store pseudonymes partagé, puis optimisation en dernier.

## 13. Open questions

- **Q1 — Où stocker les rôles et les pseudonymes ?**  
  Quand on implémentera les rôles (médical vs utilisateur) et la table pseudonyme ↔ patient, il faudra décider où ces informations vivent : fichier local, base SQLite, autre. Déféré en Should — à trancher avec PY avant d'implémenter §4 Should.
- **Q2 — Contrat avec la station de segmentation :**  
  Comment le runner lui soumet les fichiers et récupère les résultats — via une API ?
- **Q3 — Définition de « QC raté » par étape :**  
  Dimensionne les validateurs automatiques et le human-in-the-loop.
- **Q4 — Anonymisation irréversible vs pseudonymisation :**  
  Le `patient_id` revient partout — noms de fichiers, manifest, future base de données. En mode CLINICS, le pseudonyme doit être stable dans le temps pour un même patient (pour retrouver tous ses examens et comparer les antécédents). La question est : comment le générer de façon garantie unique par patient ? (en attendant la mise en place du pseudo unique par le labo : recherche automatique avec le nom de patient sur Télémis pour récupérer tous les examens ?)
