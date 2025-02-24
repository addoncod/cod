import time
import json
import hashlib
import threading
import requests
import psutil
from datasets import load_dataset
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit

# 🔧 Konfiguracija blockchaina
DIFFICULTY = 4
PEERS = []
PENDING_TRANSACTIONS = []
PENDING_AI_TASKS = []
RESOURCE_REQUESTS = []  # 📌 Korisnici koji žele da koriste CPU/RAM
MINERS = {}  # 📌 Rudari i njihovi dostupni resursi
AI_REWARD = 10  # 💰 Nagrada za AI rudarenje
RESOURCE_REWARD = 5  # 💰 Nagrada za deljenje CPU/RAM
AI_DATASET = "imdb"

app = Flask(__name__)
socketio = SocketIO(app)


class Block:
    def __init__(self, index, previous_hash, timestamp, transactions, ai_tasks, resource_tasks, miner, reward, nonce):
        self.index = index
        self.previous_hash = previous_hash
        self.timestamp = timestamp
        self.transactions = transactions
        self.ai_tasks = ai_tasks  # 🧠 AI zadaci
        self.resource_tasks = resource_tasks  # 💾 CPU/RAM zadaci
        self.miner = miner  # ⛏ Adresa rudara
        self.reward = reward  # 💰 Nagrada rudaru
        self.nonce = nonce
        self.hash = self.calculate_hash()

    def calculate_hash(self):
        data_str = f"{self.index}{self.previous_hash}{self.timestamp}{self.transactions}{self.ai_tasks}{self.resource_tasks}{self.miner}{self.reward}{self.nonce}".encode()
        return hashlib.sha256(data_str).hexdigest()


class Blockchain:
    def __init__(self):
        self.chain = [self.create_genesis_block()]

    def create_genesis_block(self):
        return Block(0, "0", int(time.time()), [], [], [], "GENESIS", 0, 0)

    def add_block(self, transactions, ai_tasks, resource_tasks, miner):
        new_block = mine_block(self.chain[-1], transactions, ai_tasks, resource_tasks, miner)
        self.chain.append(new_block)
        return new_block


blockchain = Blockchain()


# 📡 **Registracija rudara i njihovih resursa**
@app.route('/register_miner', methods=['POST'])
def register_miner():
    data = request.json
    miner_id = data.get("miner_id")
    cpu_available = data.get("cpu_available")
    ram_available = data.get("ram_available")

    if miner_id and cpu_available and ram_available:
        MINERS[miner_id] = {"cpu": cpu_available, "ram": ram_available}
        return jsonify({"message": "Miner registrovan", "miners": MINERS}), 200

    return jsonify({"error": "Neispravni podaci"}), 400


# 📡 **Dodavanje AI zadatka**
@app.route('/ai_tasks', methods=['GET'])
def get_ai_tasks():
    return jsonify({"ai_tasks": PENDING_AI_TASKS}), 200


# 📡 **Dodavanje CPU/RAM zahteva**
@app.route('/resource_request', methods=['POST'])
def add_resource_request():
    data = request.json
    requester = data.get("requester")
    cpu_needed = data.get("cpu_needed")
    ram_needed = data.get("ram_needed")

    if requester and cpu_needed and ram_needed:
        RESOURCE_REQUESTS.append({"requester": requester, "cpu": cpu_needed, "ram": ram_needed})
        return jsonify({"message": "Zahtev za CPU/RAM dodat", "requests": RESOURCE_REQUESTS}), 200

    return jsonify({"error": "Neispravni podaci"}), 400


# 📡 **Dodavanje AI zadataka u blockchain**
def fetch_ai_task():
    while True:
        if len(PENDING_AI_TASKS) < 5:
            print("🔍 Preuzimam AI zadatak sa Hugging Face...")
            try:
                dataset = load_dataset(AI_DATASET, split="train")
                sample = dataset.shuffle(seed=int(time.time())).select([0])
                task_text = sample[0]['text']
                PENDING_AI_TASKS.append({"task": task_text, "solution": "TBD"})
                print(f"📜 Novi AI zadatak dodat: {task_text[:100]}...")
            except Exception as e:
                print("❌ Greška pri preuzimanju AI zadatka!", e)
        time.sleep(30)


# ⛏ **Rudarenje bloka sa AI zadatkom i CPU/RAM uslugama**
def mine_block(previous_block, transactions, ai_tasks, resource_tasks, miner, difficulty=DIFFICULTY):
    index = previous_block.index + 1
    timestamp = int(time.time())
    previous_hash = previous_block.hash
    nonce = 0
    prefix = "0" * difficulty

    while True:
        new_block = Block(index, previous_hash, timestamp, transactions, ai_tasks, resource_tasks, miner, AI_REWARD + RESOURCE_REWARD, nonce)
        if new_block.hash.startswith(prefix):
            print(f"✅ Blok {index} iskopan | Rudar: {miner} | Nagrada: {AI_REWARD + RESOURCE_REWARD} coins | Hash: {new_block.hash}")
            return new_block
        nonce += 1


# 📡 **Rudarenje bloka**
@app.route('/mine', methods=['POST'])
def mine():
    data = request.json
    miner_address = data.get("miner")

    if not miner_address:
        return jsonify({"message": "Rudar mora poslati svoju adresu"}), 400

    if not PENDING_AI_TASKS and not RESOURCE_REQUESTS:
        return jsonify({"message": "Nema zadataka za rudarenje"}), 400

    ai_task = PENDING_AI_TASKS.pop(0) if PENDING_AI_TASKS else None
    resource_task = RESOURCE_REQUESTS.pop(0) if RESOURCE_REQUESTS else None

    new_block = blockchain.add_block([], [ai_task] if ai_task else [], [resource_task] if resource_task else [], miner_address)
    broadcast_block(new_block)
    return jsonify(new_block.__dict__), 200


# 📡 **Provera balansa rudara**
@app.route('/balance/<address>', methods=['GET'])
def get_balance(address):
    balance = sum(block.reward for block in blockchain.chain if block.miner == address)
    return jsonify({"balance": balance}), 200


# 📡 **API Endpoint za dobijanje celog blockchaina** 🔥 **(Ispravka za 404 grešku)**
@app.route('/chain', methods=['GET'])
def get_chain():
    return jsonify([block.__dict__ for block in blockchain.chain]), 200

# 📡 **Preuzimanje CPU/RAM zahteva za rudare**
@app.route('/resource_request', methods=['GET'])
def get_resource_requests():
    return jsonify({"requests": RESOURCE_REQUESTS}), 200

# 📡 **Emitovanje novog bloka svim čvorovima**
def broadcast_block(block):
    for peer in PEERS:
        try:
            requests.post(f"{peer}/mine", json=block.__dict__)
        except requests.exceptions.RequestException:
            pass


if __name__ == '__main__':
    threading.Thread(target=fetch_ai_task, daemon=True).start()
    socketio.run(app, host='0.0.0.0', port=5000)
