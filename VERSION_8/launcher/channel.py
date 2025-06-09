import math
import numpy as np

class Channel:
    """Représente le canal de propagation radio pour LoRa."""
    def __init__(self, frequency_hz: float = 868e6, path_loss_exp: float = 2.7, shadowing_std: float = 6.0):
        """
        Initialise le canal radio avec paramètres de propagation.
        :param frequency_hz: Fréquence en Hz (par défaut 868 MHz).
        :param path_loss_exp: Exposant de perte de parcours (log-distance).
        :param shadowing_std: Écart-type du shadowing (variations aléatoires en dB), 0 pour ignorer.
        """
        self.frequency_hz = frequency_hz
        self.path_loss_exp = path_loss_exp
        self.shadowing_std = shadowing_std  # σ en dB (ex: 6.0 pour environnement urbain/suburbain)

        # Paramètres LoRa (BW 125 kHz, CR 4/5, préambule 8, CRC activé)
        self.bandwidth = 125e3  # 125 kHz
        self.coding_rate = 1    # CR=1 correspond à 4/5 (dans les formules, CR+4 = 5)
        self.preamble_symbols = 8
        self.low_data_rate_threshold = 11  # SF >= 11 -> Low Data Rate Optimization activé

        # Sensibilité approximative par SF (dBm) pour BW=125kHz, CR=4/5
        self.sensitivity_dBm = {
            7: -123,
            8: -126,
            9: -129,
            10: -132,
            11: -134.5,
            12: -137
        }
        # Seuil de capture (différence de RSSI en dB pour qu'un signal plus fort capture la réception)
        self.capture_threshold_dB = 6.0

    def path_loss(self, distance: float) -> float:
        """Calcule la perte de parcours (en dB) pour une distance donnée (m)."""
        if distance <= 0:
            return 0.0
        # Modèle log-distance: PL(d) = PL(d0) + 10*gamma*log10(d/d0), avec d0 = 1 m.
        # Calcul de la perte à 1 m en utilisant le modèle espace libre:
        freq_mhz = self.frequency_hz / 1e6
        # FSPL à d0=1m: 32.45 + 20*log10(freq_MHz) - 60 dB (car 20*log10(0.001 km) = -60)
        pl_d0 = 32.45 + 20 * math.log10(freq_mhz) - 60.0
        # Perte à la distance donnée
        pl = pl_d0 + 10 * self.path_loss_exp * math.log10(max(distance, 1.0) / 1.0)
        return pl

    def compute_rssi(self, tx_power_dBm: float, distance: float) -> float:
        """Calcule le RSSI en dBm à une certaine distance pour une puissance d'émission donnée."""
        # Calcul de la perte de propagation
        loss = self.path_loss(distance)
        # Ajout du shadowing log-normal si activé
        if self.shadowing_std > 0:
            shadow = np.random.normal(0, self.shadowing_std)
            loss += shadow
        # RSSI = P_tx - pertes
        rssi = tx_power_dBm - loss
        return rssi

    def airtime(self, sf: int, payload_size: int = 20) -> float:
        """Calcule le temps de transmission (airtime) en secondes pour un paquet LoRa donné."""
        # Durée d'un symbole (seconde)
        rs = self.bandwidth / (2 ** sf)  # débit symbole (baud)
        ts = 1 / rs  # durée d'un symbole
        # Facteur d'optimisation basse débit (DE)
        de = 1 if sf >= self.low_data_rate_threshold else 0
        # Paramètres du calcul de symboles payload
        payload_bytes = payload_size
        cr_denom = self.coding_rate + 4  # dénominateur lié au coding rate (CR=1 -> 4+1=5)
        # Formule de calcul du nombre de symboles (documentation LoRa)
        numerator = 8 * payload_bytes - 4 * sf + 28 + 16 - 20 * 0  # CRC=1, header explicite (IH=0)
        denominator = 4 * (sf - 2 * de)
        payload_symb_nb = 8 + max(math.ceil(numerator / denominator) * cr_denom, 0)
        t_packet = payload_symb_nb * ts
        return t_packet
