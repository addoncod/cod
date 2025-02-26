import time
import json
import hashlib
import threading
import logging
import requests
from flask import Flask, request, jsonify
from flask_socketio import SocketIO

from functions import (
    add_balance, 
    buy_resources, 
    get_balance, 
    get_user_resources, 
    get_resource_requests, 
    save_blockchain, 
    load_blockchain,
    load_wallets,
    save_wallets,
    assign_resources_to_user,
    register_miner,
    REGISTERED_MINERS,
    RESOURCE_REQUESTS
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

DIFFICULTY = 4
FEE_PERCENTAGE = 0.1
MONERO_PER_CPU_PER_HOUR = 1.0e-7
MONERO_PER_RAM_PER_HOUR = 1.058e-10
DISCOUNT_FACTOR = 0.6
MAIN_WALLET_ADDRESS = "2Ub5eqoKGRjmEGov9dzqNsX4LA7Erd3joSBB"
MINER_SHARES = {}

app = Flask(__name__)
socketio = SocketIO(app)

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

class Blockchain:
    def __init__(self):
        self.chain = load_blockchain()
        if not self.chain:
            self.create_genesis_block()

    def create_genesis_block(self):
        genesis_block = Block(0, "0", int(time.time()), [], [], "GENESIS", 0)
        self.chain.append(genesis_block)
        save_blockchain(self.chain)
        logging.info("✅ Genesis blok kreiran.")

    def validate_block(self, new_block, previous_block):
        if previous_block.index + 1 != new_block.index:
            return False
        if previous_block.hash != new_block.previous_hash:
            return False
        if new_block.calculate_hash() != new_block.hash:
            return False
        if not new_block.hash.startswith("0" * DIFFICULTY):
            return False
        return True

blockchain = Blockchain()

@app.route("/register_miner", methods=["POST"])
def api_register_miner():
    data = request.json
    miner_id = data.get("miner_id")
    cpu_available = data.get("cpu_available")
    ram_available = data.get("ram_available")

    if not miner_id or cpu_available is None or ram_available is None:
        return jsonify({"error": "Neispravni podaci za registraciju minera"}), 400

    REGISTERED_MINERS[miner_id] = {"cpu": cpu_available, "ram": ram_available}
    save_wallets(load_wallets())
    logging.info(f"⛏️  Rudar {miner_id} registrovan sa {cpu_available} CPU i {ram_available} MB RAM-a.")
    return jsonify({"message": "✅ Rudar uspješno registrovan", "miners": REGISTERED_MINERS}), 200

@app.route("/chain", methods=["GET"])
def get_chain():
    return jsonify([block.to_dict() for block in blockchain.chain]), 200

@app.route("/resource_request", methods=["GET"])
def api_get_resource_requests():
    return get_resource_requests()

@app.route("/mine", methods=["POST"])
def submit_block():
    block_data = request.json
    required_fields = ["index", "previous_hash", "timestamp", "resource_tasks", "nonce", "hash", "miner"]

    if not all(field in block_data for field in required_fields):
        return jsonify({"error": "Nedostaju polja u bloku"}), 400

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

    last_block = blockchain.chain[-1]
    if not blockchain.validate_block(new_block, last_block):
        return jsonify({"error": "Validacija bloka nije uspjela"}), 400

    blockchain.chain.append(new_block)
    save_blockchain(blockchain.chain)
    MINER_SHARES[new_block.miner] = MINER_SHARES.get(new_block.miner, 0) + 1
    return jsonify({"message": "✅ Blok primljen"}), 200

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
