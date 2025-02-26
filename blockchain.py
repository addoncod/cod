import time
import json
import hashlib
import threading
import logging
from flask import Flask, request, jsonify
from flask_socketio import SocketIO

# Konfiguracija logiranja
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = Flask(__name__)
socketio = SocketIO(app)

# Datoteke za pohranu podataka
BLOCKCHAIN_FILE = "blockchain_data.json"
WALLETS_FILE = "wallets.json"

# Globalne varijable
USER_RESOURCES = {}          # Resursi korisnika (CPU, RAM)
RESOURCE_REQUESTS = []       # Lista zahtjeva za resurse
REGISTERED_MINERS = {}       # Evidencija aktivnih rudara
MINER_SHARES = {}            # Raspodjela zarade među rudarima

# Parametri za izračun vrijednosti resursa
MONERO_PER_CPU_PER_HOUR = 1.0e-7
MONERO_PER_RAM_PER_HOUR = 1.058e-10
DISCOUNT_FACTOR = 0.6  # Kupac dobiva 60% potencijalnog prinosa
MAIN_WALLET = "MAIN_WALLET"

class Block:
    def __init__(self, index, previous_hash, timestamp, transactions, resource_tasks, miner, nonce):
        self.index = index
        self.previous_hash = previous_hash
        self.timestamp = timestamp
        self.transactions = transactions
        self.resource_tasks = resource_tasks
        self.miner = miner
        self.nonce = nonce
        self.hash = self.calculate_hash()

    def calculate_hash(self):
        data = {
            "index": self.index,
            "previous_hash": self.previous_hash,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "resource_tasks": self.resource_tasks,
            "miner": self.miner,
            "nonce": self.nonce
        }
        data_str = json.dumps(data, sort_keys=True).encode()
        return hashlib.sha256(data_str).hexdigest()

    def to_dict(self):
        return self.__dict__

def save_blockchain(blockchain):
    with open(BLOCKCHAIN_FILE, "w") as f:
        json.dump([block.to_dict() for block in blockchain], f, indent=4)

def load_blockchain():
    try:
        with open(BLOCKCHAIN_FILE, "r") as f:
            return [Block(**block) for block in json.load(f)]
    except (FileNotFoundError, json.JSONDecodeError):
        return [Block(0, "0", 0, [], [], "GENESIS", 0)]

blockchain = load_blockchain()

def load_wallets():
    try:
        with open(WALLETS_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_wallets(wallets):
    with open(WALLETS_FILE, "w") as f:
        json.dump(wallets, f, indent=4)

@app.route("/chain", methods=["GET"])
def get_chain():
    return jsonify([block.to_dict() for block in blockchain]), 200

@app.route("/mine", methods=["POST"])
def submit_block():
    block_data = request.json
    new_block = Block(
        block_data["index"],
        block_data["previous_hash"],
        block_data["timestamp"],
        block_data.get("transactions", []),
        block_data.get("resource_tasks", []),
        block_data["miner"],
        block_data["nonce"]
    )
    if new_block.calculate_hash() != block_data["hash"]:
        return jsonify({"error": "Neispravan hash"}), 400

    blockchain.append(new_block)
    save_blockchain(blockchain)

    MINER_SHARES[new_block.miner] = MINER_SHARES.get(new_block.miner, 0) + 1
    return jsonify({"message": "✅ Blok primljen"}), 200

@app.route("/register_miner", methods=["POST"])
def register_miner():
    data = request.json
    REGISTERED_MINERS[data["miner_id"]] = {"cpu": data["cpu_available"], "ram": data["ram_available"]}
    return jsonify({"message": "✅ Rudar registriran"}), 200

@app.route("/resource_request", methods=["POST"])
def resource_request():
    data = request.json
    RESOURCE_REQUESTS.append({
        "buyer": data["buyer"],
        "cpu": data["cpu"],
        "ram": data["ram"],
        "timestamp": int(time.time())
    })
    return jsonify({"message": "✅ Zahtjev dodan"}), 200

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
