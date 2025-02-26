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

# Konfiguracija logiranja
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Blockchain parametri
DIFFICULTY = 4
FEE_PERCENTAGE = 0.1  # 10% naknade ide u glavni wallet

# Resursi CPU i RAM vrijednosti
MONERO_PER_CPU_PER_HOUR = 1.0e-7
MONERO_PER_RAM_PER_HOUR = 1.058e-10
DISCOUNT_FACTOR = 0.6  # Kupac dobija 60% potencijalnog prinosa

# Rudari i balansi
MINER_SHARES = {}
MAIN_WALLET_ADDRESS = "2Ub5eqoKGRjmEGov9dzqNsX4LA7Erd3joSBB"

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
        """Generiše hash bloka koristeći SHA-256"""
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
        """Učitava blockchain iz memorije ili kreira genesis blok ako ne postoji."""
        self.chain = load_blockchain()

    def validate_block(self, new_block, previous_block):
        """Validira novi blok pre nego što ga doda u lanac."""
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
        """Dodaje novi blok u blockchain."""
        new_block = self.mine_block(self.chain[-1], transactions, resource_tasks, miner)
        if self.validate_block(new_block, self.chain[-1]):
            self.chain.append(new_block)
            save_blockchain(self.chain)
            logging.info(f"✅ Blok {new_block.index} uspješno dodan.")
            return new_block
        else:
            logging.error("❌ Neuspješna validacija novog bloka.")
            return None

    def mine_block(self, previous_block, transactions, resource_tasks, miner):
        """Proces rudarenja bloka."""
        index = previous_block.index + 1
        timestamp = int(time.time())
        previous_hash = previous_block.hash
        nonce = 0
        prefix = "0" * DIFFICULTY

        while True:
            new_block = Block(index, previous_hash, timestamp, transactions, resource_tasks, miner, nonce)
            if new_block.hash.startswith(prefix):
                logging.info(f"⛏️  Blok {index} iskopan | Rudar: {miner} | Hash: {new_block.hash}")
                return new_block
            nonce += 1

blockchain = Blockchain()

@app.route("/register_miner", methods=["POST"])
def api_register_miner():
    """Registruje minera na sistem."""
    data = request.json
    miner_id = data.get("miner_id")
    cpu_available = data.get("cpu_available")
    ram_available = data.get("ram_available")

    if not miner_id or cpu_available is None or ram_available is None:
        return jsonify({"error": "Neispravni podaci za registraciju minera"}), 400

    REGISTERED_MINERS[miner_id] = {"cpu": cpu_available, "ram": ram_available}
    save_wallets(load_wallets())  # Osigurava da svi miner walleti postoje
    logging.info(f"⛏️  Rudar {miner_id} registrovan sa {cpu_available} CPU i {ram_available} MB RAM-a.")

    return jsonify({"message": "✅ Rudar uspješno registrovan", "miners": REGISTERED_MINERS}), 200

@app.route("/mine", methods=["POST"])
def submit_block():
    """Endpoint za prijem bloka od rudara."""
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

    # Beleženje shareova rudara
    MINER_SHARES[new_block.miner] = MINER_SHARES.get(new_block.miner, 0) + 1
    return jsonify({"message": "✅ Blok primljen"}), 200

def resource_usage_session_thread(buyer, cpu, ram, total_minutes=1440):
    """Obračunava korištenje resursa po minuti i naplatu."""
    total_cost = 0.00009 * (cpu / 2) * (ram / 2048.0)
    minute_cost = total_cost / total_minutes
    fee_per_minute = minute_cost * FEE_PERCENTAGE
    miner_reward_per_minute = minute_cost - fee_per_minute

    for i in range(total_minutes):
        wallets = load_wallets()
        if wallets.get(buyer, 0) < minute_cost:
            logging.error(f"Nedovoljno sredstava za {buyer}. Naplata prekinuta.")
            break

        wallets[buyer] -= minute_cost
        wallets[MAIN_WALLET_ADDRESS] += fee_per_minute

        active_miners = {m_id: MINER_SHARES[m_id] for m_id in MINER_SHARES if m_id in REGISTERED_MINERS}
        if active_miners:
            reward_each = miner_reward_per_minute / len(active_miners)
            for miner_id in active_miners:
                wallets[miner_id] += reward_each

        save_wallets(wallets)
        time.sleep(60)

@app.route("/resource_usage_session", methods=["POST"])
def resource_usage_session():
    """Endpoint za naplatu resursa po minuti."""
    data = request.get_json()
    buyer = data.get("buyer")
    try:
        cpu = float(data.get("cpu", 0))
        ram = float(data.get("ram", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Neispravne vrijednosti za CPU ili RAM"}), 400

    if not buyer or cpu <= 0 or ram <= 0:
        return jsonify({"error": "Buyer, CPU i RAM moraju biti veći od 0"}), 400

    thread = threading.Thread(target=resource_usage_session_thread, args=(buyer, cpu, ram))
    thread.start()
    return jsonify({"message": "Naplata resursa pokrenuta."}), 200

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
