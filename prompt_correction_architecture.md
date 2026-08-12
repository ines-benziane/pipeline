Correction importante : tu m'as dit "jamais mutools, exprès, puisque tout l'objectif est que ton Method réimplémenté n'en dépende pas du tout (ni import mutools, ni appel subprocess)". C'est faux, et ça contredit la vraie décision, prise en réunion avec mon boss.

**La vraie architecture** : `methods` **appelle mutools comme une dépendance installée normale** — `import mutools...` puis des appels directs à ses fonctions (ex: `mutools.fatwater.dixon.dixon_3pt(...)`). Je ne copie jamais le code source de mutools dans PIPELINE_01, je ne le réimplémente jamais. Je ne suis pas chercheuse : je n'ai pas le droit de toucher à la logique de calcul des algorithmes (recherche publiée). Ce que j'écris moi-même, c'est uniquement la plomberie autour (lecture DICOM, orchestration, empaquetage du résultat) — jamais le calcul lui-même.

Règle absolue, indépendante de tout ça : je ne modifie jamais un seul fichier du dépôt mutools (lecture seule uniquement).

Reprends sur cette base. Si une décision technique déjà prise semble contredire ce modèle, demande-moi avant de conclure autre chose.
