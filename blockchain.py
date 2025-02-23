import time
import json
import hashlib
import threading
import requests
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit

# Blockchain konfiguracija
DIFFICULTY = 4  # Težina rudarenja
PEERS = []  # Spisak povezanih čvorova
TRANSACTIONS = []  # Mempool transakcija

# Definicija bloka
class Block:
    def __init__(self, index, previous_hash, timestamp, data, nonce):
        self.index = index
        self.previous_hash = previous_hash
        self.timestamp = timestamp
        self.data = data
        self.nonce = nonce
        self.hash = self.calculate_hash()

    def calculate_hash(self):
        data_str = f"{self.index}{self.previous_hash}{self.timestamp}{self.data}{self.nonce}".encode()
        return hashlib.sha256(data_str).hexdigest()  # SHA-256 hashiranje

    def __repr__(self):
        return json.dumps(self.__dict__, indent=4)

# Kreiranje Genesis bloka
def create_genesis_block():
    return Block(0, "0", int(time.time()), "Genesis Block", 0)

# Blockchain klasa
class Blockchain:
    def __init__(self):
        self.chain = [create_genesis_block()]

    def add_block(self, data):
        new_block = mine_block(self.chain[-1], data)
        self.chain.append(new_block)
        broadcast_block(new_block)
        return new_block

    def is_chain_valid(self, chain):
        for i in range(1, len(chain)):
            prev_block = chain[i - 1]
            curr_block = chain[i]
            if curr_block.hash != curr_block.calculate_hash():
                return False
            if curr_block.previous_hash != prev_block.hash:
                return False
        return True

    def replace_chain(self, new_chain):
        if len(new_chain) > len(self.chain) and self.is_chain_valid(new_chain):
            self.chain = new_chain
            return True
        return False

# Rudarenje bloka sa SHA-256
def mine_block(previous_block, data, difficulty=DIFFICULTY):
    index = previous_block.index + 1
    timestamp = int(time.time())
    previous_hash = previous_block.hash
    nonce = 0
    prefix = "0" * difficulty

    while True:
        new_block = Block(index, previous_hash, timestamp, data, nonce)
        if new_block.hash.startswith(prefix):
            print(f"✅ Rudaren blok {index} | Nonce: {nonce} | Hash: {new_block.hash}")
            return new_block
        nonce += 1

# Inicijalizacija blockchaina
blockchain = Blockchain()

# Flask API za blockchain i mrežu
app = Flask(__name__)
socketio = SocketIO(app)

# 🚀 **Automatska sinhronizacija sa drugim čvorovima**
def sync_chain():
    for peer in PEERS:
        try:
            response = requests.get(f"{peer}/chain")
            peer_chain = response.json()
            peer_chain = [Block(**block) for block in peer_chain]

            if blockchain.replace_chain(peer_chain):
                print("🔄 Blockchain sinhronizovan sa čvorom:", peer)
        except requests.exceptions.RequestException:
            pass

# 🚀 **Slanje transakcija između čvorova**
@app.route('/transaction', methods=['POST'])
def add_transaction():
    data = request.json.get('data', '')
    if not data:
        return jsonify({'error': 'Nema podataka za transakciju'}), 400

    TRANSACTIONS.append(data)
    broadcast_transaction(data)
    return jsonify({'message': 'Transakcija dodata u mempool'}), 200

@app.route('/transactions', methods=['GET'])
def get_transactions():
    return jsonify({'transactions': TRANSACTIONS}), 200

def broadcast_transaction(transaction):
    for peer in PEERS:
        try:
            requests.post(f"{peer}/transaction", json={'data': transaction})
        except requests.exceptions.RequestException:
            pass

# 🚀 **Rudarenje bloka**
@app.route('/mine', methods=['POST'])
def mine():
    if not TRANSACTIONS:
        return jsonify({'error': 'Nema transakcija za rudarenje'}), 400

    new_block = blockchain.add_block(TRANSACTIONS[:])
    TRANSACTIONS.clear()  # Brišemo mempool nakon rudarenja
    return jsonify(new_block.__dict__), 200

# 🚀 **Preuzimanje blockchaina**
@app.route('/chain', methods=['GET'])
def get_chain():
    return jsonify([block.__dict__ for block in blockchain.chain]), 200

# 🚀 **Dodavanje čvorova u mrežu**
@app.route('/nodes', methods=['POST'])
def add_peer():
    node = request.json.get('node')
    if node and node not in PEERS:
        PEERS.append(node)
        sync_chain()  # Sinhronizacija sa novim čvorom
    return jsonify({'peers': PEERS}), 200

@app.route('/nodes', methods=['GET'])
def get_peers():
    return jsonify({'peers': PEERS}), 200

# 🚀 **Sinhronizacija blokova preko WebSockets-a**
@socketio.on('new_block')
def handle_new_block(data):
    new_block = Block(**data)
    if new_block.previous_hash == blockchain.chain[-1].hash:
        blockchain.chain.append(new_block)
        print("🔗 Novi blok dodat iz mreže!")
    emit('chain_update', [block.__dict__ for block in blockchain.chain], broadcast=True)

# 🚀 **Emitovanje novih blokova svim čvorovima**
def broadcast_block(block):
    for peer in PEERS:
        try:
            requests.post(f"{peer}/mine", json=block.__dict__)
        except requests.exceptions.RequestException:
            pass

# Pokretanje blockchain servera
if __name__ == '__main__':
    threading.Thread(target=sync_chain, daemon=True).start()
    socketio.run(app, host='0.0.0.0', port=5000)
