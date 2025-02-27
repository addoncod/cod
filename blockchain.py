import time
import json
import hashlib
import logging
import threading
import requests
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from functions import (
    save_blockchain,
    load_blockchain,
    load_wallets,
    save_wallets,
    register_miner,
    distribute_mining_rewards,
    get_resource_requests
)

# Konfiguracija logiranja
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Blockchain parametri
DIFFICULTY = 4
FEE_PERCENTAGE = 0.03  # 3% naknade za transakcije
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
        self.chain = []
        chain_data = load_blockchain()
        for block in chain_data:
            if isinstance(block, dict):
                new_block = Block(
                    index=block["index"],
                    previous_hash=block["previous_hash"],
                    timestamp=block["timestamp"],
                    transactions=block.get("transactions", []),
                    resource_tasks=block.get("resource_tasks", []),
                    miner=block["miner"],
                    reward=block["reward"],
                    nonce=block["nonce"]
                )
                self.chain.append(new_block)

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
        total_mining_fee = 0  # Ukupni fee za rudara

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

@app.route("/transaction", methods=['POST'])
def new_transaction():
    data = request.json
    sender = data.get("from")
    recipient = data.get("to")
    amount = data.get("amount")
    fee = amount * FEE_PERCENTAGE

    if not sender or not recipient or amount is None:
        return jsonify({"error": "Neispravni podaci za transakciju"}), 400

    wallets = load_wallets()
    sender_balance = wallets.get(sender, 0)
    if sender_balance < (amount + fee):
        return jsonify({"error": "Nedovoljno sredstava"}), 400

    wallets[sender] -= (amount + fee)
    wallets[recipient] = wallets.get(recipient, 0) + amount
    wallets[MAIN_WALLET_ADDRESS] = wallets.get(MAIN_WALLET_ADDRESS, 0) + fee
    save_wallets(wallets)

    transaction = {"from": sender, "to": recipient, "amount": amount}
    logging.info(f"✅ Transakcija dodana: {sender} -> {recipient} ({amount} coins)")

    return jsonify({"message": "Transakcija zabilježena"}), 200

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
