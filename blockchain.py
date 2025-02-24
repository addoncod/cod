import time
import json
import hashlib
import threading
import requests
import ecdsa
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit

# 🔧 Blockchain konfiguracija
DIFFICULTY = 4
PEERS = []
PENDING_TRANSACTIONS = []
RESOURCE_REQUESTS = []  # 📌 Lista CPU/RAM zahteva
MINERS = {}
WALLETS = {}
USED_TXNS = set()  # 📌 Sprečavanje duplih troškova
BLOCKCHAIN_FILE = "blockchain_data.json"
RESOURCE_REWARD = 5
RESOURCE_PRICE = 2

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


class Blockchain:
    def __init__(self):
        self.chain = self.load_blockchain()

    def create_genesis_block(self):
        return Block(0, "0", int(time.time()), [], [], "GENESIS", 0, 0)

    def load_blockchain(self):
        try:
            with open(BLOCKCHAIN_FILE, "r") as f:
                return [Block(**block) for block in json.load(f)]
        except (FileNotFoundError, json.JSONDecodeError):
            return [self.create_genesis_block()]

    def save_blockchain(self):
        with open(BLOCKCHAIN_FILE, "w") as f:
            json.dump([block.__dict__ for block in self.chain], f, indent=4)

    def add_block(self, transactions, resource_tasks, miner):
        new_block = mine_block(self.chain[-1], transactions, resource_tasks, miner)
        self.chain.append(new_block)
        self.save_blockchain()
        broadcast_block(new_block)
        return new_block


blockchain = Blockchain()


# 📡 **Validacija transakcija koristeći ECDSA**
def validate_transaction(transaction):
    sender_pub_key = ecdsa.VerifyingKey.from_string(bytes.fromhex(transaction["public_key"]), curve=ecdsa.SECP256k1)
    signature = bytes.fromhex(transaction["signature"])
    transaction_data = json.dumps({
        "sender": transaction["sender"],
        "recipient": transaction["recipient"],
        "amount": transaction["amount"]
    })
    
    if sender_pub_key.verify(signature, transaction_data.encode()):
        if transaction["txid"] in USED_TXNS:
            return False  # 🚨 Sprečavanje duplih troškova
        USED_TXNS.add(transaction["txid"])
        return True
    return False


# 📡 **Dodavanje transakcija**
@app.route('/add_transaction', methods=['POST'])
def add_transaction():
    data = request.json
    if validate_transaction(data):
        PENDING_TRANSACTIONS.append(data)
        return jsonify({"message": "Transakcija validna i dodata"}), 200
    return jsonify({"error": "Nevalidna transakcija"}), 400


# 📡 **Rudarenje koristeći SHA-256**
def mine_block(previous_block, transactions, resource_tasks, miner):
    index = previous_block.index + 1
    timestamp = int(time.time())
    previous_hash = previous_block.hash
    nonce = 0
    prefix = "0" * DIFFICULTY

    while True:
        new_block = Block(index, previous_hash, timestamp, transactions, resource_tasks, miner, RESOURCE_REWARD, nonce)
        if new_block.hash.startswith(prefix):
            print(f"✅ Blok {index} iskopan | Rudar: {miner} | Nagrada: {RESOURCE_REWARD} coins | Hash: {new_block.hash}")

            # 💰 Dodaj nagradu rudaru
            WALLETS[miner] = WALLETS.get(miner, 0) + RESOURCE_REWARD
            return new_block
        nonce += 1


# 📡 **Distribuirani P2P sistem - Primanje blokova**
@app.route('/new_block', methods=['POST'])
def receive_new_block():
    block_data = request.json
    new_block = Block(**block_data)

    last_block = blockchain.chain[-1]
    if new_block.previous_hash == last_block.hash:
        blockchain.chain.append(new_block)
        blockchain.save_blockchain()
        return jsonify({"message": "Blok prihvaćen"}), 200
    return jsonify({"error": "Nevalidan blok"}), 400


# 📡 **Dodavanje P2P čvorova**
@app.route('/register_peer', methods=['POST'])
def register_peer():
    data = request.json
    peer = data.get("peer")
    if peer and peer not in PEERS:
        PEERS.append(peer)
        return jsonify({"message": "Čvor dodat"}), 200
    return jsonify({"error": "Neispravan čvor"}), 400


# 📡 **Pregled čvorova u mreži**
@app.route('/peers', methods=['GET'])
def get_peers():
    return jsonify({"peers": PEERS}), 200


# 📡 **Emitovanje bloka u P2P mrežu**
def broadcast_block(block):
    for peer in PEERS:
        try:
            requests.post(f"{peer}/new_block", json=block.__dict__)
        except requests.exceptions.RequestException:
            pass


# 📡 **Pregled blockchaina**
@app.route('/chain', methods=['GET'])
def get_chain():
    return jsonify([block.__dict__ for block in blockchain.chain]), 200


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
