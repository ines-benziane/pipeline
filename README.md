# Pipeline

pip install jinja2
pip install weasyprint
pip install cmcrameri
pip install pydantic
pip install -e tools\py-bspline
pip install pyyaml 

## Installation

Le dépôt est un monorepo de plusieurs packages editables (`myo-pipeline` à la racine, `myo-medical-report` dans `medical_report/`, plus `bsplines`, un package local hors PyPI). setuptools n'a pas de mode "workspace" : un script d'installation enchaîne les étapes.

1. **Environnement conda dédié** (à faire une fois) :
   ```
   conda create -n pipeline python=3.11
   conda activate pipeline
   ```

2. **Installation complète du workspace**, depuis la racine du projet :
   - Linux : `./install.sh`
   - Windows : `.\install.ps1`

   Le script installe, dans l'ordre, `myo-pipeline` (avec les extras `dev`), `myo-medical-report`, puis `bsplines` — tous en editable. Il s'arrête immédiatement si une étape échoue.

3. **Dépendances système — WeasyPrint** : WeasyPrint nécessite des bibliothèques système (GTK / Pango / Cairo) que pip n'installe pas. Sous Linux, ce sont des paquets système à prévoir lors du déploiement (ex. sur la station de calcul).
