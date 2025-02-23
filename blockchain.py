import time
import json
import hashlib
import threading
import requests
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from datasets import load_dataset  # Hugging Face API za AI zadatke

# Blockchain konfiguracija
DIFFICULTY = 4  # Početna težina rudarenja
PEERS = []  # Spisak povezanih čvorova
PENDING_TRANSACTIONS = []  # Mempool za transakcije
PENDING_AI_TASKS = []  # Spisak AI zadataka

# Flask API za blockchain
app = Flask(__name__)
socketio = SocketIO(app)

# ✅ Klasa za blok
class Block:
    def __init__(self, index, previous_hash, timestamp, transactions, nonce, ai_task=None, ai_result=None):
        self.index = index
        self.previous_hash = previous_hash
        self.timestamp = timestamp
        self.transactions = transactions
        self.nonce = nonce
        self.ai_task = ai_task  # AI zadatak (opciono)
        self.ai_result = ai_result  # AI rezultat (opciono)
        self.hash = self.calculate_hash()

    def calculate_hash(self):
        data_str = f"{self.index}{self.previous_hash}{self.timestamp}{self.transactions}{self.nonce}{self.ai_task}{self.ai_result}".encode()
        return hashlib.sha256(data_str).hexdigest()

# ✅ Blockchain klasa
class Blockchain:
    def __init__(self):
        self.chain = [self.create_genesis_block()]

    def create_genesis_block(self):
        return Block(0, "0", int(time.time()), [], 0)

    def add_block(self, transactions, ai_task=None, ai_result=None):
        new_block = mine_block(self.chain[-1], transactions, ai_task, ai_result)
        self.chain.append(new_block)
        return new_block

blockchain = Blockchain()

# ✅ Funkcija za rudarenje (AI Proof-of-Work)
def mine_block(previous_block, transactions, ai_task=None, ai_result=None, difficulty=DIFFICULTY):
    index = previous_block.index + 1
    timestamp = int(time.time())
    previous_hash = previous_block.hash
    nonce = 0
    prefix = "0" * difficulty

    while True:
        new_block = Block(index, previous_hash, timestamp, transactions, nonce, ai_task, ai_result)
        if new_block.hash.startswith(prefix):
            return new_block
        nonce += 1

# ✅ Preuzimanje AI zadataka sa Hugging Face-a
def fetch_ai_task():
    try:
        dataset = load_dataset("imdb")  # Koristimo IMDB dataset (može se promeniti)
        sample = dataset["train"][0]  # Uzima prvi zadatak iz skupa
        task = {
            "text": sample["text"],
            "label": sample["label"]  # Sentiment (0 = negativno, 1 = pozitivno)
        }
        return task
    except Exception as e:
        print(f"⚠️ Greška pri učitavanju AI zadatka: {e}")
        return None

# ✅ API Endpoint za rudarenje sa AI zadacima
@app.route('/mine', methods=['POST'])
def mine():
    if not PENDING_TRANSACTIONS and not PENDING_AI_TASKS:
        return jsonify({"message": "Nema transakcija ni AI zadataka za rudarenje"}), 400

    ai_task = fetch_ai_task() if PENDING_AI_TASKS else None
    ai_result = None  # Rudari će rešiti AI zadatak
    new_block = blockchain.add_block(PENDING_TRANSACTIONS.copy(), ai_task, ai_result)
    
    PENDING_TRANSACTIONS.clear()
    PENDING_AI_TASKS.clear()

    broadcast_block(new_block)
    return jsonify(new_block.__dict__), 200

# ✅ API Endpoint za prijem transakcija
@app.route('/transactions', methods=['POST'])
def receive_transaction():
    transaction = request.json
    PENDING_TRANSACTIONS.append(transaction)
    return jsonify({"message": "Transakcija primljena"}), 200

# ✅ API Endpoint za preuzimanje blockchaina
@app.route('/chain', methods=['GET'])
def get_chain():
    return jsonify([block.__dict__ for block in blockchain.chain]), 200

# ✅ API Endpoint za dodavanje AI zadatka
@app.route('/ai_task', methods=['POST'])
def add_ai_task():
    ai_task = request.json
    PENDING_AI_TASKS.append(ai_task)
    return jsonify({"message": "AI zadatak primljen"}), 200

# ✅ API Endpoint za proveru balansa korisnika
@app.route('/balance/<address>', methods=['GET'])
def get_balance(address):
    balance = 0
    for block in blockchain.chain:
        for tx in block.transactions:
            if tx["recipient"] == address:
                balance += tx["amount"]
            if tx["sender"] == address:
                balance -= tx["amount"]
    return jsonify({"balance": balance}), 200

# ✅ Sinhronizacija blokova među čvorovima
@socketio.on('new_block')
def handle_new_block(data):
    new_block = Block(**data)
    if new_block.previous_hash == blockchain.chain[-1].hash:
        blockchain.chain.append(new_block)
        emit('chain_update', [block.__dict__ for block in blockchain.chain], broadcast=True)

# ✅ Emitovanje novog bloka svim čvorovima
def broadcast_block(block):
    for peer in PEERS:
        try:
            requests.post(f"{peer}/mine", json=block.__dict__)
        except requests.exceptions.RequestException:
            pass

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
