import time
import json
import hashlib
import threading
import requests
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
import ecdsa

DIFFICULTY = 4
PEERS = []
PENDING_TRANSACTIONS = []

app = Flask(__name__)
socketio = SocketIO(app)

class Block:
    def __init__(self, index, previous_hash, timestamp, transactions, nonce):
        self.index = index
        self.previous_hash = previous_hash
        self.timestamp = timestamp
        self.transactions = transactions
        self.nonce = nonce
        self.hash = self.calculate_hash()

    def calculate_hash(self):
        data_str = f"{self.index}{self.previous_hash}{self.timestamp}{self.transactions}{self.nonce}".encode()
        return hashlib.sha256(data_str).hexdigest()

class Blockchain:
    def __init__(self):
        self.chain = [self.create_genesis_block()]

    def create_genesis_block(self):
        return Block(0, "0", int(time.time()), [], 0)

    def add_block(self, transactions):
        new_block = mine_block(self.chain[-1], transactions)
        self.chain.append(new_block)
        return new_block

blockchain = Blockchain()

def mine_block(previous_block, transactions, difficulty=DIFFICULTY):
    index = previous_block.index + 1
    timestamp = int(time.time())
    previous_hash = previous_block.hash
    nonce = 0
    prefix = "0" * difficulty

    while True:
        new_block = Block(index, previous_hash, timestamp, transactions, nonce)
        if new_block.hash.startswith(prefix):
            return new_block
        nonce += 1

@app.route('/mine', methods=['POST'])
def mine():
    if not PENDING_TRANSACTIONS:
        return jsonify({"message": "Nema transakcija za rudarenje"}), 400

    new_block = blockchain.add_block(PENDING_TRANSACTIONS.copy())
    PENDING_TRANSACTIONS.clear()
    broadcast_block(new_block)
    return jsonify(new_block.__dict__), 200

@app.route('/transactions', methods=['POST'])
def receive_transaction():
    transaction = request.json
    if validate_transaction(transaction):
        PENDING_TRANSACTIONS.append(transaction)
        return jsonify({"message": "Transakcija primljena"}), 200
    return jsonify({"error": "Nevažeća transakcija"}), 400

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
