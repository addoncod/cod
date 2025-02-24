import time
import json
import hashlib
import threading
import requests
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
import functions  # ✅ Uvoz helper funkcija iz functions.py

# 🔧 Blockchain konfiguracija
DIFFICULTY = 4
PEERS = []
BLOCKCHAIN_FILE = "blockchain_data.json"
WALLETS = {}

app = Flask(__name__)
socketio = SocketIO(app)


class Block:
    def __init__(self, index, previous_hash, timestamp, transactions, resource_tasks, miner, reward, nonce):
        self.index = index
        self.previous_hash = previous_hash
        self.timestamp = timestamp
        self.transactions = transactions
        self.resource_tasks = resource_tasks
        self.miner = miner
        self.reward = reward
        self.nonce = nonce
        self.hash = self.calculate_hash()

    def calculate_hash(self):
        data_str = f"{self.index}{self.previous_hash}{self.timestamp}{self.transactions}{self.resource_tasks}{self.miner}{self.reward}{self.nonce}".encode()
        return hashlib.sha256(data_str).hexdigest()


class Blockchain:
    def __init__(self):
        self.chain = self.load_blockchain()

    def create_genesis_block(self):
        return Block(0, "0", int(time.time()), [], [], "GENESIS", 0, 0)

    def load_blockchain(self):
        try:
            with open(BLOCKCHAIN_FILE, "r") as f:
                return [Block(**block) for block in json.load(f)]
        except (FileNotFoundError, json.JSONDecodeError):
            return [self.create_genesis_block()]

    def save_blockchain(self):
        with open(BLOCKCHAIN_FILE, "w") as f:
            json.dump([block.__dict__ for block in self.chain], f, indent=4)

    def add_block(self, transactions, resource_tasks, miner):
        new_block = mine_block(self.chain[-1], transactions, resource_tasks, miner)
        self.chain.append(new_block)
        self.save_blockchain()
        broadcast_block(new_block)
        return new_block


blockchain = Blockchain()


# 📡 **Pregled CPU/RAM zahteva**
@app.route('/resource_request', methods=['GET'])
def get_resource_requests():
    return jsonify(functions.get_resource_requests())


# 📡 **Dodavanje CPU/RAM zahteva**
@app.route('/resource_request', methods=['POST'])
def add_resource_request():
    return jsonify(*functions.add_resource_request(request.json))


# 📡 **Kupovina CPU/RAM resursa**
@app.route('/buy_resources', methods=['POST'])
def buy_resources():
    return jsonify(*functions.buy_resources(request.json))


# 📡 **Pregled transakcija**
@app.route('/transactions', methods=['GET'])
def get_transactions():
    return jsonify(functions.get_transactions())


# 📡 **Dodavanje transakcije**
@app.route('/add_transaction', methods=['POST'])
def add_transaction():
    return jsonify(*functions.add_transaction(request.json))


# 📡 **Pregled čvorova**
@app.route('/peers', methods=['GET'])
def get_peers():
    return jsonify(functions.get_peers())


# 📡 **Registracija čvora**
@app.route('/register_peer', methods=['POST'])
def register_peer():
    return jsonify(*functions.register_peer(request.json))


# 📡 **Pregled balansa korisnika**
@app.route('/balance/<address>', methods=['GET'])
def get_balance(address):
    return jsonify(functions.get_balance(address))


# 📡 **Dodavanje balansa korisniku (testiranje)**
@app.route('/add_balance', methods=['POST'])
def add_balance():
    return jsonify(*functions.add_balance(request.json))


# 📡 **Pregled blockchaina**
@app.route('/chain', methods=['GET'])
def get_chain():
    return jsonify([block.__dict__ for block in blockchain.chain]), 200


# 📡 **Emitovanje bloka u P2P mrežu**
def broadcast_block(block):
    for peer in PEERS:
        try:
            requests.post(f"{peer}/new_block", json=block.__dict__)
        except requests.exceptions.RequestException:
            pass


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
