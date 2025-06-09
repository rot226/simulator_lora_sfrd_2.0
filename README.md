src/
    node.py
    gateway.py
    channel.py
    server.py
    simulator.py
    dashboard.py
    __init__.py
run.py
requirements.txt
README.md

# Simulateur Réseau LoRa (Python 3.10+)

Bienvenue ! Ce projet est un **simulateur complet de réseau LoRa**, inspiré du fonctionnement de FLoRa sous OMNeT++, codé entièrement en Python.

## 🛠️ Installation

1. **Clonez ou téléchargez** le projet.
2. **Créez un environnement virtuel** (optionnel mais recommandé) :
   ```bash
   python3 -m venv env
   source env/bin/activate  # Sous Windows : env\Scripts\activate

pip install -r requirements.txt

panel serve dashboard.py --show

python run.py --nodes 30 --gateways 1 --area 1000 --mode Random --interval 10 --steps 100 --output resultats.csv

python run.py --nodes 20 --mode Random --interval 15

python run.py --nodes 5 --mode Periodic --interval 10

panel serve dashboard.py --show
