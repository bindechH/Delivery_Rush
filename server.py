"""
Server UDP pour Delivery Rush - Gestion du multijoueur
Gère les connexions clients, la synchronisation des positions et la logique réseau.
"""

import json
import hashlib
import secrets
import logging
import math
import random
import socket
import time
from pathlib import Path

# Configuration du serveur
SERVER_HOST = '0.0.0.0'  # Écoute sur toutes les interfaces
SERVER_PORT = 12345
HEARTBEAT_TIMEOUT = 5  # secondes avant de considérer un client mort
BROADCAST_RATE = 30    # paquets par seconde pour pousser l'état du monde
TICK_SLEEP = 0.003     # petit sleep pour garder la charge raisonnable
BUFFER_SIZE = 4096
DATA_DIR = Path("server_data")
DATA_DIR.mkdir(exist_ok=True)
MISSION_GEN_INTERVAL = 40.0
MAX_SERVER_MISSIONS = 6

# Lieux de mission (copie serveur — doit correspondre à missions.py)
SERVER_LOCATIONS = [
    {"name": "Bibliothèque", "x": 75, "y": 105},
    {"name": "École de cinéma", "x": 98, "y": 132},
    {"name": "Campus Epita", "x": 135, "y": 132},
    {"name": "Université", "x": 167, "y": 105},
    {"name": "Restaurant italien", "x": 234, "y": 105},
    {"name": "Restaurant chinois", "x": 243, "y": 85},
    {"name": "Épicerie", "x": 279, "y": 85},
    {"name": "Pharmacie", "x": 219, "y": 85},
    {"name": "Centre commercial", "x": 261, "y": 132},
    {"name": "Agence de voyage", "x": 266, "y": 161},
    {"name": "Commissariat de police", "x": 285, "y": 183},
    {"name": "News Industry", "x": 286, "y": 203},
    {"name": "Tribunal", "x": 331, "y": 203},
    {"name": "Laboratoire", "x": 327, "y": 183},
    {"name": "Musée", "x": 359, "y": 181},
    {"name": "Fast food", "x": 373, "y": 181},
    {"name": "Hôpital 1", "x": 464, "y": 180},
    {"name": "Hôpital 2", "x": 256, "y": 250},
    {"name": "Hôtel", "x": 214, "y": 227},
    {"name": "Siège Vision Industry", "x": 219, "y": 185},
    {"name": "Siège Corp Industry", "x": 361, "y": 236},
    {"name": "Banque 1", "x": 417, "y": 342},
    {"name": "Banque 2", "x": 333, "y": 250},
    {"name": "Quartier d'affaires 1", "x": 403, "y": 236},
    {"name": "Quartier d'affaires 2", "x": 436, "y": 272},
    {"name": "Quartier d'affaires 3", "x": 412, "y": 307},
    {"name": "Stade", "x": 488, "y": 31},
    {"name": "Parc", "x": 488, "y": 131},
    {"name": "Quartier résidentiel 1", "x": 463, "y": 61},
    {"name": "Quartier résidentiel 2", "x": 475, "y": 28},
    {"name": "Quartier résidentiel 3", "x": 474, "y": 12},
    {"name": "Quartier résidentiel 4", "x": 427, "y": 61},
    {"name": "Quartier résidentiel 5", "x": 407, "y": 46},
    {"name": "Quartier résidentiel 6", "x": 358, "y": 22},
    {"name": "Siège Delivery Rush", "x": 397, "y": 412},
    {"name": "Delivery Dispatch", "x": 472, "y": 379},
    {"name": "Delivery Rush Logistics", "x": 411, "y": 446},
    {"name": "Entrepôt Delivery Rush", "x": 330, "y": 463},
]

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
        self.server_socket.setblocking(False)

        self.clients = {}       # username -> {addr, x, y, angle, car, last_seen}
        self.addr_to_name = {}  # addr -> username

        self.last_broadcast = time.time()

        # Données persistantes (auth + progression)
        self.player_data = self._load_data()

        # Missions générées par le serveur
        self.server_missions = []
        self._mission_counter = 0
        self._last_mission_gen = time.time()

        # Missions coop en attente
        self.coop_waiting = {}  # mission_id -> [usernames qui ont join]

        # Générer les premières missions
        self._generate_missions(MAX_SERVER_MISSIONS)

        logging.info(f"Serveur démarré sur {SERVER_HOST}:{SERVER_PORT}")

    def handle_incoming_data(self):
        """
        Traite les données entrantes des clients
        Gère les messages hello, state, disconnect, login et coop
        """
        addr = None
        try:
            data, addr = self.server_socket.recvfrom(BUFFER_SIZE)
            msg = json.loads(data.decode())
            msg_type = msg.get('type')

            if msg_type == 'hello':
                self.handle_hello(addr, msg)
                return

            if msg_type == 'state':
                self.handle_state(addr, msg)
                return

            if msg_type == 'disconnect':
                self.handle_disconnect(addr, msg)
                return

            if msg_type == 'chat':
                self.handle_chat(addr, msg)
                return

            if msg_type == 'mission_event':
                self.handle_mission_event(addr, msg)
                return

            if msg_type == 'coop_join':
                self.handle_coop_join(addr, msg)
                return

            if msg_type == 'save_progress':
                self.handle_save_progress(addr, msg)
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
        Gère la connexion d'un client avec authentification optionnelle.
        Si password fourni → mode multi (auth requise).
        Sinon → mode casual (pas d'auth).
        """
        username = msg.get('username')
        car = msg.get('car', ('SUPERCAR', 'Black'))
        password = msg.get('password')

        if not username:
            self._send_hello_response(addr, status='denied', reason='invalid_username')
            return

        # Mode authentifié (multi)
        if password is not None:
            if username in self.player_data:
                # Compte existant → vérifier le mot de passe
                stored = self.player_data[username]
                if not self._verify_password(password, stored.get('salt', ''), stored.get('password_hash', '')):
                    self._send_hello_response(addr, status='denied', reason='wrong_password')
                    return
            else:
                # Nouveau compte → enregistrer
                salt = secrets.token_hex(16)
                pw_hash = hashlib.sha256((salt + password).encode()).hexdigest()
                self.player_data[username] = {
                    'salt': salt,
                    'password_hash': pw_hash,
                    'money': 0,
                    'owned_cars': [{'model': 'MICRO', 'color': 'White'}],
                    'car_model': car[0] if isinstance(car, (list, tuple)) else 'MICRO',
                    'car_color': car[1] if isinstance(car, (list, tuple)) and len(car) > 1 else 'White',
                    'completed_missions': 0,
                    'failed_missions': 0,
                }
                self._save_data()
                logging.info(f"Nouveau compte créé : {username}")

        # Vérifier collision de nom si déjà connecté
        if username in self.clients and self.clients[username]['addr'] != addr:
            logging.info(f"Nom '{username}' déjà connecté, rejet de {addr}")
            self._send_hello_response(addr, status='denied', reason='username_taken')
            return

        # Accepter la connexion
        saved_x = 6000
        saved_y = 6000
        saved_angle = 0.0
        saved_car = car
        if username in self.player_data:
            pd = self.player_data[username]
            saved_x = pd.get('last_x', 6000)
            saved_y = pd.get('last_y', 6000)
            saved_angle = pd.get('last_angle', 0.0)
            saved_car_m = pd.get('car_model')
            saved_car_c = pd.get('car_color')
            if saved_car_m and saved_car_c:
                saved_car = (saved_car_m, saved_car_c)

        self.clients[username] = {
            'addr': addr,
            'x': saved_x,
            'y': saved_y,
            'angle': saved_angle,
            'car': saved_car,
            'on_road': True,
            'last_seen': time.time()
        }
        self.addr_to_name[addr] = username

        # Préparer les données joueur pour la réponse
        player_info = None
        if username in self.player_data:
            pd = self.player_data[username]
            player_info = {
                'money': pd.get('money', 0),
                'owned_cars': pd.get('owned_cars', []),
                'car_model': pd.get('car_model', 'MICRO'),
                'car_color': pd.get('car_color', 'White'),
                'completed_missions': pd.get('completed_missions', 0),
                'failed_missions': pd.get('failed_missions', 0),
                'last_x': pd.get('last_x', 6000),
                'last_y': pd.get('last_y', 6000),
                'last_angle': pd.get('last_angle', 0.0),
                'total_distance': pd.get('total_distance', 0.0),
            }

        logging.info(f"Connexion : {username} @ {addr}" + (" (authentifié)" if password else ""))
        self._send_hello_response(addr, status='ok', player_data=player_info)

    def _send_hello_response(self, addr, status='ok', reason=None, player_data=None):
        """Envoie la réponse au handshake hello d'un client"""
        payload = {'type': 'hello_response', 'status': status}
        if reason:
            payload['reason'] = reason
        if player_data:
            payload['player_data'] = player_data
        # Envoyer aussi la liste des missions serveur
        if status == 'ok':
            payload['missions'] = [m for m in self.server_missions if m.get('status') == 'available']
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
        client['on_road'] = msg.get('on_road', True)
        new_car = msg.get('car', client['car'])
        client['car'] = new_car
        client['last_seen'] = time.time()  # Timestamp de dernière activité

        # Persist car change to player data
        if username in self.player_data:
            car_m = new_car[0] if isinstance(new_car, (list, tuple)) else new_car
            car_c = new_car[1] if isinstance(new_car, (list, tuple)) and len(new_car) > 1 else 'White'
            if self.player_data[username].get('car_model') != car_m or self.player_data[username].get('car_color') != car_c:
                self.player_data[username]['car_model'] = car_m
                self.player_data[username]['car_color'] = car_c

    def handle_disconnect(self, addr, msg):
        """Gère la déconnexion propre d'un client, sauvegarde la position."""
        username = msg.get('username') or self.addr_to_name.get(addr)
        if not username or username not in self.clients:
            return
        client_data = self.clients[username]
        client_addr = client_data['addr']
        # Sauvegarder la dernière position et voiture
        if username in self.player_data:
            self.player_data[username]["last_x"] = client_data.get("x", 0)
            self.player_data[username]["last_y"] = client_data.get("y", 0)
            self.player_data[username]["last_angle"] = client_data.get("angle", 0)
            car = client_data.get("car")
            if car:
                self.player_data[username]["car_model"] = car[0] if isinstance(car, (list, tuple)) else car
                self.player_data[username]["car_color"] = car[1] if isinstance(car, (list, tuple)) and len(car) > 1 else 'White'
            self._save_player(username)
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
            client_data = self.clients[username]
            addr = client_data['addr']
            # Sauvegarder position et voiture avant suppression
            if username in self.player_data:
                self.player_data[username]["last_x"] = client_data.get("x", 0)
                self.player_data[username]["last_y"] = client_data.get("y", 0)
                self.player_data[username]["last_angle"] = client_data.get("angle", 0)
                car = client_data.get("car")
                if car:
                    self.player_data[username]["car_model"] = car[0] if isinstance(car, (list, tuple)) else car
                    self.player_data[username]["car_color"] = car[1] if isinstance(car, (list, tuple)) and len(car) > 1 else 'White'
                self._save_player(username)
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
                'car': data['car'],
                'on_road': data.get('on_road', True),
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

    def handle_chat(self, addr, msg):
        """Relaye un message de chat à tous les autres clients."""
        username = msg.get('username') or self.addr_to_name.get(addr)
        if not username or username not in self.clients:
            return
        message = msg.get('message', '')[:200]
        logging.info(f"Chat [{username}]: {message}")
        packet = json.dumps({
            'type': 'chat_broadcast',
            'username': username,
            'message': message
        }).encode()
        for uname, data in list(self.clients.items()):
            if uname != username:
                try:
                    self.server_socket.sendto(packet, data['addr'])
                except Exception:
                    pass

    def handle_mission_event(self, addr, msg):
        """Relaye un événement de mission à tous les autres clients."""
        username = msg.get('username') or self.addr_to_name.get(addr)
        if not username or username not in self.clients:
            return
        event = msg.get('event', '')
        mission_data = msg.get('data', {})
        logging.info(f"Mission event [{username}]: {event}")

        # Mettre à jour la progression côté serveur si authentifié
        if event == 'mission_complete' and username in self.player_data:
            reward = mission_data.get('reward', 0)
            self.player_data[username]['money'] = self.player_data[username].get('money', 0) + reward
            self.player_data[username]['completed_missions'] = self.player_data[username].get('completed_missions', 0) + 1
            self._save_data()
        elif event == 'mission_fail' and username in self.player_data:
            self.player_data[username]['failed_missions'] = self.player_data[username].get('failed_missions', 0) + 1
            self._save_data()

        packet = json.dumps({
            'type': 'mission_broadcast',
            'username': username,
            'event': event,
            'data': mission_data
        }).encode()
        for uname, data in list(self.clients.items()):
            if uname != username:
                try:
                    self.server_socket.sendto(packet, data['addr'])
                except Exception:
                    pass

    def handle_coop_join(self, addr, msg):
        """Gère un joueur qui rejoint une mission coop."""
        username = self.addr_to_name.get(addr)
        if not username:
            return
        mission_id = msg.get('mission_id')
        if mission_id is None:
            return

        # Trouver la mission serveur
        mission = None
        for m in self.server_missions:
            if m['id'] == mission_id and m.get('coop'):
                mission = m
                break
        if not mission:
            return

        if mission_id not in self.coop_waiting:
            self.coop_waiting[mission_id] = []
        if username not in self.coop_waiting[mission_id]:
            self.coop_waiting[mission_id].append(username)
            logging.info(f"Coop join: {username} -> mission {mission_id} ({len(self.coop_waiting[mission_id])}/{mission.get('required_players', 2)})")

        required = mission.get('required_players', 2)
        if len(self.coop_waiting[mission_id]) >= required:
            # Mission coop activée !
            participants = self.coop_waiting.pop(mission_id)
            mission['status'] = 'active'
            mission['participants'] = participants
            logging.info(f"Coop mission {mission_id} activée pour : {participants}")
            # Notifier les participants
            coop_packet = json.dumps({
                'type': 'coop_activated',
                'mission': mission,
                'participants': participants,
            }).encode()
            for uname in participants:
                if uname in self.clients:
                    try:
                        self.server_socket.sendto(coop_packet, self.clients[uname]['addr'])
                    except Exception:
                        pass

    def handle_save_progress(self, addr, msg):
        """Sauvegarde la progression d'un joueur (mode multi)."""
        username = self.addr_to_name.get(addr)
        if not username or username not in self.player_data:
            return
        progress = msg.get('data', {})
        pd = self.player_data[username]
        for key in ('money', 'owned_cars', 'car_model', 'car_color', 'completed_missions', 'failed_missions', 'total_distance', 'last_x', 'last_y', 'last_angle'):
            if key in progress:
                pd[key] = progress[key]
        self._save_player(username)
        logging.info(f"Progression sauvegardée pour {username}")

    # === DATA PERSISTENCE ===

    def _load_data(self):
        """Charge les données persistantes depuis server_data/ (un fichier par joueur)."""
        data = {}
        for f in DATA_DIR.glob("*.json"):
            try:
                pdata = json.loads(f.read_text())
                username = f.stem
                data[username] = pdata
            except Exception as e:
                logging.error(f"Erreur chargement {f}: {e}")
        logging.info(f"Données chargées : {len(data)} joueurs")
        return data

    def _save_data(self):
        """Sauvegarde les données persistantes (un fichier par joueur)."""
        for username, pdata in self.player_data.items():
            safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in username)
            fpath = DATA_DIR / f"{safe_name}.json"
            try:
                fpath.write_text(json.dumps(pdata, indent=2, ensure_ascii=False))
            except Exception as e:
                logging.error(f"Erreur sauvegarde {username}: {e}")

    def _save_player(self, username):
        """Sauvegarde un seul joueur."""
        if username not in self.player_data:
            return
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in username)
        fpath = DATA_DIR / f"{safe_name}.json"
        try:
            fpath.write_text(json.dumps(self.player_data[username], indent=2, ensure_ascii=False))
        except Exception as e:
            logging.error(f"Erreur sauvegarde {username}: {e}")

    @staticmethod
    def _verify_password(password, salt, stored_hash):
        """Vérifie un mot de passe contre le hash stocké."""
        return hashlib.sha256((salt + password).encode()).hexdigest() == stored_hash

    # === SERVER MISSION GENERATION ===

    def _generate_missions(self, count=1):
        """Génère des missions côté serveur."""
        for _ in range(count):
            if len([m for m in self.server_missions if m.get('status') == 'available']) >= MAX_SERVER_MISSIONS:
                break
            self._mission_counter += 1
            locations = random.sample(SERVER_LOCATIONS, 2)
            pickup = dict(locations[0])
            delivery = dict(locations[1])

            dist = math.hypot(delivery['x'] - pickup['x'], delivery['y'] - pickup['y'])
            dist_factor = max(0.5, dist / 4000.0)

            # 20% chance de coop si 2+ joueurs connectés
            is_coop = len(self.clients) >= 2 and random.random() < 0.2
            mission_type = random.choices(['standard', 'express', 'chain'], weights=[60, 25, 15], k=1)[0]

            if mission_type == 'express':
                reward = int(random.uniform(200, 500) * dist_factor)
                time_limit = random.uniform(45, 90) * max(0.7, dist_factor)
            elif mission_type == 'chain':
                reward = int(random.uniform(150, 350) * dist_factor)
                time_limit = random.uniform(90, 150) * max(0.7, dist_factor)
            else:
                reward = int(random.uniform(100, 250) * dist_factor)
                time_limit = random.uniform(120, 240) * max(0.7, dist_factor)

            if is_coop:
                reward = int(reward * 1.5)  # Bonus récompense coop

            mission = {
                'id': self._mission_counter,
                'type': mission_type,
                'pickup': pickup,
                'delivery': delivery,
                'reward': reward,
                'time_limit': int(time_limit),
                'status': 'available',
                'coop': is_coop,
                'required_players': 2 if is_coop else 1,
            }
            self.server_missions.append(mission)

    def _tick_missions(self):
        """Met à jour les missions serveur (régénération)."""
        now = time.time()
        if now - self._last_mission_gen >= MISSION_GEN_INTERVAL:
            self._last_mission_gen = now
            # Supprimer les missions expirées
            self.server_missions = [m for m in self.server_missions if m.get('status') in ('available', 'active')]
            self._generate_missions(2)
            # Broadcast la liste mise à jour
            self._broadcast_missions()

    def _broadcast_missions(self):
        """Envoie la liste des missions à tous les clients."""
        available = [m for m in self.server_missions if m.get('status') == 'available']
        packet = json.dumps({'type': 'mission_list', 'missions': available}).encode()
        for uname, data in list(self.clients.items()):
            try:
                self.server_socket.sendto(packet, data['addr'])
            except Exception:
                pass

    def run(self):
        """
        Boucle principale du serveur - traite les connexions et les données
        Gère les nouveaux clients, les déconnexions et la diffusion des positions
        """
        logging.info("En attente de connexions clients...")
        try:
            while True:
                self.handle_incoming_data()
                self.check_disconnections()
                self.broadcast_positions()
                self._tick_missions()
                time.sleep(TICK_SLEEP)
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