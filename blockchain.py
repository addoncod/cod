import time
import json
import hashlib
import threading
import requests
from datasets import load_dataset  # Hugging Face API za AI zadatke
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit

# 🔧 Konfiguracija blockchain-a
DIFFICULTY = 4
PEERS = []
PENDING_TRANSACTIONS = []
PENDING_AI_TASKS = []
AI_REWARD = 10  # 💰 Nagrada za AI rudarenje
AI_DATASET = "imdb"

app = Flask(__name__)
socketio = SocketIO(app)


class Block:
    def __init__(self, index, previous_hash, timestamp, transactions, ai_tasks, miner, reward, nonce):
        self.index = index
        self.previous_hash = previous_hash
        self.timestamp = timestamp
        self.transactions = transactions
        self.ai_tasks = ai_tasks  # 🧠 AI zadaci u bloku
        self.miner = miner  # ⛏ Adresa rudara
        self.reward = reward  # 💰 Nagrada rudaru
        self.nonce = nonce
        self.hash = self.calculate_hash()

    def calculate_hash(self):
        data_str = f"{self.index}{self.previous_hash}{self.timestamp}{self.transactions}{self.ai_tasks}{self.miner}{self.reward}{self.nonce}".encode()
        return hashlib.sha256(data_str).hexdigest()


class Blockchain:
    def __init__(self):
        self.chain = [self.create_genesis_block()]

    def create_genesis_block(self):
        return Block(0, "0", int(time.time()), [], [], "GENESIS", 0, 0)

    def add_block(self, transactions, ai_tasks, miner):
        new_block = mine_block(self.chain[-1], transactions, ai_tasks, miner)
        self.chain.append(new_block)
        return new_block


blockchain = Blockchain()


# 🔄 **Automatsko preuzimanje AI zadataka sa Hugging Face**
def fetch_ai_task():
    while True:
        if len(PENDING_AI_TASKS) < 5:  # 🛠 Ako ima manje od 5 zadataka u čekanju, dodaj novi
            print("🔍 Preuzimam AI zadatak sa Hugging Face...")
            try:
                dataset = load_dataset(AI_DATASET, split="train")
                sample = dataset.shuffle(seed=int(time.time())).select([0])
                task_text = sample[0]['text']
                PENDING_AI_TASKS.append({"task": task_text, "solution": "TBD"})
                print(f"📜 Novi AI zadatak dodat u mempool: {task_text[:100]}...")
            except Exception as e:
                print("❌ Greška pri preuzimanju AI zadatka!", e)
        time.sleep(30)


# 📡 **Endpoint za dobijanje AI zadataka**
@app.route('/ai_tasks', methods=['GET'])
def get_ai_tasks():
    if not PENDING_AI_TASKS:
        return jsonify({"message": "Trenutno nema AI zadataka"}), 200
    return jsonify({"ai_tasks": PENDING_AI_TASKS}), 200


# 📡 **Endpoint za dobijanje celog blockchaina**
@app.route('/chain', methods=['GET'])
def get_chain():
    return jsonify([block.__dict__ for block in blockchain.chain]), 200


# ⛏ **Rudarenje bloka sa AI zadatkom + nagrada**
def mine_block(previous_block, transactions, ai_tasks, miner, difficulty=DIFFICULTY):
    index = previous_block.index + 1
    timestamp = int(time.time())
    previous_hash = previous_block.hash
    nonce = 0
    prefix = "0" * difficulty

    while True:
        new_block = Block(index, previous_hash, timestamp, transactions, ai_tasks, miner, AI_REWARD, nonce)
        if new_block.hash.startswith(prefix):
            print(f"✅ Blok {index} iskopan | Rudar: {miner} | Nagrada: {AI_REWARD} coins | Hash: {new_block.hash}")
            return new_block
        nonce += 1


# 📡 **Endpoint za rudarenje (rudar šalje svoju adresu)**
@app.route('/mine', methods=['POST'])
def mine():
    data = request.json
    miner_address = data.get("miner")  # 🎯 Rudar mora poslati svoju adresu

    if not miner_address:
        return jsonify({"message": "Rudar mora poslati svoju adresu"}), 400

    if not PENDING_AI_TASKS:
        return jsonify({"message": "Nema AI zadataka za rudarenje"}), 400

    ai_task = PENDING_AI_TASKS.pop(0)  # ✅ Uklanja prvi AI zadatak
    new_block = blockchain.add_block([], [ai_task], miner_address)
    broadcast_block(new_block)
    return jsonify(new_block.__dict__), 200


# 📡 **API endpoint za proveru balansa rudara**
@app.route('/balance/<address>', methods=['GET'])
def get_balance(address):
    balance = 0
    for block in blockchain.chain:
        if block.miner == address:
            balance += block.reward  # ✅ Dodajemo nagradu u bilans
    return jsonify({"balance": balance}), 200


# 📡 **Emitovanje novog bloka svim čvorovima**
def broadcast_block(block):
    for peer in PEERS:
        try:
            requests.post(f"{peer}/mine", json=block.__dict__)
        except requests.exceptions.RequestException:
            pass


if __name__ == '__main__':
    threading.Thread(target=fetch_ai_task, daemon=True).start()  # ✅ Pokreće automatsko preuzimanje AI zadataka
    socketio.run(app, host='0.0.0.0', port=5000)
