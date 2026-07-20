# ADR-001 — Déploiement et mode d'accès utilisateur

**Statut :** proposé
**Version :** 1
**Date :** 2026-07-18
**Contexte projet :** pipeline IRM, milestone M1 (squelette ambulant)

---

## 1. Contexte

Le pipeline traite des examens IRM : récupération DICOM, exécution d'une méthode de calcul, génération d'un rapport médical. Deux caractéristiques structurent le problème de déploiement :

- **Traitements longs** : le calcul sur un examen n'est pas une opération interactive de quelques secondes.
- **Point de suspension** : le pipeline peut s'arrêter en attente d'une validation humaine (QC). L'utilisateur doit alors *voir* des images (overviews) et *décider*.

### Contraintes acquises

| Élément | Valeur | Statut |
|---|---|---|
| Machine cible | Station de calcul existante, accès SSH, Linux | Ouvert |
| Accès au PACS (Télémis) depuis la station | Oui, joignable sur le réseau | **Confirmé** |
| Processus permanent (service) | Autorisé, sous réserve de coordination sur la charge | **Confirmé** |
| Gestion des environnements | conda disponible, droits utilisateur suffisants | **Confirmé** |
| Version de Python | Libre (fixée par l'environnement conda) → `>=3.11` retenu | **Confirmé** |
| Environnement de développement | Poste Windows | Confirmé |
| Utilisateurs (phase 1) | Techniciens du labo, médecins — non-développeurs | Confirmé |
| Utilisateurs (phase 2) | Cliniciens partenaires, autres établissements | Confirmé |
| Machine partagée / contention | Station partagée : un calcul lourd voisin peut dégrader le service | **Confirmé** |
| Espace disque dédié | À préciser | Ouvert |
| Sauvegarde de l'espace disque | À préciser | Ouvert |
| Ordonnanceur de travaux (type Slurm) | À vérifier | Ouvert |

---

## 2. Décisions

### D1 — Le calcul s'exécute sur la station, pas sur le poste client

**Acté.** Le calcul scientifique est trop lourd pour un poste client, et les données ne doivent pas circuler.

**Conséquence non négociable :** le client, quel qu'il soit, ne calcule rien. Il ne fait qu'émettre des demandes et consulter des états. **Un point d'entrée réseau côté station est donc inévitable.** Le débat « faut-il une API ? » est clos par cette décision — il ne reste que le choix de la nature du client.

### D2 — Les échanges sont asynchrones par conception

**Acté.** Un traitement n'est jamais un appel bloquant dont on attend le retour.

Un traitement est **soumis** (retour immédiat d'un identifiant), puis son état est **consulté**. Trois raisons convergentes :

1. Les traitements sont longs ; une requête HTTP ne peut pas attendre.
2. Le point de suspension implique qu'un traitement puisse rester en attente indéfiniment, éventuellement repris par une autre personne ou après un redémarrage.
3. Contrainte pratique immédiate : un processus lancé dans une session SSH meurt à la déconnexion.

**Conséquence :** la notion de **job** entre dans le modèle — un objet portant un identifiant, un état, et l'historique de la demande. Cette forme doit être vraie **dès la CLI**, sinon elle sera à réécrire lors du passage à une interface distante.

### D3 — Le mode d'accès est un adaptateur, jamais du cœur

**Acté.** C'est la décision qui rend toutes les autres différables.

CLI aujourd'hui, API et interface visuelle demain : ce sont des adaptateurs primaires au sens de l'architecture hexagonale. Le cœur (runner, méthodes) ignore par quel canal la demande est arrivée.

**Conséquences immédiates sur le code existant :**
- Les `print` actuels dans `run_pipeline` sont provisoires : la sortie devra être injectée, pas codée en dur dans le cœur.
- Aucun `input()` ni interaction directe dans le cœur, jamais.

### D4 — Le canal utilisateur cible est un service exposant une API, avec un client visuel

**Acté sur le principe, différé sur la réalisation.**

Cette conclusion découle des trois contraintes déjà connues, elle n'est pas un choix parmi d'autres :

- calcul sur la station → le client est mince ;
- les fichiers ne doivent pas être modifiables par l'utilisateur → aucun accès direct au système de fichiers, tout passe par un service qui contrôle ;
- le QC exige d'afficher des images et de recueillir une décision → il faut une interface visuelle.

**Le seul degré de liberté restant** est la nature du client : navigateur ou application installée. Ce choix est **réversible** dès lors que l'API existe, et il est donc explicitement différé.

> *Note sur l'option « envoyer un exécutable aux sites distants » :* elle n'évite pas l'API (le calcul reste sur la station), elle ne fait que remplacer le navigateur par un logiciel installé. Elle transfère alors le coût des mises à jour sur N postes × M établissements, chez des utilisateurs non techniques. À écarter comme solution par défaut, sans être définitivement exclue.

### D5 — Phasage

| Phase | Canal | Utilisateurs |
|---|---|---|
| M1–M2 | CLI en SSH sur la station | Développement, techniciens du labo |
| Cible | Service + API + client visuel | Médecins, sites partenaires |

La CLI est l'**outil de travail**, pas le produit. Elle ne doit pas être conçue comme la solution finale, mais elle doit adopter la forme asynchrone (D2) pour être exposable ensuite.

### D6 — Le projet est installable

**Acté et réalisé.** `pyproject.toml` avec installation en mode éditable (`pip install -e .`), dans un environnement conda dédié.

Double bénéfice : les imports ne dépendent plus du répertoire de lancement (gain immédiat), et l'environnement devient reproductible sur la station (prérequis de tout déploiement).

---

## 3. Conséquences transverses

### Contraintes à respecter dès maintenant (coûteuses à rétrofitter)

- **Portabilité Windows → Linux.** Manipulation des chemins exclusivement via `pathlib`, jamais par concaténation de chaînes. Vigilance sur la casse : Linux distingue `Dixon` de `dixon`, Windows non. *S'applique dès le prochain morceau de code, qui manipule `exam_dir` et `workdir`.*

- **Aucun chemin, URL ou nom de base en dur.** Tout provient d'un fichier de configuration. Sans cela, chaque établissement exigerait une version différente du logiciel.

- **L'état de suspension est persistant.** Un traitement en attente de validation doit survivre à un redémarrage et être repris par un autre canal que celui qui l'a lancé. L'état vit en base, pas en mémoire.

- **Environnement reproductible.** Environnement conda dédié au projet, dépendances déclarées dans `pyproject.toml`, même version de Python en développement et sur la station.

### Contention de ressources (nouveau)

La station est partagée. Un calcul lourd lancé par une autre équipe peut rendre le service temporairement inutilisable — sans que le code du pipeline soit en cause. C'est un mode de défaillance difficile à diagnostiquer.

**Conséquences :**
- Toute mise en service permanente doit être **coordonnée** avec les autres utilisateurs de la machine. Ce n'est pas une formalité administrative mais une contrainte technique réelle.
- Cela renforce D2 : séparer le *service* (léger, doit rester réactif) du *calcul* (lourd, peut attendre) est la bonne réponse architecturale. Si un calcul saturait le service, un utilisateur ne pourrait même plus consulter l'état de ses travaux.
- À vérifier : existence d'un ordonnanceur de travaux sur la machine. S'il existe, les calculs devront lui être **soumis** plutôt que lancés directement — forme très proche de celle retenue en D2.

### Explicitement différé

- Choix du client (navigateur vs application installée) et du framework d'API
- Authentification, rôles et permissions
- Conteneurisation, intégration continue, supervision
- Stratégie de sauvegarde et de migration (dépend de l'ADR stockage)
- Déploiement multi-sites et gestion des versions entre établissements

### Risques

| Risque | Gravité | Mitigation |
|---|---|---|
| Du code M1 suppose implicitement un usage local et bloquant (sorties `print`, attente de saisie, chemins locaux) | Élevée | Contraintes ci-dessus + D3 |
| Coût de l'interface de QC sous-estimé (affichage d'overviews, recueil de validation) | Moyenne | Instruire tôt, réaliser tard |
| Contention sur la station dégrade le service sans cause apparente dans le code | Moyenne | Coordination + séparation service / calcul |
| L'espace de stockage n'est pas sauvegardé par l'IT | À évaluer | Question ouverte, à poser |

---

## 4. Questions ouvertes

- Le QC est-il validé par la personne qui lance le traitement, ou par un rôle distinct ? *(Impacte fortement la conception de l'interface.)*
- Les établissements partenaires accèdent-ils au **même** service, ou chacun déploie-t-il le sien ? *(Change le modèle de données et la sécurité.)*
- Combien d'examens simultanés faut-il envisager ? *(Détermine si un traitement séquentiel suffit ou s'il faut une file.)*
- Où est l'espace disque dédié, quelle capacité, qui y a accès, est-il sauvegardé ?
- Existe-t-il un ordonnanceur de travaux sur la station ?
- D'autres outils sont-ils déjà déployés sur cette machine, et selon quelle procédure ? *(S'aligner sur un précédent coûte moins cher que d'imposer une approche nouvelle.)*

---

## 5. Références

- Notes de réunion du 9 juillet 2026— stockage, arborescence, accès aux fichiers
- Design doc pipeline IRM v2, §5 (architecture hexagonale), §7 (design détaillé)
- ADR-001 v1 (2026-07-18), remplacé par le présent document