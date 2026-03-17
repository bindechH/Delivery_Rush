"""
Module réseau client pour Delivery Rush
Gère la connexion UDP au serveur, l'envoi/réception des positions et la synchronisation multijoueur.
Inclut la synchronisation des missions, le chat et l'interpolation.
"""

import json
import socket
import time

# Configuration réseau
BUFFER_SIZE = 4096  # Taille maximale des paquets UDP
HANDSHAKE_TIMEOUT = 1.0  # Timeout pour le handshake initial
MAX_RECV_BATCH = 10  # Évite une boucle infinie si trop de paquets
INTERP_DELAY = 0.1  # Délai d'interpolation en secondes


class InterpolatedPlayer:
    """Stocke les positions passées d'un joueur distant pour interpolation lisse."""

    def __init__(self):
        self.states = []  # Liste de (timestamp, x, y, angle)
        self.x = 0
        self.y = 0
        self.angle = 0
        self.car = ('SUPERCAR', 'Black')
        self.on_road = True

    def add_state(self, x, y, angle, car=None, on_road=True):
        t = time.monotonic()
        self.states.append((t, x, y, angle))
        if car:
            self.car = car
        self.on_road = on_road
        # Garder seulement les 10 derniers états
        if len(self.states) > 10:
            self.states = self.states[-10:]

    def interpolate(self):
        """Interpole la position entre les deux derniers états."""
        now = time.monotonic()
        render_time = now - INTERP_DELAY

        # Trouver les deux états qui encadrent render_time
        if len(self.states) < 2:
            if self.states:
                _, self.x, self.y, self.angle = self.states[-1]
            return

        # Chercher les bons états pour interpolation
        s0 = self.states[0]
        s1 = self.states[1]
        for i in range(len(self.states) - 1):
            if self.states[i + 1][0] >= render_time:
                s0 = self.states[i]
                s1 = self.states[i + 1]
                break
        else:
            # render_time est après tous les états, utiliser les deux derniers
            s0 = self.states[-2]
            s1 = self.states[-1]

        t0, x0, y0, a0 = s0
        t1, x1, y1, a1 = s1
        dt = t1 - t0
        if dt <= 0:
            self.x, self.y, self.angle = x1, y1, a1
            return

        t = max(0.0, min(1.0, (render_time - t0) / dt))
        self.x = x0 + (x1 - x0) * t
        self.y = y0 + (y1 - y0) * t
        # Interpolation angulaire (plus court chemin)
        da = (a1 - a0 + 180) % 360 - 180
        self.angle = (a0 + da * t) % 360

    def to_dict(self):
        return {
            'x': self.x,
            'y': self.y,
            'angle': self.angle,
            'car': self.car,
            'on_road': self.on_road,
        }


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
        # Interpolation des joueurs distants
        self.interpolated_players = {}  # {username: InterpolatedPlayer}
        # Chat et missions réseau
        self.chat_messages = []
        self.pending_mission_data = None
        self.server_missions = []      # Missions générées par le serveur
        self.server_player_data = None # Données joueur reçues du serveur
        self.coop_notifications = []   # Notifications coop

    def _reset_socket(self):
        """Réinitialise le socket UDP pour une nouvelle connexion"""
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def connect(self, username, car, password=None):
        """
        Établit la connexion au serveur via handshake UDP.
        Si password fourni, le serveur authentifie/enregistre le compte.
        Retourne (succès, raison).
        """
        self.username = username
        self.car = car
        self._reset_socket()
        self.sock.settimeout(HANDSHAKE_TIMEOUT)

        hello = {
            'type': 'hello',
            'username': username,
            'car': car,
            'version': 1,
        }
        if password is not None:
            hello['password'] = password

        try:
            self.sock.sendto(json.dumps(hello).encode(), (self.server_ip, self.server_port))
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

        # Récupérer les données joueur et missions du serveur
        self.server_player_data = resp.get('player_data')
        self.server_missions = resp.get('missions', [])

        print(f"Connecté au serveur en tant que {username}")
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
            'car': player.car,
            'on_road': getattr(player, 'on_road', True)
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

    def send_save_progress(self, progress_dict):
        """Send player progress data to the server for saving."""
        if not self.sock or not self.username:
            return
        pkt = json.dumps({
            'type': 'save_progress',
            'username': self.username,
            'data': progress_dict
        }).encode()
        try:
            self.sock.sendto(pkt, (self.server_ip, self.server_port))
        except Exception as e:
            print(f"Envoi de la progression échoué : {e}")

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
                msg_type = msg.get('type')
                if msg_type == 'state_broadcast':
                    last_players = msg.get('players', {})  # Positions de tous les joueurs
                elif msg_type == 'control' and msg.get('code') == 'need_hello':
                    print("Le serveur a demandé une reconnexion")
                    return False, {}  # Le serveur demande une reconnexion
                elif msg_type == 'chat_broadcast':
                    username = msg.get('username', '?')
                    message = msg.get('message', '')
                    self.chat_messages.append((time.monotonic(), username, message))
                    # Garder les 50 derniers messages
                    if len(self.chat_messages) > 50:
                        self.chat_messages = self.chat_messages[-50:]
                elif msg_type == 'mission_broadcast':
                    self.pending_mission_data = msg.get('data')
                elif msg_type == 'mission_list':
                    self.server_missions = msg.get('missions', [])
                elif msg_type == 'coop_activated':
                    self.coop_notifications.append(msg)
        except BlockingIOError:
            pass  # Pas de données disponibles (normal en mode non-bloquant)
        except Exception as e:
            print(f"Réception des positions échouée : {e}")
            return False, {}

        if last_players is None:
            return None, {}  # Aucune donnée reçue

        # Filtrer pour exclure notre propre position
        filtered = {k: v for k, v in last_players.items() if k != self.username}

        # Mettre à jour l'interpolation
        for username, data in filtered.items():
            if username not in self.interpolated_players:
                self.interpolated_players[username] = InterpolatedPlayer()
            ip = self.interpolated_players[username]
            if isinstance(data, dict):
                ip.add_state(data.get('x', 0), data.get('y', 0), data.get('angle', 0), data.get('car'), data.get('on_road', True))
            else:
                ip.add_state(data[0] if len(data) > 0 else 0, data[1] if len(data) > 1 else 0, 0)

        # Supprimer les joueurs déconnectés
        for username in list(self.interpolated_players.keys()):
            if username not in last_players:
                del self.interpolated_players[username]

        return True, filtered

    def get_interpolated_players(self):
        """Retourne les positions interpolées de tous les joueurs distants."""
        result = {}
        for username, ip in self.interpolated_players.items():
            ip.interpolate()
            result[username] = ip.to_dict()
        return result

    def send_mission_event(self, event_type, mission_data=None):
        """
        Envoie un événement mission au serveur.
        event_type: 'mission_complete', 'mission_accept', 'mission_fail'
        """
        if not self.sock or not self.username:
            return
        pkt = json.dumps({
            'type': 'mission_event',
            'username': self.username,
            'event': event_type,
            'data': mission_data or {}
        }).encode()
        try:
            self.sock.sendto(pkt, (self.server_ip, self.server_port))
        except Exception as e:
            print(f"Envoi événement mission échoué : {e}")

    def send_chat(self, message):
        """Envoie un message de chat au serveur."""
        if not self.sock or not self.username:
            return
        pkt = json.dumps({
            'type': 'chat',
            'username': self.username,
            'message': message[:200]
        }).encode()
        try:
            self.sock.sendto(pkt, (self.server_ip, self.server_port))
        except Exception as e:
            print(f"Envoi chat échoué : {e}")

    def send_coop_join(self, mission_id):
        """Envoie une demande de participation à une mission coop."""
        if not self.sock or not self.username:
            return
        pkt = json.dumps({
            'type': 'coop_join',
            'username': self.username,
            'mission_id': mission_id,
        }).encode()
        try:
            self.sock.sendto(pkt, (self.server_ip, self.server_port))
        except Exception as e:
            print(f"Envoi coop_join échoué : {e}")

    def send_save_progress(self, progress_data):
        """Envoie la progression du joueur au serveur pour sauvegarde."""
        if not self.sock or not self.username:
            return
        pkt = json.dumps({
            'type': 'save_progress',
            'username': self.username,
            'data': progress_data,
        }).encode()
        try:
            self.sock.sendto(pkt, (self.server_ip, self.server_port))
        except Exception as e:
            print(f"Envoi save_progress échoué : {e}")

    def close(self):
        """Ferme proprement la connexion réseau"""
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
        self.sock = None