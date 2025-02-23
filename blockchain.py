import time
import json
import pyblake2
import threading
import requests
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit

# Blockchain konfiguracija
DIFFICULTY = 4  # Početna težina rudarenja
PEERS = []  # Spisak povezanih čvorova

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
        return pyblake2.blake2b(data_str, digest_size=32).hexdigest()

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
        return new_block

    def is_chain_valid(self):
        for i in range(1, len(self.chain)):
            prev_block = self.chain[i - 1]
            curr_block = self.chain[i]
            if curr_block.hash != curr_block.calculate_hash():
                return False
            if curr_block.previous_hash != prev_block.hash:
                return False
        return True

# Rudarenje bloka
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

# Flask API za rudarenje i P2P mrežu
app = Flask(__name__)
socketio = SocketIO(app)

@app.route('/mine', methods=['POST'])
def mine():
    data = request.json.get('data', 'Default Transaction')
    new_block = blockchain.add_block(data)
    broadcast_block(new_block)
    return jsonify(new_block.__dict__), 200

@app.route('/chain', methods=['GET'])
def get_chain():
    return jsonify([block.__dict__ for block in blockchain.chain]), 200

@app.route('/nodes', methods=['POST'])
def add_peer():
    node = request.json.get('node')
    if node and node not in PEERS:
        PEERS.append(node)
    return jsonify({'peers': PEERS}), 200

@app.route('/nodes', methods=['GET'])
def get_peers():
    return jsonify({'peers': PEERS}), 200

# WebSockets za sinhronizaciju blokova
@socketio.on('new_block')
def handle_new_block(data):
    new_block = Block(**data)
    if new_block.previous_hash == blockchain.chain[-1].hash:
        blockchain.chain.append(new_block)
        print("🔗 Novi blok dodat iz mreže!")
    emit('chain_update', [block.__dict__ for block in blockchain.chain], broadcast=True)

# Emitovanje novog bloka svim čvorovima
def broadcast_block(block):
    for peer in PEERS:
        try:
            requests.post(f"{peer}/mine", json=block.__dict__)
        except requests.exceptions.RequestException:
            pass

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
