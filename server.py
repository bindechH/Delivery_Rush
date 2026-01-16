"""
Server UDP pour Delivery Rush - Gestion du multijoueur
Gère les connexions clients, la synchronisation des positions et la logique réseau.
"""

import json
import logging
import socket
import time

# Configuration du serveur
SERVER_HOST = '0.0.0.0'  # Écoute sur toutes les interfaces
SERVER_PORT = 12345
HEARTBEAT_TIMEOUT = 5  # secondes avant de considérer un client mort
BROADCAST_RATE = 30    # paquets par seconde pour pousser l'état du monde
TICK_SLEEP = 0.003     # petit sleep pour garder la charge raisonnable
BUFFER_SIZE = 2048

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class DeliveryRushServer:
    """
    Serveur principal pour Delivery Rush - Gestion du multijoueur UDP
    Gère les connexions clients, les positions et la synchronisation en temps réel
    """

    def __init__(self):
        """Initialisation du serveur UDP"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_socket.bind((SERVER_HOST, SERVER_PORT))
        self.server_socket.setblocking(False)  # Mode non-bloquant

        # Structures de données pour les clients
        self.clients = {}  # username -> {addr, x, y, angle, car, last_seen}
        self.addr_to_name = {}  # addr -> username pour nettoyage rapide

        self.last_broadcast = time.time()  # Timestamp du dernier broadcast

        logging.info(f"Serveur démarré sur {SERVER_HOST}:{SERVER_PORT}")

    def handle_incoming_data(self):
        """
        Traite les données entrantes des clients
        Gère les messages hello, state et disconnect
        """
        addr = None
        try:
            data, addr = self.server_socket.recvfrom(BUFFER_SIZE)
            msg = json.loads(data.decode())
            msg_type = msg.get('type')

            if msg_type == 'hello':  # Nouveau client ou reconnexion
                self.handle_hello(addr, msg)
                return

            if msg_type == 'state':  # Mise à jour de position d'un client
                self.handle_state(addr, msg)
                return

            if msg_type == 'disconnect':  # Client qui se déconnecte
                self.handle_disconnect(addr, msg)
                return

        except BlockingIOError:
            return  # Pas de données disponibles
        except ConnectionResetError as e:
            logging.warning(f"Connexion réinitialisée depuis {addr or '<unknown>'}: {e}")
        except json.JSONDecodeError as e:
            logging.warning(f"JSON invalide reçu de {addr or '<unknown>'}: {e}")
        except Exception as e:
            logging.error(f"Erreur lors du traitement des données de {addr or '<unknown>'}: {e}")

    def handle_hello(self, addr, msg):
        """
        Gère la connexion initiale d'un client (handshake)
        Vérifie le nom d'utilisateur et accepte/refuse la connexion
        """
        username = msg.get('username')
        car = msg.get('car', ('SUPERCAR', 'Black'))  # Voiture par défaut

        if not username:
            self._send_hello_response(addr, status='denied', reason='invalid_username')
            return

        # Vérifier les collisions de noms d'utilisateur
        if username in self.clients and self.clients[username]['addr'] != addr:
            logging.info(f"Nom d'utilisateur '{username}' déjà pris, rejet de {addr}")
            self._send_hello_response(addr, status='denied', reason='username_taken')
            return

        # Accepter la connexion (nouveau client ou reconnexion)
        self.clients[username] = {
            'addr': addr,
            'x': msg.get('x', 6000),  # Position X par défaut
            'y': msg.get('y', 6000),  # Position Y par défaut
            'angle': msg.get('angle', 0.0),  # Angle par défaut
            'car': car,  # Modèle et couleur de voiture
            'last_seen': time.time()  # Timestamp de dernière activité
        }
        self.addr_to_name[addr] = username
        logging.info(f"Connexion établie : {username} @ {addr}")
        self._send_hello_response(addr, status='ok')

    def _send_hello_response(self, addr, status='ok', reason=None):
        """Envoie la réponse au handshake hello d'un client"""
        payload = {'type': 'hello_response', 'status': status}
        if reason:
            payload['reason'] = reason
        try:
            self.server_socket.sendto(json.dumps(payload).encode(), addr)
        except Exception as e:
            logging.error(f"Échec d'envoi de hello_response à {addr}: {e}")

    def handle_state(self, addr, msg):
        """
        Met à jour l'état d'un client (position, angle, voiture)
        Gère aussi les changements d'adresse IP/port (NAT traversal)
        """
        username = msg.get('username')
        if not username or username not in self.clients:
            # Client non enregistré ou état perdu : demander un re-hello
            self._send_control(addr, 'need_hello')
            return

        client = self.clients[username]
        if client['addr'] != addr:
            # Mise à jour de l'adresse si NAT/port changé (reconnexion rapide)
            old_addr = client['addr']
            self.addr_to_name.pop(old_addr, None)
            client['addr'] = addr
            self.addr_to_name[addr] = username
            logging.info(f"Adresse mise à jour pour {username}: {old_addr} -> {addr}")

        # Mise à jour des données du client
        client['x'] = msg.get('x', client['x'])
        client['y'] = msg.get('y', client['y'])
        client['angle'] = msg.get('angle', client.get('angle', 0.0))
        client['car'] = msg.get('car', client['car'])
        client['last_seen'] = time.time()  # Timestamp de dernière activité

    def handle_disconnect(self, addr, msg):
        """Gère la déconnexion propre d'un client"""
        username = msg.get('username') or self.addr_to_name.get(addr)
        if not username or username not in self.clients:
            return
        client_addr = self.clients[username]['addr']
        logging.info(f"Déconnexion : {username} ({client_addr})")
        self.addr_to_name.pop(client_addr, None)
        self.clients.pop(username, None)

    def _send_control(self, addr, code):
        """Envoie un message de contrôle à un client (ex: need_hello)"""
        payload = {'type': 'control', 'code': code}
        try:
            self.server_socket.sendto(json.dumps(payload).encode(), addr)
        except Exception as e:
            logging.error(f"Échec d'envoi du contrôle '{code}' à {addr}: {e}")

    def check_disconnections(self):
        """
        Vérifie les clients inactifs et les déconnecte automatiquement
        Utilise HEARTBEAT_TIMEOUT pour déterminer l'inactivité
        """
        now = time.time()
        to_drop = []
        for username, data in list(self.clients.items()):
            if now - data['last_seen'] > HEARTBEAT_TIMEOUT:
                to_drop.append(username)

        for username in to_drop:
            addr = self.clients[username]['addr']
            logging.info(f"Suppression de {username} ({addr}) - timeout")
            self.addr_to_name.pop(addr, None)
            self.clients.pop(username, None)

    def broadcast_positions(self):
        """
        Diffuse les positions de tous les joueurs à tous les clients connectés
        Respecte le taux BROADCAST_RATE pour éviter la surcharge réseau
        """
        if time.time() - self.last_broadcast < 1.0 / BROADCAST_RATE:
            return  # Pas encore temps de broadcaster

        if not self.clients:
            return  # Aucun client connecté

        # Construction du paquet avec toutes les positions
        players = {
            username: {
                'x': data['x'],
                'y': data['y'],
                'angle': data.get('angle', 0.0),
                'car': data['car']
            }
            for username, data in self.clients.items()
        }

        packet = json.dumps({'type': 'state_broadcast', 'players': players}).encode()
        # Envoi à tous les clients
        for username, data in list(self.clients.items()):
            addr = data['addr']
            try:
                self.server_socket.sendto(packet, addr)
            except Exception as e:
                logging.error(f"Échec d'envoi du broadcast à {username} ({addr}): {e}")

        self.last_broadcast = time.time()

    def run(self):
        """
        Boucle principale du serveur - traite les connexions et les données
        Gère les nouveaux clients, les déconnexions et la diffusion des positions
        """
        logging.info("En attente de connexions clients...")
        try:
            while True:
                self.handle_incoming_data()    # Traiter les messages entrants
                self.check_disconnections()    # Nettoyer les clients inactifs
                self.broadcast_positions()     # Diffuser les positions
                time.sleep(TICK_SLEEP)         # Pause pour contrôler l'usage CPU
        except KeyboardInterrupt:
            logging.info("Arrêt du serveur...")
        finally:
            self.server_socket.close()  # Fermeture propre du socket


def main():
    """Fonction principale - crée et lance le serveur"""
    server = DeliveryRushServer()
    server.run()


# Point d'entrée du programme serveur
if __name__ == "__main__":
    main()