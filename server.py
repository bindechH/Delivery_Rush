import json
import logging
import socket
import time

# Server configuration
# Bind to all interfaces so Hamachi/remote clients can reach us. To force a
# specific IP (ex: your Hamachi address), set SERVER_HOST to that value.
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 12345
HEARTBEAT_TIMEOUT = 5  # seconds before considering a client dead
BROADCAST_RATE = 30    # packets per second to push world state
TICK_SLEEP = 0.003     # small sleep to keep CPU reasonable
BUFFER_SIZE = 2048

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class DeliveryRushServer:
    def __init__(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_socket.bind((SERVER_HOST, SERVER_PORT))
        self.server_socket.setblocking(False)

        # username -> data; data contains addr, x, y, car, last_seen
        self.clients = {}
        # addr -> username for quick cleanup
        self.addr_to_name = {}

        self.last_broadcast = time.time()

        logging.info(f"Server started on {SERVER_HOST}:{SERVER_PORT}")

    def handle_incoming_data(self):
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

        except BlockingIOError:
            return
        except ConnectionResetError as e:
            logging.warning(f"Connection reset from {addr or '<unknown>'}: {e}")
        except json.JSONDecodeError as e:
            logging.warning(f"Invalid JSON received from {addr or '<unknown>'}: {e}")
        except Exception as e:
            logging.error(f"Error handling data from {addr or '<unknown>'}: {e}")

    def handle_hello(self, addr, msg):
        username = msg.get('username')
        car = msg.get('car', ('SUPERCAR TOPDOWN', 'Black'))

        if not username:
            self._send_hello_response(addr, status='denied', reason='invalid_username')
            return

        if username in self.clients and self.clients[username]['addr'] != addr:
            logging.info(f"Rejected username collision for '{username}' from {addr}")
            self._send_hello_response(addr, status='denied', reason='username_taken')
            return

        # Accept (new or reconnect from same addr)
        self.clients[username] = {
            'addr': addr,
            'x': msg.get('x', 6000),
            'y': msg.get('y', 6000),
            'car': car,
            'last_seen': time.time()
        }
        self.addr_to_name[addr] = username
        logging.info(f"Hello/connected: {username} @ {addr}")
        self._send_hello_response(addr, status='ok')

    def _send_hello_response(self, addr, status='ok', reason=None):
        payload = {'type': 'hello_response', 'status': status}
        if reason:
            payload['reason'] = reason
        try:
            self.server_socket.sendto(json.dumps(payload).encode(), addr)
        except Exception as e:
            logging.error(f"Failed to send hello_response to {addr}: {e}")

    def handle_state(self, addr, msg):
        username = msg.get('username')
        if not username or username not in self.clients:
            # Client not registered or lost state: request re-hello
            self._send_control(addr, 'need_hello')
            return

        client = self.clients[username]
        if client['addr'] != addr:
            # Update address if NAT/port changed (quick reconnect)
            old_addr = client['addr']
            self.addr_to_name.pop(old_addr, None)
            client['addr'] = addr
            self.addr_to_name[addr] = username
            logging.info(f"Updated addr for {username}: {old_addr} -> {addr}")

        client['x'] = msg.get('x', client['x'])
        client['y'] = msg.get('y', client['y'])
        client['car'] = msg.get('car', client['car'])
        client['last_seen'] = time.time()

    def _send_control(self, addr, code):
        payload = {'type': 'control', 'code': code}
        try:
            self.server_socket.sendto(json.dumps(payload).encode(), addr)
        except Exception as e:
            logging.error(f"Failed to send control '{code}' to {addr}: {e}")

    def check_disconnections(self):
        now = time.time()
        to_drop = []
        for username, data in list(self.clients.items()):
            if now - data['last_seen'] > HEARTBEAT_TIMEOUT:
                to_drop.append(username)

        for username in to_drop:
            addr = self.clients[username]['addr']
            logging.info(f"Dropping {username} ({addr}) - timeout")
            self.addr_to_name.pop(addr, None)
            self.clients.pop(username, None)

    def broadcast_positions(self):
        if time.time() - self.last_broadcast < 1.0 / BROADCAST_RATE:
            return

        if not self.clients:
            return

        players = {
            username: {
                'x': data['x'],
                'y': data['y'],
                'car': data['car']
            }
            for username, data in self.clients.items()
        }

        packet = json.dumps({'type': 'state_broadcast', 'players': players}).encode()
        for username, data in list(self.clients.items()):
            addr = data['addr']
            try:
                self.server_socket.sendto(packet, addr)
            except Exception as e:
                logging.error(f"Failed to send broadcast to {username} ({addr}): {e}")

        self.last_broadcast = time.time()

    def run(self):
        logging.info("Waiting for client connections...")
        try:
            while True:
                self.handle_incoming_data()
                self.check_disconnections()
                self.broadcast_positions()
                time.sleep(TICK_SLEEP)
        except KeyboardInterrupt:
            logging.info("Server shutting down...")
        finally:
            self.server_socket.close()


def main():
    server = DeliveryRushServer()
    server.run()


if __name__ == "__main__":
    main()