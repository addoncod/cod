import time
import json
import threading
from flask import Flask, request, jsonify
from flask_socketio import SocketIO
from functions import *  # 📌 Importujemo sve funkcije

# 🔧 Konfiguracija blockchaina
app = Flask(__name__)
socketio = SocketIO(app)
blockchain = load_blockchain() or [{"index": 0, "previous_hash": "0", "timestamp": int(time.time()), "transactions": [], "miner": "GENESIS", "nonce": 0, "hash": "0"}]

# 📡 **Pregled kupljenih resursa korisnika**
@app.route('/user_resources/<user>', methods=['GET'])
def user_resources(user):
    user_res = get_user_resources(user)
    if not user_res:
        return jsonify({"message": "Korisnik nema kupljene resurse."}), 404
    return jsonify({"message": "Pregled resursa", "resources": user_res}), 200

# 📡 **Dodavanje CPU/RAM zahteva**
@app.route('/resource_request', methods=['POST'])
def add_request():
    data = request.json
    requester, cpu_needed, ram_needed = data.get("requester"), data.get("cpu_needed"), data.get("ram_needed")
    if not all([requester, cpu_needed, ram_needed]):
        return jsonify({"error": "Neispravni podaci"}), 400
    return jsonify({"requests": add_resource_request(requester, cpu_needed, ram_needed)}), 200

# 📡 **Kupovina CPU/RAM resursa koristeći coin**
@app.route('/buy_resources', methods=['POST'])
def buy_resources():
    data = request.json
    buyer, cpu_amount, ram_amount, seller = data.get("buyer"), data.get("cpu"), data.get("ram"), data.get("seller")

    if not all([buyer, cpu_amount, ram_amount, seller]):
        return jsonify({"error": "Neispravni podaci"}), 400

    if get_user_balance(buyer) < (cpu_amount + ram_amount) * 2:
        return jsonify({"error": "Nedovoljno coina za kupovinu"}), 400

    add_user_balance(buyer, -((cpu_amount + ram_amount) * 2))
    add_user_balance(seller, (cpu_amount + ram_amount) * 2)

    return jsonify({"message": "Uspešno kupljeni resursi", "balance": get_user_balance(buyer)}), 200

# 📡 **Provera balansa korisnika**
@app.route('/balance/<address>', methods=['GET'])
def get_balance(address):
    return jsonify({"balance": get_user_balance(address)}), 200

# 📡 **Dodavanje balansa korisniku**
@app.route('/add_balance', methods=['POST'])
def add_balance():
    data = request.json
    user_address, amount = data.get("user"), data.get("amount")
    if not all([user_address, amount]):
        return jsonify({"message": "Nedostaju parametri"}), 400
    return jsonify({"message": f"{amount} coina dodato korisniku {user_address}", "balance": add_user_balance(user_address, amount)}), 200

# 📡 **API Endpoint za preuzimanje blockchaina**
@app.route('/chain', methods=['GET'])
def get_chain():
    return jsonify(blockchain), 200

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
