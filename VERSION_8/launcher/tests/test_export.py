import panel as pn
import pandas as pd
import os

pn.extension()

def exporter_csv(event=None):
    df = pd.DataFrame({
        "Nom": ["Alice", "Bob", "Charly"],
        "Score": [14, 18, 12]
    })
    chemin = os.path.join(os.getcwd(), "resultats_panel.csv")
    df.to_csv(chemin, index=False, encoding="utf-8")
    message.object = f"✅ Fichier exporté : <b>{chemin}</b><br>(Ouvre-le avec Excel ou pandas)"

    # Optionnel : ouvrir le dossier (Windows uniquement)
    try:
        os.startfile(os.getcwd())
    except Exception:
        pass

export_button = pn.widgets.Button(name="Exporter CSV (dossier courant)", button_type="primary")
export_button.on_click(exporter_csv)

message = pn.pane.HTML("Clique sur le bouton pour générer le fichier CSV.")

dashboard = pn.Column(
    pn.pane.Markdown("# Export CSV – Solution universelle"),
    export_button,
    message
)
dashboard.servable()
