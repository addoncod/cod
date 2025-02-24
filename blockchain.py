import time
import json
import hashlib
import threading
import requests
import psutil
import ecdsa
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit

# 🔧 Blockchain konfiguracija
DIFFICULTY = 4
PEERS = []
PENDING_TRANSACTIONS = []
RESOURCE_REQUESTS = []  # 📌 Lista CPU/RAM zahteva
MINERS = {}
WALLETS = {}
BLOCKCHAIN_FILE = "blockchain_data.json"
RESOURCE_REWARD = 5
RESOURCE_PRICE = 2

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


# 📡 **CPU/RAM tržište - Pregled zahteva**
@app.route('/resource_request', methods=['GET'])
def get_resource_requests():
    return jsonify({"requests": RESOURCE_REQUESTS}), 200


# 📡 **Dodavanje CPU/RAM zahteva**
@app.route('/resource_request', methods=['POST'])
def add_resource_request():
    data = request.json
    requester = data.get("requester")
    cpu_needed = data.get("cpu_needed")
    ram_needed = data.get("ram_needed")

    if not all([requester, cpu_needed, ram_needed]):
        return jsonify({"error": "Neispravni podaci"}), 400

    RESOURCE_REQUESTS.append({"requester": requester, "cpu": cpu_needed, "ram": ram_needed})
    return jsonify({"message": "Zahtev za CPU/RAM dodat", "requests": RESOURCE_REQUESTS}), 200


# 📡 **Kupovina CPU/RAM resursa koristeći coin**
@app.route('/buy_resources', methods=['POST'])
def buy_resources():
    data = request.json
    buyer = data.get("buyer")
    cpu_amount = data.get("cpu")
    ram_amount = data.get("ram")
    seller = data.get("seller")

    if not all([buyer, cpu_amount, ram_amount, seller]):
        return jsonify({"error": "Neispravni podaci"}), 400

    if seller not in MINERS:
        return jsonify({"error": "Prodavac nije registrovan kao rudar"}), 400

    total_price = (cpu_amount + ram_amount) * RESOURCE_PRICE

    if WALLETS.get(buyer, 0) < total_price:
        return jsonify({"error": "Nedovoljno coina za kupovinu"}), 400

    WALLETS[buyer] -= total_price
    WALLETS[seller] += total_price

    RESOURCE_REQUESTS.append({
        "requester": buyer,
        "cpu": cpu_amount,
        "ram": ram_amount
    })

    return jsonify({"message": "Uspešno kupljeni resursi"}), 200


# 📡 **Rudarenje bloka**
@app.route('/mine', methods=['POST'])
def mine():
    data = request.json
    miner_address = data.get("miner")

    if not miner_address:
        return jsonify({"message": "Rudar mora poslati svoju adresu"}), 400

    if not RESOURCE_REQUESTS:
        return jsonify({"message": "Nema CPU/RAM zahteva za rudarenje"}), 400

    resource_task = RESOURCE_REQUESTS.pop(0)

    new_block = blockchain.add_block([], [resource_task] if resource_task else [], miner_address)
    broadcast_block(new_block)
    return jsonify(new_block.__dict__), 200


# 📡 **Provera balansa korisnika**
@app.route('/balance/<address>', methods=['GET'])
def get_balance(address):
    balance = WALLETS.get(address, 0)
    return jsonify({"balance": balance}), 200


# 📡 **Dodavanje balansa korisniku (testiranje)**
@app.route('/add_balance', methods=['POST'])
def add_balance():
    data = request.json
    user_address = data.get("user")
    amount = data.get("amount")

    if not all([user_address, amount]):
        return jsonify({"message": "Nedostaju parametri"}), 400

    WALLETS[user_address] = WALLETS.get(user_address, 0) + amount

    return jsonify({"message": f"{amount} coina dodato korisniku {user_address}", "balance": WALLETS[user_address]}), 200


# 📡 **API Endpoint za preuzimanje blockchaina**
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


@app.route('/new_block', methods=['POST'])
def receive_new_block():
    block_data = request.json
    new_block = Block(**block_data)

    last_block = blockchain.chain[-1]
    if new_block.previous_hash == last_block.hash:
        blockchain.chain.append(new_block)
        blockchain.save_blockchain()
        return jsonify({"message": "Blok prihvaćen"}), 200
    else:
        return jsonify({"error": "Nevalidan blok"}), 400


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
