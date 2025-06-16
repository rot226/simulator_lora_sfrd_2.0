# Simulateur Réseau LoRa

Ce dépôt contient un simulateur complet de réseau LoRa réalisé en Python. Le code source principal se trouve dans `VERSION_8/launcher` et s'utilise soit via l'interface graphique Panel soit en ligne de commande.

## Installation

1. Clonez ce dépôt puis créez un environnement virtuel (optionnel mais recommandé):
   ```bash
   python3 -m venv env
   source env/bin/activate  # Sous Windows : env\Scripts\activate
   ```
2. Installez les dépendances :
   ```bash
   pip install -r requirements.txt
   ```

## Lancement du tableau de bord Panel

Exécutez la commande suivante pour démarrer l'interface graphique permettant de configurer et lancer la simulation :

```bash
panel serve VERSION_8/launcher/dashboard.py --show
```

## Utilisation en ligne de commande

La simulation peut aussi être exécutée sans interface :

```bash
python VERSION_8/run.py --nodes 30 --gateways 1 --area 1000 --mode Random --interval 10 --steps 100 --output resultats.csv
```

## Mobilité optionnelle

Dans le `dashboard`, la case « Activer la mobilité des nœuds » permet de choisir si les nœuds se déplacent pendant la simulation. Cette option correspond au paramètre `mobility` du `Simulator`. Si elle est décochée, tous les nœuds demeurent statiques.
