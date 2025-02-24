import time
import json
import hashlib
import threading
import requests
import psutil
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from functions import add_balance, buy_resources, get_balance, get_user_resources, get_resource_requests, save_blockchain, load_blockchain

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
        # Uklonjen je argument, load_blockchain sada ne prima nikakve parametre.
        self.chain = load_blockchain()
        # Ako učitani lanac sadrži samo dict-ove (npr. iz JSON fajla), možemo ga po potrebi pretvoriti u Block objekte.
        self.chain = [Block(**block) if isinstance(block, dict) else block for block in self.chain]

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


@app.route('/user_resources/<user>', methods=['GET'])
def api_get_user_resources(user):
    return get_user_resources(user)


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
    WALLETS.setdefault(miner_id, 0)  # ✅ Kreira novčanik ako ne postoji

    return jsonify({"message": "Miner registrovan", "miners": MINERS}), 200


@app.route('/resource_request', methods=['GET'])
def api_get_resource_requests():
    return get_resource_requests()


@app.route('/chain', methods=['GET'])
def get_chain():
    # Pretvaramo objekte u dictionary prije slanja kao JSON
    return jsonify([block.__dict__ for block in blockchain.chain]), 200


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
