import time
import json
import hashlib
import threading
import requests
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
import ecdsa
from datasets import load_dataset  # Hugging Face API za AI zadatke

DIFFICULTY = 4
PEERS = []
PENDING_TRANSACTIONS = []
PENDING_AI_TASKS = []  # **Dodato: AI zadaci čekaju na rudarenje**
AI_REWARD = 10  # **Povećana nagrada za AI zadatke**
REGULAR_REWARD = 2  # **Standardna nagrada za obične transakcije**

app = Flask(__name__)
socketio = SocketIO(app)

class Block:
    def __init__(self, index, previous_hash, timestamp, transactions, ai_tasks, nonce, reward):
        self.index = index
        self.previous_hash = previous_hash
        self.timestamp = timestamp
        self.transactions = transactions
        self.ai_tasks = ai_tasks  # **Dodato: AI zadaci**
        self.nonce = nonce
        self.reward = reward
        self.hash = self.calculate_hash()

    def calculate_hash(self):
        data_str = f"{self.index}{self.previous_hash}{self.timestamp}{self.transactions}{self.ai_tasks}{self.nonce}{self.reward}".encode()
        return hashlib.sha256(data_str).hexdigest()

class Blockchain:
    def __init__(self):
        self.chain = [self.create_genesis_block()]

    def create_genesis_block(self):
        return Block(0, "0", int(time.time()), [], [], 0, 0)

    def add_block(self, transactions, ai_tasks, reward):
        new_block = mine_block(self.chain[-1], transactions, ai_tasks, reward)
        self.chain.append(new_block)
        return new_block

blockchain = Blockchain()

def mine_block(previous_block, transactions, ai_tasks, reward, difficulty=DIFFICULTY):
    index = previous_block.index + 1
    timestamp = int(time.time())
    previous_hash = previous_block.hash
    nonce = 0
    prefix = "0" * difficulty

    while True:
        new_block = Block(index, previous_hash, timestamp, transactions, ai_tasks, nonce, reward)
        if new_block.hash.startswith(prefix):
            return new_block
        nonce += 1

@app.route('/mine', methods=['POST'])
def mine():
    print(f"🔍 Provera PENDING_AI_TASKS: {PENDING_AI_TASKS}")  # **Debugging poruka**

    # **Dodato: Omogućiti rudarenje ako postoje AI zadaci ili transakcije**
    if not PENDING_TRANSACTIONS and not PENDING_AI_TASKS:
        return jsonify({"message": "Nema transakcija ni AI zadataka za rudarenje"}), 400

    reward = AI_REWARD if PENDING_AI_TASKS else REGULAR_REWARD  # **Dodeli veću nagradu ako ima AI zadataka**
    
    new_block = blockchain.add_block(PENDING_TRANSACTIONS.copy(), PENDING_AI_TASKS.copy(), reward)
    
    # **Obriši pending liste nakon uspešnog rudarenja**
    PENDING_TRANSACTIONS.clear()
    PENDING_AI_TASKS.clear()
    
    broadcast_block(new_block)
    return jsonify(new_block.__dict__), 200

@app.route('/transactions', methods=['POST'])
def receive_transaction():
    transaction = request.json
    if validate_transaction(transaction):
        PENDING_TRANSACTIONS.append(transaction)
        return jsonify({"message": "Transakcija primljena"}), 200
    return jsonify({"error": "Nevažeća transakcija"}), 400

@app.route('/ai_task', methods=['POST'])
def receive_ai_task():
    ai_task = request.json
    if "task" in ai_task and "solution" in ai_task:
        PENDING_AI_TASKS.append(ai_task)
        return jsonify({"message": "AI zadatak dodat"}), 200
    return jsonify({"error": "Neispravan AI zadatak"}), 400

def validate_transaction(transaction):
    sender_pub_key = ecdsa.VerifyingKey.from_string(bytes.fromhex(transaction["public_key"]), curve=ecdsa.SECP256k1)
    signature = bytes.fromhex(transaction["signature"])
    transaction_data = json.dumps({
        "sender": transaction["sender"],
        "recipient": transaction["recipient"],
        "amount": transaction["amount"]
    })
    return sender_pub_key.verify(signature, transaction_data.encode())

@app.route('/chain', methods=['GET'])
def get_chain():
    return jsonify([block.__dict__ for block in blockchain.chain]), 200

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

@socketio.on('new_block')
def handle_new_block(data):
    new_block = Block(**data)
    if new_block.previous_hash == blockchain.chain[-1].hash:
        blockchain.chain.append(new_block)
        emit('chain_update', [block.__dict__ for block in blockchain.chain], broadcast=True)

def broadcast_block(block):
    for peer in PEERS:
        try:
            requests.post(f"{peer}/mine", json=block.__dict__)
        except requests.exceptions.RequestException:
            pass

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
