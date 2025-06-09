import logging

logger = logging.getLogger(__name__)

class NetworkServer:
    """Représente le serveur de réseau LoRa (collecte des paquets reçus)."""
    def __init__(self):
        """Initialise le serveur réseau."""
        # Ensemble des identifiants d'événements déjà reçus (pour éviter les doublons)
        self.received_events = set()
        # Stockage optionnel d'infos sur les réceptions (par ex : via quelle passerelle)
        self.event_gateway = {}
        # Compteur de paquets reçus
        self.packets_received = 0
        # Indicateur ADR serveur
        self.adr_enabled = False
        # Références pour ADR serveur
        self.nodes = []
        self.gateways = []
        self.channel = None

    def receive(self, event_id: int, node_id: int, gateway_id: int):
        """
        Traite la réception d'un paquet par le serveur.
        Évite de compter deux fois le même paquet s'il arrive via plusieurs passerelles.
        :param event_id: Identifiant unique de l'événement de transmission du paquet.
        :param node_id: Identifiant du nœud source.
        :param gateway_id: Identifiant de la passerelle ayant reçu le paquet.
        """
        if event_id in self.received_events:
            # Doublon (déjà reçu via une autre passerelle)
            logger.debug(f"NetworkServer: duplicate packet event {event_id} from node {node_id} (ignored).")
            return
        # Nouveau paquet reçu
        self.received_events.add(event_id)
        self.event_gateway[event_id] = gateway_id
        self.packets_received += 1
        logger.debug(f"NetworkServer: packet event {event_id} from node {node_id} received via gateway {gateway_id}.")

        # Appliquer ADR au niveau serveur si activé
        if self.adr_enabled:
            # Trouver l'objet node et gateway correspondants
            node = next((n for n in self.nodes if n.id == node_id), None)
            gateway = next((g for g in self.gateways if g.id == gateway_id), None)
            if node and gateway and self.channel:
                # Calculer le RSSI de ce paquet au niveau de la gateway
                rssi = self.channel.compute_rssi(node.tx_power, node.distance_to(gateway))
                # Ajuster le SF en respectant les bornes [7,12]
                if rssi > -120 and node.sf > 7:
                    node.sf -= 1
                elif rssi < -120 and node.sf < 12:
                    node.sf += 1
