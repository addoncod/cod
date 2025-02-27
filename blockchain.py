import time
import json
import hashlib
import threading
import logging
import requests
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
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

# Konfiguracija logiranja
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Blockchain parametri
DIFFICULTY = 4
FEE_PERCENTAGE = 0.03
MAIN_WALLET_ADDRESS = "2Ub5eqoKGRjmEGov9dzqNsX4LA7Erd3joSBB"

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

    def to_dict(self):
        return self.__dict__

class Blockchain:
    def __init__(self):
        self.chain = load_blockchain()

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

    def add_block(self, transactions, resource_tasks, miner):
        wallets = load_wallets()
        valid_transactions = []
        total_mining_fee = 0

        for tx in transactions:
            sender, recipient, amount = tx["from"], tx["to"], tx["amount"]
            fee = amount * FEE_PERCENTAGE
            if wallets.get(sender, 0) >= amount + fee:
                wallets[sender] -= (amount + fee)
                wallets[recipient] = wallets.get(recipient, 0) + amount
                wallets[miner] = wallets.get(miner, 0) + fee
                valid_transactions.append(tx)
                total_mining_fee += fee
            else:
                logging.error(f"🚨 Nedovoljno balansa za transakciju {sender} -> {recipient}")
        save_wallets(wallets)

        new_block = self.mine_block(self.chain[-1], valid_transactions, resource_tasks, miner)

        if self.validate_block(new_block, self.chain[-1]):
            self.chain.append(new_block)
            save_blockchain([block.to_dict() for block in self.chain])
            logging.info(f"✅ Blok {new_block.index} dodan | Transakcije: {len(new_block.transactions)} | Rudarski fee: {total_mining_fee}")
            return new_block
        else:
            logging.error("❌ Neuspješna validacija bloka")
            return None

    def mine_block(self, previous_block, transactions, resource_tasks, miner):
        index = previous_block.index + 1
        timestamp = int(time.time())
        previous_hash = previous_block.hash
        nonce = 0
        prefix = "0" * DIFFICULTY

        while True:
            new_block = Block(index, previous_hash, timestamp, transactions, resource_tasks, miner, 0, nonce)
            if new_block.hash.startswith(prefix):
                logging.info(f"⛏️ Blok {index} iskopan | Rudar: {miner} | Transakcije: {len(transactions)} | Hash: {new_block.hash}")
                return new_block
            nonce += 1

blockchain = Blockchain()

@app.route("/chain", methods=["GET"])
def get_chain():
    return jsonify([block.to_dict() if isinstance(block, Block) else block for block in blockchain.chain]), 200


@app.route("/transactions", methods=["GET"])
def get_pending_transactions():
    return jsonify({"transactions": []}), 200

@app.route("/resource_request", methods=["GET"])
def api_get_resource_requests():
    return get_resource_requests()

@app.route("/assign_resources", methods=["POST"])
def api_assign_resources():
    data = request.json
    return assign_resources_to_user(data.get("buyer"), data.get("cpu"), data.get("ram"))
@app.route("/resource_usage_session", methods=["POST"])
def resource_usage_session():
    data = request.json
    buyer = data.get("buyer")
    cpu = data.get("cpu")
    ram = data.get("ram")

    if not buyer or cpu is None or ram is None:
        return jsonify({"error": "Neispravni podaci"}), 400

    return jsonify({"message": "Resource usage session pokrenut"}), 200

@app.route("/register_miner", methods=["POST"])
def api_register_miner():
    data = request.json
    return register_miner(data.get("miner_id"), data.get("cpu_available"), data.get("ram_available"))

@app.route("/balance/<address>", methods=["GET"])
def api_get_balance(address):
    return jsonify({"balance": get_balance(address)})

@app.route("/buy_resources", methods=["POST"])
def api_buy_resources():
    data = request.json
    return buy_resources(data.get("buyer"), data.get("cpu"), data.get("ram"), data.get("seller"))

@app.route("/add_balance", methods=["POST"])
def api_add_balance():
    data = request.json
    return add_balance(data.get("user"), data.get("amount"))


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
