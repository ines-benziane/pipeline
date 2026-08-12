# ADR-003 — Gestion des antécédents dans le pipeline

**Statut :** proposé
**Version :** 1
**Date :** 2026-07-28
**Contexte projet :** pipeline IRM, suite du squelette ambulant

---

## 1. Contexte

Un rapport peut avoir besoin de comparer l'examen du jour à un examen antérieur du même patient (l'antécédent).

Aujourd'hui, `medical_report` sait retrouver un antécédent seulement s'il porte **le même exam_id** que l'examen du jour, avec juste une date différente (il cherche des fichiers dans le dossier de résultats). Mais dans la vraie vie, un nouvel examen n'a pas le même exam_id que le précédent : Télémis donne son propre identifiant à chaque passage. Ce mécanisme ne peut donc pas retrouver un vrai antécédent venant d'une autre séance.

Il y a aussi une question ouverte depuis la réunion du 9 juillet : on n'a pas d'identifiant unique par patient. On ne peut donc pas construire facilement notre propre système qui retrouve "l'historique du patient X".

---

## 2. Décision

On ajoute une option pour dire si on veut un antécédent ou non.

- **On ne veut pas d'antécédent** : le pipeline tourne normalement, sur l'examen du jour seulement.
- **On veut un antécédent** :
  1. On regarde si on a déjà quelque chose en base (ou dans un dossier, en attendant la vraie base) pour cet exam_id.
  2. On demande à Télémis (via ExamCatalog) quel est l'antécédent le plus récent connu pour cet examen.
  3. Si ce qu'on a déjà correspond à ce que Télémis dit être le plus récent : on l'utilise tel quel, pas besoin de retraiter.
  4. Sinon (rien en base, ou ce qu'on a est dépassé) : on récupère l'exam_id de l'antécédent le plus récent chez Télémis, on le retraite (retrieve + run) comme un examen normal, et on lance le rapport avec les deux examens : celui du jour et l'antécédent.

Ce système ne demande jamais de connaître l'identité du patient directement. C'est toujours Télémis qui dit ce qui est lié à quoi. Notre propre stockage n'a besoin d'être organisé que par exam_id.

On ne gère qu'**un seul antécédent** (le plus récent) pour l'instant. Gérer plusieurs antécédents est prévu pour une version plus tard, pas maintenant.

---

## 3. Conséquences

### Ce que ça implique aussi

`medical_report` doit pouvoir accepter **une liste d'exam_id** (l'examen du jour + son antécédent) au lieu d'un seul. Aujourd'hui il ne travaille qu'avec un seul exam_id et retrouve ses "antécédents" tout seul par nom de fichier — ce mécanisme ne sert plus une fois qu'on gère de vrais antécédents avec un exam_id différent. Il faut changer ça en même temps que cette décision, pas plus tard.

### Positif

- Pas besoin de résoudre "identifiant unique par patient" pour que ça marche.
- On évite de retraiter un antécédent à chaque rapport si on l'a déjà traité une fois.

### Différé

- Gérer plus d'un antécédent à la fois.
- Vraie base de données (on utilise un dossier ou un stockage simple en attendant, mais organisé comme si c'était la base).

---

## 4. Alternatives écartées

**Toujours tout retraiter, jamais rien en cache.** Simple, mais lent et inutile si l'antécédent a déjà été traité pour un rapport précédent.

**Construire notre propre index par patient.** Écarté : on n'a pas d'identifiant patient stable, et Télémis fait déjà ce travail de relation entre examens — pas la peine de le refaire nous-mêmes.

---

## 5. Références

- Notes de réunion du 9 juillet 2026
- ADR-002 — Granularité du traitement et du rapport
