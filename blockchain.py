import time
import json
import hashlib
import threading
import requests
import psutil
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from functions import (
    add_balance, 
    buy_resources, 
    get_balance, 
    get_user_resources, 
    get_resource_requests, 
    save_blockchain, 
    load_blockchain
)

# 🔧 Konfiguracija blockchaina
DIFFICULTY = 4
PEERS = []
RESOURCE_REWARD = 5
RESOURCE_PRICE = 2

# Globalne varijable za rudare i novčanike (ako nisu definirane drugdje)
MINERS = {}
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
        self.chain = load_blockchain()
        # Pretvaranje učitanog blockchaina (lista dict-ova) u objekte klase Block
        new_chain = []
        for block in self.chain:
            if isinstance(block, dict):
                block_copy = block.copy()
                block_copy.pop("hash", None)
                new_chain.append(Block(**block_copy))
            else:
                new_chain.append(block)
        self.chain = new_chain

    def add_block(self, transactions, resource_tasks, miner):
        new_block = self.mine_block(self.chain[-1], transactions, resource_tasks, miner)
        self.chain.append(new_block)
        save_blockchain(self.chain)
        return new_block

    def mine_block(self, previous_block, transactions, resource_tasks, miner):
        index = previous_block.index + 1
        timestamp = int(time.time())
        previous_hash = previous_block.hash
        nonce = 0
        prefix = "0" * DIFFICULTY

        while True:
            new_block = Block(index, previous_hash, timestamp, transactions, resource_tasks, miner, RESOURCE_REWARD, nonce)
            if new_block.hash.startswith(prefix):
                print(f"✅ Blok {index} iskopan | Rudar: {miner} | Nagrada: {RESOURCE_REWARD} coins | Hash: {new_block.hash}")
                return new_block
            nonce += 1

blockchain = Blockchain()

# 📡 API endpointi
@app.route('/add_balance', methods=['POST'])
def api_add_balance():
    data = request.json
    return add_balance(data.get("user"), data.get("amount"))

@app.route('/buy_resources', methods=['POST'])
def api_buy_resources():
    data = request.json
    return buy_resources(data.get("buyer"), data.get("cpu"), data.get("ram"), data.get("seller"))

@app.route('/balance/<address>', methods=['GET'])
def api_get_balance(address):
    return jsonify({"balance": get_balance(address)})

@app.route('/register_miner', methods=['POST'])
def register_miner():
    """Registracija rudara i njihovih resursa"""
    data = request.json
    miner_id = data.get("miner_id")
    cpu_available = data.get("cpu_available")
    ram_available = data.get("ram_available")

    if not all([miner_id, cpu_available, ram_available]):
        return jsonify({"error": "Neispravni podaci"}), 400

    MINERS[miner_id] = {"cpu": cpu_available, "ram": ram_available}
    WALLETS.setdefault(miner_id, 0)  # Kreira novčanik ako ne postoji

    return jsonify({"message": "Miner registrovan", "miners": MINERS}), 200


@app.route('/user_resources/<user>', methods=['GET'])
def api_get_user_resources(user):
    return get_user_resources(user)

@app.route('/resource_request', methods=['GET'])
def api_get_resource_requests():
    return get_resource_requests()
@app.route('/mine', methods=['POST'])
def api_submit_block():
    block_data = request.json
    # Osnovna validacija podataka (možete proširiti validaciju prema potrebi)
    required_fields = ["index", "previous_hash", "timestamp", "resource_tasks", "nonce", "hash", "miner"]
    if not all(field in block_data for field in required_fields):
        return jsonify({"error": "Neispravni podaci bloka"}), 400

    # Možete dodati dodatnu validaciju, npr. provjeru hash-a, prethodnog bloka itd.
    try:
        new_block = Block(
            index=block_data["index"],
            previous_hash=block_data["previous_hash"],
            timestamp=block_data["timestamp"],
            transactions=block_data.get("transactions", []),
            resource_tasks=block_data.get("resource_tasks", []),
            miner=block_data["miner"],
            reward=RESOURCE_REWARD,  # ili koristiti block_data["reward"] ako se šalje
            nonce=block_data["nonce"]
        )
    except Exception as e:
        return jsonify({"error": f"Greška pri kreiranju bloka: {e}"}), 400

    # Jednostavno dodajemo blok na kraj lanca (bez dodatne provjere)
    blockchain.chain.append(new_block)
    save_blockchain(blockchain.chain)

    print(f"✅ Blok {new_block.index} primljen i dodan u lanac.")
    return jsonify({"message": "Blok primljen", "block": new_block.__dict__}), 200

@app.route('/chain', methods=['GET'])
def get_chain():
    return jsonify([block.__dict__ for block in blockchain.chain]), 200

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
