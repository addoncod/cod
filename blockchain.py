import time
import json
import hashlib
import threading
import requests
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
import ecdsa

DIFFICULTY = 4
PEERS = []
PENDING_TRANSACTIONS = []

# 🔥 Maksimalan broj coina koji mogu biti rudaren (npr. 21 miliona kao Bitcoin)
MAX_SUPPLY = 21000000  
current_supply = 0  # Trenutni broj iskopanih coina

app = Flask(__name__)
socketio = SocketIO(app)

class Block:
    def __init__(self, index, previous_hash, timestamp, transactions, nonce, reward):
        self.index = index
        self.previous_hash = previous_hash
        self.timestamp = timestamp
        self.transactions = transactions
        self.nonce = nonce
        self.reward = reward  # Dodata nagrada za rudarenje
        self.hash = self.calculate_hash()

    def calculate_hash(self):
        data_str = f"{self.index}{self.previous_hash}{self.timestamp}{json.dumps(self.transactions)}{self.nonce}{self.reward}".encode()
        return hashlib.sha256(data_str).hexdigest()

class Blockchain:
    def __init__(self):
        self.chain = [self.create_genesis_block()]

    def create_genesis_block(self):
        return Block(0, "0", int(time.time()), [], 0, 0)

    def add_block(self, transactions, reward):
        new_block = mine_block(self.chain[-1], transactions, reward)
        self.chain.append(new_block)
        return new_block

blockchain = Blockchain()

def mine_block(previous_block, transactions, reward, difficulty=DIFFICULTY):
    global current_supply

    if current_supply + reward > MAX_SUPPLY:
        print("⚠️ Maksimalna količina coina dostignuta! Rudarenje onemogućeno.")
        return None

    index = previous_block.index + 1
    timestamp = int(time.time())
    previous_hash = previous_block.hash
    nonce = 0
    prefix = "0" * difficulty

    while True:
        new_block = Block(index, previous_hash, timestamp, transactions, nonce, reward)
        if new_block.hash.startswith(prefix):
            current_supply += reward  # Dodajemo rudarsku nagradu
            return new_block
        nonce += 1

@app.route('/mine', methods=['POST'])
def mine():
    global current_supply

    if not PENDING_TRANSACTIONS:
        return jsonify({"message": "Nema transakcija za rudarenje"}), 400

    reward = 50  # Početna nagrada za blok (može se smanjivati na pola kao kod Bitcoina)

    if current_supply + reward > MAX_SUPPLY:
        return jsonify({"message": "Dostignut maksimalan broj coina"}), 400

    new_block = blockchain.add_block(PENDING_TRANSACTIONS.copy(), reward)
    if new_block:
        PENDING_TRANSACTIONS.clear()
        broadcast_block(new_block)
        return jsonify(new_block.__dict__), 200
    else:
        return jsonify({"message": "Nema više coina za rudarenje"}), 400

@app.route('/chain', methods=['GET'])
def get_chain():
    return jsonify([block.__dict__ for block in blockchain.chain]), 200

@app.route('/balance/<address>', methods=['GET'])
def get_balance(address):
    balance = 0
    for block in blockchain.chain:
        for tx in block.transactions:
            if tx["recipient"] == address:
                balance += tx["amount"]
            if tx["sender"] == address:
                balance -= tx["amount"]
    return jsonify({"balance": balance}), 200

@socketio.on('new_block')
def handle_new_block(data):
    new_block = Block(**data)
    if new_block.previous_hash == blockchain.chain[-1].hash:
        blockchain.chain.append(new_block)
        emit('chain_update', [block.__dict__ for block in blockchain.chain], broadcast=True)

def broadcast_block(block):
    for peer in PEERS:
        try:
            requests.post(f"{peer}/mine", json=block.__dict__)
        except requests.exceptions.RequestException:
            pass

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
