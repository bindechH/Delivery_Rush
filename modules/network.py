"""
Module réseau client pour Delivery Rush
Gère la connexion UDP au serveur, l'envoi/réception des positions et la synchronisation multijoueur.
"""

import json
import socket

# Configuration réseau
BUFFER_SIZE = 2048  # Taille maximale des paquets UDP
HANDSHAKE_TIMEOUT = 1.0  # Timeout pour le handshake initial
MAX_RECV_BATCH = 5  # Évite une boucle infinie si trop de paquets


class NetworkClient:
    """
    Client réseau UDP pour la communication avec le serveur
    Gère la connexion, l'authentification et l'échange de données de jeu
    """

    def __init__(self, server_ip, server_port):
        """Initialisation du client réseau"""
        self.server_ip = server_ip
        self.server_port = server_port
        self.sock = None  # Socket UDP (None si déconnecté)
        self.username = None  # Nom d'utilisateur du joueur
        self.car = None  # Voiture du joueur (modèle, couleur)

    def _reset_socket(self):
        """Réinitialise le socket UDP pour une nouvelle connexion"""
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def connect(self, username, car):
        """
        Établit la connexion au serveur via handshake UDP
        Retourne (succès, raison) où succès est True/False
        """
        self.username = username
        self.car = car
        self._reset_socket()
        self.sock.settimeout(HANDSHAKE_TIMEOUT)

        # Construction et envoi du message hello
        hello = json.dumps({
            'type': 'hello',
            'username': username,
            'car': car,
            'version': 1  # Version du protocole
        }).encode()

        try:
            self.sock.sendto(hello, (self.server_ip, self.server_port))
            data, _ = self.sock.recvfrom(BUFFER_SIZE)
            resp = json.loads(data.decode())
        except socket.timeout:
            print("Délai d'attente dépassé lors de la vérification")
            self.close()
            return False, 'timeout'
        except Exception as e:
            print(f"Vérification échouée : {e}")
            self.close()
            return False, 'error'

        # Vérification de la réponse du serveur
        if resp.get('type') != 'hello_response':
            print(f"Mauvaise réponse de vérification : {resp}")
            self.close()
            return False, 'bad_response'

        status = resp.get('status')
        if status != 'ok':
            reason = resp.get('reason', 'denied')
            print(f"Vérification refusée : {reason}")
            self.close()
            return False, reason

        print(f"Connecté au serveur en tant que {username}")
        # Passage en mode non-bloquant après connexion réussie
        self.sock.setblocking(False)
        return True, 'ok'

    def send_state(self, player):
        """
        Envoie l'état du joueur (position, angle, voiture) au serveur
        Utilisé pour synchroniser la position en multijoueur
        """
        if not self.sock or not player:
            return
        pkt = json.dumps({
            'type': 'state',
            'username': self.username,
            'x': player.x,
            'y': player.y,
            'angle': getattr(player, 'angle', 0.0),
            'car': player.car
        }).encode()
        try:
            self.sock.sendto(pkt, (self.server_ip, self.server_port))
        except Exception as e:
            print(f"Envoi de l'état échoué : {e}")

    def send_disconnect(self, reason='client_disconnect'):
        """
        Informe le serveur de la déconnexion du client
        reason peut être 'menu_quit', 'esc_menu', 'net_error', etc.
        """
        if not self.sock or not self.username:
            return
        pkt = json.dumps({
            'type': 'disconnect',
            'username': self.username,
            'reason': reason
        }).encode()
        try:
            self.sock.sendto(pkt, (self.server_ip, self.server_port))
        except Exception as e:
            print(f"Déconnexion échouée : {e}")

    def receive_states(self):
        """
        Reçoit les positions des autres joueurs depuis le serveur
        Retourne (succès, positions_dict) où positions_dict contient {username: {x, y, angle, car}}
        """
        if not self.sock:
            return False, {}

        last_players = None
        try:
            # Traiter jusqu'à MAX_RECV_BATCH paquets pour éviter les blocages
            for _ in range(MAX_RECV_BATCH):
                data, _ = self.sock.recvfrom(BUFFER_SIZE)
                msg = json.loads(data.decode())
                if msg.get('type') == 'state_broadcast':
                    last_players = msg.get('players', {})  # Positions de tous les joueurs
                elif msg.get('type') == 'control' and msg.get('code') == 'need_hello':
                    print("Le serveur a demandé une reconnexion")
                    return False, {}  # Le serveur demande une reconnexion
        except BlockingIOError:
            pass  # Pas de données disponibles (normal en mode non-bloquant)
        except Exception as e:
            print(f"Réception des positions échouée : {e}")
            return False, {}

        if last_players is None:
            return None, {}  # Aucune donnée reçue

        # Filtrer pour exclure notre propre position
        filtered = {k: v for k, v in last_players.items() if k != self.username}
        return True, filtered

    def close(self):
        """Ferme proprement la connexion réseau"""
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
        self.sock = None