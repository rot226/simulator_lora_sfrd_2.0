import math
import heapq
import numpy as np
import pandas as pd
import logging
from node import Node
from gateway import Gateway
from channel import Channel
from server import NetworkServer

logger = logging.getLogger(__name__)

class Simulator:
    """Gère la simulation du réseau LoRa (nœuds, passerelles, événements)."""
    # Constantes ADR LoRaWAN standard
    REQUIRED_SNR = {7: -7.5, 8: -10.0, 9: -12.5, 10: -15.0, 11: -17.5, 12: -20.0}
    MARGIN_DB = 10.0            # marge d'installation en dB (typiquement 10 dB)
    PER_THRESHOLD = 0.1         # Seuil de Packet Error Rate pour déclencher ADR
    
    def __init__(self, num_nodes: int = 10, num_gateways: int = 1, area_size: float = 1000.0,
                 transmission_mode: str = 'Random', packet_interval: float = 60.0,
                 packets_to_send: int = 0, adr_node: bool = False, adr_server: bool = False):
        """
        Initialise la simulation LoRa avec les entités et paramètres donnés.
        :param num_nodes: Nombre de nœuds à simuler.
        :param num_gateways: Nombre de passerelles à simuler.
        :param area_size: Taille de l'aire carrée (mètres) dans laquelle sont déployés nœuds et passerelles.
        :param transmission_mode: 'Random' pour transmissions aléatoires (Poisson) ou 'Periodic' pour périodiques.
        :param packet_interval: Intervalle moyen entre transmissions (si Random, moyenne en s; si Periodic, période fixe en s).
        :param packets_to_send: Nombre total de paquets à émettre avant d'arrêter la simulation (0 = infini).
        :param adr_node: Activation de l'ADR côté nœud.
        :param adr_server: Activation de l'ADR côté serveur.
        """
        # Paramètres de simulation
        self.num_nodes = num_nodes
        self.num_gateways = num_gateways
        self.area_size = area_size
        self.transmission_mode = transmission_mode
        self.packet_interval = packet_interval
        self.packets_to_send = packets_to_send
        self.adr_node = adr_node
        self.adr_server = adr_server
        
        # Initialiser le canal radio et le serveur réseau
        self.channel = Channel()
        self.network_server = NetworkServer()
        
        # Générer les passerelles
        self.gateways = []
        for gw_id in range(self.num_gateways):
            if self.num_gateways == 1:
                # Une seule passerelle au centre de l'aire
                gw_x = area_size / 2.0
                gw_y = area_size / 2.0
            else:
                # Plusieurs passerelles placées aléatoirement
                gw_x = np.random.rand() * area_size
                gw_y = np.random.rand() * area_size
            self.gateways.append(Gateway(gw_id, gw_x, gw_y))
        
        # Générer les nœuds aléatoirement dans l'aire et assigner un SF initial
        self.nodes = []
        for node_id in range(self.num_nodes):
            x = np.random.rand() * area_size
            y = np.random.rand() * area_size
            sf = np.random.randint(7, 13)        # SF aléatoire entre 7 et 12
            tx_power = 14.0                      # Puissance d'émission typique en dBm
            node = Node(node_id, x, y, sf, tx_power)
            # Enregistrer les états initiaux du nœud pour rapport ultérieur
            node.initial_x = x
            node.initial_y = y
            node.initial_sf = sf
            node.initial_tx_power = tx_power
            # Attributs supplémentaires pour mobilité et ADR
            node.history = []            # Historique des 20 dernières transmissions (snr, delivered)
            node.in_transmission = False # Indique si le nœud est actuellement en transmission
            node.current_end_time = None # Instant de fin de la transmission en cours (si in_transmission True)
            node.last_rssi = None       # Dernier meilleur RSSI mesuré pour la transmission en cours
            self.nodes.append(node)
        
        # File d'événements (min-heap)
        self.event_queue = []
        self.current_time = 0.0
        self.event_id_counter = 0
        
        # Statistiques cumulatives
        self.packets_sent = 0
        self.packets_delivered = 0
        self.packets_lost_collision = 0
        self.packets_lost_no_signal = 0
        self.total_energy_J = 0.0
        self.total_delay = 0.0
        self.delivered_count = 0
        
        # Journal des événements (pour export CSV)
        self.events_log = []
        
        # Planifier le premier envoi de chaque nœud et le premier mouvement
        for node in self.nodes:
            if self.transmission_mode.lower() == 'random':
                # Random: tirer un délai initial selon une distribution exponentielle
                t0 = np.random.exponential(self.packet_interval)
            else:
                # Periodic: délai initial aléatoire uniforme dans [0, période]
                t0 = np.random.rand() * self.packet_interval
            self.schedule_event(node, t0)
            # Planifier le premier changement de position au bout de 10 secondes
            self.schedule_mobility(node, 10.0)
        
        # Indicateur d'exécution de la simulation
        self.running = True
    
    def schedule_event(self, node: Node, time: float):
        """Planifie un événement de transmission pour un nœud à l'instant donné."""
        event_id = self.event_id_counter
        self.event_id_counter += 1
        heapq.heappush(self.event_queue, (time, 1, event_id, node))
        logger.debug(f"Scheduled transmission {event_id} for node {node.id} at t={time:.2f}s")
    
    def schedule_mobility(self, node: Node, time: float):
        """Planifie un événement de mobilité (déplacement aléatoire) pour un nœud à l'instant donné."""
        event_id = self.event_id_counter
        self.event_id_counter += 1
        heapq.heappush(self.event_queue, (time, 2, event_id, node))
        logger.debug(f"Scheduled mobility {event_id} for node {node.id} at t={time:.2f}s")
    
    def step(self) -> bool:
        """Exécute le prochain événement planifié. Retourne False si plus d'événement à traiter."""
        if not self.running or not self.event_queue:
            return False
        # Extraire le prochain événement (le plus tôt dans le temps)
        time, priority, event_id, node = heapq.heappop(self.event_queue)
        # Avancer le temps de simulation
        self.current_time = time
        
        if priority == 1:
            # Début d'une transmission émise par 'node'
            node_id = node.id
            sf = node.sf
            tx_power = node.tx_power
            # Durée de la transmission
            duration = self.channel.airtime(sf)
            end_time = time + duration
            # Mettre à jour le compteur de paquets émis
            self.packets_sent += 1
            # Énergie consommée par la transmission (E = P(mW) * t)
            p_mW = 10 ** (tx_power / 10.0)  # convertir dBm en mW
            energy_J = (p_mW / 1000.0) * duration
            self.total_energy_J += energy_J
            node.add_energy(energy_J)
            # Marquer le nœud comme en cours de transmission
            node.in_transmission = True
            node.current_end_time = end_time
            
            heard_by_any = False
            best_rssi = None
            # Propagation du paquet vers chaque passerelle
            for gw in self.gateways:
                distance = node.distance_to(gw)
                rssi = self.channel.compute_rssi(tx_power, distance)
                # Vérifier si le signal est décodable par la passerelle
                if rssi < self.channel.sensitivity_dBm.get(sf, -float('inf')):
                    continue  # signal trop faible pour être reçu
                heard_by_any = True
                if best_rssi is None or rssi > best_rssi:
                    best_rssi = rssi
                # Démarrer la réception à la passerelle (gestion des collisions et capture)
                gw.start_reception(event_id, node_id, sf, rssi, end_time,
                                   self.channel.capture_threshold_dB, self.current_time)
            
            # Retenir le meilleur RSSI mesuré pour cette transmission
            node.last_rssi = best_rssi if heard_by_any else None
            # Planifier l'événement de fin de transmission correspondant
            heapq.heappush(self.event_queue, (end_time, 0, event_id, node))
            # Planifier la prochaine transmission de ce nœud (selon le mode), sauf si limite atteinte
            if self.packets_to_send == 0 or self.packets_sent < self.packets_to_send:
                if self.transmission_mode.lower() == 'random':
                    next_interval = np.random.exponential(self.packet_interval)
                else:
                    next_interval = self.packet_interval
                next_time = end_time + next_interval
                self.schedule_event(node, next_time)
            else:
                # Limite de paquets atteinte: ne plus planifier de nouvelles transmissions
                new_queue = []
                for evt in self.event_queue:
                    # Conserver uniquement les fins de transmissions en cours (priority 0)
                    if evt[1] == 0:
                        new_queue.append(evt)
                heapq.heapify(new_queue)
                self.event_queue = new_queue
                logger.debug("Packet limit reached – no more new events will be scheduled.")
            
            # Journaliser l'événement de transmission (résultat inconnu à ce stade)
            self.events_log.append({
                'event_id': event_id,
                'node_id': node_id,
                'sf': sf,
                'start_time': time,
                'end_time': end_time,
                'energy_J': energy_J,
                'heard': heard_by_any,
                'result': None,
                'gateway_id': None
            })
            return True
        
        elif priority == 0:
            # Fin d'une transmission – traitement de la réception/perte
            node_id = node.id
            # Marquer la fin de transmission du nœud
            node.in_transmission = False
            node.current_end_time = None
            # Notifier chaque passerelle de la fin de réception
            for gw in self.gateways:
                gw.end_reception(event_id, self.network_server, node_id)
            # Vérifier si le paquet a été reçu par au moins une passerelle
            delivered = event_id in self.network_server.received_events
            if delivered:
                self.packets_delivered += 1
                # Délai = temps de fin - temps de début de l'émission
                start_time = next(item for item in self.events_log if item['event_id'] == event_id)['start_time']
                delay = self.current_time - start_time
                self.total_delay += delay
                self.delivered_count += 1
            else:
                # Identifier la cause de perte: collision ou absence de couverture
                log_entry = next(item for item in self.events_log if item['event_id'] == event_id)
                heard = log_entry['heard']
                if heard:
                    self.packets_lost_collision += 1
                else:
                    self.packets_lost_no_signal += 1
            # Mettre à jour le résultat et la passerelle du log de l'événement
            for entry in self.events_log:
                if entry['event_id'] == event_id:
                    entry['result'] = 'Success' if delivered else ('CollisionLoss' if entry['heard'] else 'NoCoverage')
                    entry['gateway_id'] = self.network_server.event_gateway.get(event_id, None) if delivered else None
                    break
            
            # Gestion Adaptive Data Rate (ADR)
            if self.adr_node:
                # Mettre à jour l'historique du nœud (20 dernières transmissions)
                snr_value = None
                if delivered and node.last_rssi is not None:
                    # Calculer le SNR mesuré (approximation) à partir du meilleur RSSI
                    snr_value = (node.last_rssi - self.channel.sensitivity_dBm.get(node.sf, -float('inf'))
                                 + Simulator.REQUIRED_SNR.get(node.sf, 0.0))
                node.history.append({'snr': snr_value, 'delivered': delivered})
                if len(node.history) > 20:
                    node.history.pop(0)
                # Calculer le PER récent et la marge ADR
                total_count = len(node.history)
                success_count = sum(1 for e in node.history if e['delivered'])
                per = (total_count - success_count) / total_count if total_count > 0 else 0.0
                snr_values = [e['snr'] for e in node.history if e['snr'] is not None]
                margin_val = None
                if snr_values:
                    max_snr = max(snr_values)
                    # Marge = meilleur SNR - SNR minimal requis (pour SF actuel) - marge d'installation
                    margin_val = max_snr - Simulator.REQUIRED_SNR.get(node.sf, 0.0) - Simulator.MARGIN_DB
                # Vérifier déclenchement d'une requête ADR (marge suffisante ou PER trop élevé)
                if (margin_val is not None and margin_val > 0) or (per > Simulator.PER_THRESHOLD):
                    if self.adr_server:
                        # Traitement de la requête ADR côté serveur: calcul des nouveaux SF/TxPower
                        if per > Simulator.PER_THRESHOLD:
                            # Lien de mauvaise qualité – augmenter la portée (augmenter SF ou puissance)
                            if node.sf < 12:
                                node.sf += 1  # augmenter SF (ralentir le débit pour plus de portée)
                            elif node.tx_power < 14.0:
                                node.tx_power = min(14.0, node.tx_power + 3.0)  # augmenter puissance de 3 dB
                        elif margin_val is not None and margin_val > 0:
                            # Lien avec bonne marge – optimiser en réduisant SF et/ou puissance
                            steps = int(margin_val // 3)  # nombre d'incréments de 3 dB exploitables
                            min_power = 2.0  # puissance minimale (dBm) permise
                            # Augmenter le débit tant qu'il y a de la marge (et réduire la puissance graduellement)
                            while steps > 0:
                                if node.sf > 7:
                                    node.sf -= 1
                                    if node.tx_power > min_power:
                                        node.tx_power = max(min_power, node.tx_power - 3.0)
                                    steps -= 1
                                else:
                                    # SF déjà au minimum, on réduit seulement la puissance si possible
                                    if node.tx_power > min_power:
                                        node.tx_power = max(min_power, node.tx_power - 3.0)
                                        steps -= 1
                                    else:
                                        break
                        # Réinitialiser l'historique ADR après ajustement
                        node.history.clear()
                        logger.debug(f"ADR ajusté pour le nœud {node.id}: nouveau SF={node.sf}, TxPower={node.tx_power:.1f} dBm")
                    else:
                        logger.debug(f"Requête ADR du nœud {node.id} ignorée (ADR serveur désactivé).")
            return True
        
        elif priority == 2:
            # Événement de mobilité (changement de position du nœud)
            node_id = node.id
            if node.in_transmission:
                # Si le nœud est en cours de transmission, reporter le déplacement à la fin de celle-ci
                next_move_time = node.current_end_time if node.current_end_time is not None else self.current_time
                self.schedule_mobility(node, next_move_time)
            else:
                # Déplacer le nœud à une nouvelle position aléatoire
                node.x = np.random.rand() * self.area_size
                node.y = np.random.rand() * self.area_size
                # Enregistrer l'événement de mobilité dans le log
                self.events_log.append({
                    'event_id': event_id,
                    'node_id': node_id,
                    'sf': node.sf,
                    'start_time': time,
                    'end_time': time,
                    'heard': None,
                    'result': 'Mobility',
                    'energy_J': 0.0,
                    'gateway_id': None
                })
                # Planifier le prochain déplacement dans 10 secondes (si simulation toujours active)
                if self.packets_to_send == 0 or self.packets_sent < self.packets_to_send:
                    self.schedule_mobility(node, time + 10.0)
            return True
        
        # Si autre type d'événement (non prévu)
        return True
    
    def run(self, max_steps: int = None):
        """Exécute la simulation en traitant les événements jusqu'à épuisement ou jusqu'à une limite optionnelle."""
        step_count = 0
        while self.event_queue and self.running:
            self.step()
            step_count += 1
            if max_steps and step_count >= max_steps:
                break
    
    def stop(self):
        """Arrête la simulation en cours."""
        self.running = False
    
    def get_metrics(self) -> dict:
        """Retourne un dictionnaire des métriques actuelles de la simulation."""
        total_sent = self.packets_sent
        delivered = self.packets_delivered
        pdr = delivered / total_sent if total_sent > 0 else 0.0
        avg_delay = self.total_delay / self.delivered_count if self.delivered_count > 0 else 0.0
        return {
            'PDR': pdr,
            'collisions': self.packets_lost_collision,
            'energy_J': self.total_energy_J,
            'avg_delay_s': avg_delay,
            'sf_distribution': {sf: sum(1 for node in self.nodes if node.sf == sf) for sf in range(7, 13)}
        }
    
    def get_events_dataframe(self) -> pd.DataFrame:
        """
        Retourne un DataFrame pandas contenant le log de tous les événements de 
        transmission enrichi des états initiaux et finaux des nœuds.
        """
        if not self.events_log:
            return pd.DataFrame()
        df = pd.DataFrame(self.events_log)
        # Construire un dictionnaire id->nœud pour récupérer les états initiaux/finaux
        node_dict = {node.id: node for node in self.nodes}
        # Ajouter colonnes d'état initial et final du nœud pour chaque événement
        df['initial_x'] = df['node_id'].apply(lambda nid: node_dict[nid].initial_x)
        df['initial_y'] = df['node_id'].apply(lambda nid: node_dict[nid].initial_y)
        df['final_x'] = df['node_id'].apply(lambda nid: node_dict[nid].x)
        df['final_y'] = df['node_id'].apply(lambda nid: node_dict[nid].y)
        df['initial_sf'] = df['node_id'].apply(lambda nid: node_dict[nid].initial_sf)
        df['final_sf'] = df['node_id'].apply(lambda nid: node_dict[nid].sf)
        df['initial_tx_power'] = df['node_id'].apply(lambda nid: node_dict[nid].initial_tx_power)
        df['final_tx_power'] = df['node_id'].apply(lambda nid: node_dict[nid].tx_power)
        # Colonnes d'intérêt dans un ordre lisible
        columns_order = [
            'event_id', 'node_id', 'initial_x', 'initial_y', 'final_x', 'final_y',
            'initial_sf', 'final_sf', 'initial_tx_power', 'final_tx_power',
            'start_time', 'end_time', 'energy_J', 'result', 'gateway_id'
        ]
        for col in columns_order:
            if col not in df.columns:
                df[col] = None
        return df[columns_order]
