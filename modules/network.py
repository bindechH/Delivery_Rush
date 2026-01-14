import json
import socket

# Network configuration
BUFFER_SIZE = 2048
HANDSHAKE_TIMEOUT = 1.0
MAX_RECV_BATCH = 5  # Drain a few packets per frame to stay current


class NetworkClient:
    def __init__(self, server_ip, server_port):
        self.server_ip = server_ip
        self.server_port = server_port
        self.sock = None
        self.username = None
        self.car = None

    def _reset_socket(self):
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def connect(self, username, car):
        """Perform hello handshake. Returns (success, reason)."""
        self.username = username
        self.car = car
        self._reset_socket()
        self.sock.settimeout(HANDSHAKE_TIMEOUT)

        hello = json.dumps({
            'type': 'hello',
            'username': username,
            'car': car,
            'version': 1
        }).encode()

        try:
            self.sock.sendto(hello, (self.server_ip, self.server_port))
            data, _ = self.sock.recvfrom(BUFFER_SIZE)
            resp = json.loads(data.decode())
        except socket.timeout:
            print("[NET] Handshake timeout")
            self.close()
            return False, 'timeout'
        except Exception as e:
            print(f"[NET] Handshake failed: {e}")
            self.close()
            return False, 'error'

        if resp.get('type') != 'hello_response':
            print(f"[NET] Bad handshake response: {resp}")
            self.close()
            return False, 'bad_response'

        status = resp.get('status')
        if status != 'ok':
            reason = resp.get('reason', 'denied')
            print(f"[NET] Handshake denied: {reason}")
            self.close()
            return False, reason

        print(f"[NET] Connected to server as {username}")
        # Switch to non-blocking after handshake
        self.sock.setblocking(False)
        return True, 'ok'

    def send_state(self, player):
        if not self.sock or not player:
            return
        pkt = json.dumps({
            'type': 'state',
            'username': self.username,
            'x': player.x,
            'y': player.y,
            'car': player.car
        }).encode()
        try:
            self.sock.sendto(pkt, (self.server_ip, self.server_port))
        except Exception as e:
            print(f"[NET] Send failed: {e}")

    def receive_states(self):
        """Returns (success_flag, positions_dict) where success_flag can be True, False, or None (no data)."""
        if not self.sock:
            return False, {}

        last_players = None
        try:
            for _ in range(MAX_RECV_BATCH):
                data, _ = self.sock.recvfrom(BUFFER_SIZE)
                msg = json.loads(data.decode())
                if msg.get('type') == 'state_broadcast':
                    last_players = msg.get('players', {})
                elif msg.get('type') == 'control' and msg.get('code') == 'need_hello':
                    print("[NET] Server requested re-hello")
                    return False, {}
        except BlockingIOError:
            pass
        except Exception as e:
            print(f"[NET] Receive failed: {e}")
            return False, {}

        if last_players is None:
            return None, {}

        filtered = {k: v for k, v in last_players.items() if k != self.username}
        return True, filtered

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
        self.sock = None