import time
import json
import hashlib
import threading
import requests
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit

DIFFICULTY = 4
PEERS = []
PENDING_TRANSACTIONS = []
PENDING_AI_TASKS = []  # ✅ AI zadaci sada čekaju pre rudarenja!

app = Flask(__name__)
socketio = SocketIO(app)

class Block:
    def __init__(self, index, previous_hash, timestamp, transactions, ai_tasks, nonce):
        self.index = index
        self.previous_hash = previous_hash
        self.timestamp = timestamp
        self.transactions = transactions
        self.ai_tasks = ai_tasks  # ✅ AI zadaci su deo bloka!
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

# ✅ Funkcija za rudarenje AI blokova
def mine_block(previous_block, transactions, ai_tasks, difficulty=DIFFICULTY):
    index = previous_block.index + 1
    timestamp = int(time.time())
    previous_hash = previous_block.hash
    nonce = 0
    prefix = "0" * difficulty

    while True:
        new_block = Block(index, previous_hash, timestamp, transactions, ai_tasks, nonce)
        if new_block.hash.startswith(prefix):
            return new_block
        nonce += 1

# ✅ API za dodavanje AI zadatka na blockchain (admin ili eksterni API)
@app.route('/ai_task', methods=['POST'])
def receive_ai_task():
    task = request.json
    if "task" in task:
        PENDING_AI_TASKS.append(task)
        return jsonify({"message": "AI zadatak primljen"}), 200
    return jsonify({"error": "Neispravan AI zadatak"}), 400

# ✅ Rudari sada mogu dobiti AI zadatke od servera
@app.route('/ai_tasks', methods=['GET'])
def get_ai_tasks():
    return jsonify({"ai_tasks": PENDING_AI_TASKS}), 200

# ✅ Popravljena funkcija rudarenja (AI zadaci su sada deo blockchaina)
@app.route('/mine', methods=['POST'])
def mine():
    if not PENDING_TRANSACTIONS and not PENDING_AI_TASKS:
        return jsonify({"message": "Nema transakcija ni AI zadataka za rudarenje"}), 400

    new_block = blockchain.add_block(PENDING_TRANSACTIONS.copy(), PENDING_AI_TASKS.copy())
    PENDING_TRANSACTIONS.clear()
    PENDING_AI_TASKS.clear()  # ✅ AI zadaci se brišu nakon rudarenja!
    broadcast_block(new_block)
    return jsonify(new_block.__dict__), 200

@app.route('/chain', methods=['GET'])
def get_chain():
    return jsonify([block.__dict__ for block in blockchain.chain]), 200

def broadcast_block(block):
    for peer in PEERS:
        try:
            requests.post(f"{peer}/mine", json=block.__dict__)
        except requests.exceptions.RequestException:
            pass

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
