import time
import json
import hashlib
import threading
import requests
from datasets import load_dataset  # Hugging Face API za AI zadatke
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit

# ⚡ Konfiguracija blockchain-a
DIFFICULTY = 4
PEERS = []
PENDING_TRANSACTIONS = []
PENDING_AI_TASKS = []  # ✨ Lista AI zadataka koji čekaju rudarenje
AI_DATASET = "imdb"  # Hugging Face dataset

app = Flask(__name__)
socketio = SocketIO(app)


class Block:
    def __init__(self, index, previous_hash, timestamp, transactions, ai_tasks, nonce):
        self.index = index
        self.previous_hash = previous_hash
        self.timestamp = timestamp
        self.transactions = transactions
        self.ai_tasks = ai_tasks  # ✅ Blok sada podržava AI zadatke
        self.nonce = nonce
        self.hash = self.calculate_hash()

    def calculate_hash(self):
        data_str = f"{self.index}{self.previous_hash}{self.timestamp}{self.transactions}{self.ai_tasks}{self.nonce}".encode()
        return hashlib.sha256(data_str).hexdigest()


class Blockchain:
    def __init__(self):
        self.chain = [self.create_genesis_block()]

    def create_genesis_block(self):
        return Block(0, "0", int(time.time()), [], [], 0)

    def add_block(self, transactions, ai_tasks):
        new_block = mine_block(self.chain[-1], transactions, ai_tasks)
        self.chain.append(new_block)
        return new_block


blockchain = Blockchain()


# ⚙️ Automatsko preuzimanje AI zadataka sa Hugging Face API-ja
def fetch_ai_task():
    while True:
        print("🔍 Preuzimam AI zadatak sa Hugging Face...")
        try:
            dataset = load_dataset(AI_DATASET, split="train")
            sample = dataset.shuffle(seed=int(time.time())).select([0])  # Nasumičan AI zadatak
            task_text = sample[0]['text']
            PENDING_AI_TASKS.append({"task": task_text, "solution": "TBD"})
            print(f"📜 Novi AI zadatak dodat: {task_text[:100]}...")
        except Exception as e:
            print("❌ Greška pri preuzimanju AI zadatka!", e)

        time.sleep(30)  # ✅ Svakih 30 sekundi dodaje novi AI zadatak


# ⛏ Rudarenje bloka

def mine_block(previous_block, transactions, ai_tasks, difficulty=DIFFICULTY):
    index = previous_block.index + 1
    timestamp = int(time.time())
    previous_hash = previous_block.hash
    nonce = 0
    prefix = "0" * difficulty

    while True:
        new_block = Block(index, previous_hash, timestamp, transactions, ai_tasks, nonce)
        if new_block.hash.startswith(prefix):
            print(f"✅ Blok {index} iskopan | Nonce: {nonce} | Hash: {new_block.hash}")
            return new_block
        nonce += 1


# 📡 Endpoint za dobijanje AI zadataka
@app.route('/ai_tasks', methods=['GET'])
def get_ai_tasks():
    return jsonify({"ai_tasks": PENDING_AI_TASKS}), 200


# 📡 Endpoint za rudarenje (miner preuzima zadatak)
@app.route('/mine', methods=['POST'])
def mine():
    if not PENDING_AI_TASKS:
        return jsonify({"message": "Nema AI zadataka za rudarenje"}), 400

    ai_task = PENDING_AI_TASKS.pop(0)  # ✅ Skida prvi AI zadatak
    new_block = blockchain.add_block([], [ai_task])
    broadcast_block(new_block)
    return jsonify(new_block.__dict__), 200


# 📡 Endpoint za dohvaćanje blockchaina
@app.route('/chain', methods=['GET'])
def get_chain():
    return jsonify([block.__dict__ for block in blockchain.chain]), 200


# 📡 Emitovanje novog bloka svim čvorovima
def broadcast_block(block):
    for peer in PEERS:
        try:
            requests.post(f"{peer}/mine", json=block.__dict__)
        except requests.exceptions.RequestException:
            pass


if __name__ == '__main__':
    threading.Thread(target=fetch_ai_task, daemon=True).start()  # ✅ Pokreće automatsko preuzimanje AI zadataka
    socketio.run(app, host='0.0.0.0', port=5000)
