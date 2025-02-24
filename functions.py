import time
import json
from flask import jsonify

BLOCKCHAIN_FILE = "blockchain_data.json"
WALLETS_FILE = "wallets.json"

# Globalni rječnik za korisničke resurse
USER_RESOURCES = {}

# Globalna lista za zahtjeve resursa
RESOURCE_REQUESTS = []

# 📌 Čuva blockchain u JSON fajl
def save_blockchain(blockchain):
    with open(BLOCKCHAIN_FILE, "w") as f:
        json.dump([block.__dict__ for block in blockchain], f, indent=4)

# 📌 Učitava blockchain iz JSON fajla
def load_blockchain():
    try:
        with open(BLOCKCHAIN_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return [{
            "index": 0,
            "previous_hash": "0",
            "timestamp": 0,
            "transactions": [],
            "resource_tasks": [],
            "miner": "GENESIS",
            "reward": 0,
            "nonce": 0,
            "hash": "0"
        }]

# 📌 Dodavanje balansa korisniku
def add_balance(user_address, amount):
    if not user_address or amount is None:
        return jsonify({"message": "Nedostaju parametri"}), 400

    wallets = load_wallets()
    wallets[user_address] = wallets.get(user_address, 0) + amount
    save_wallets(wallets)

    return jsonify({"message": f"{amount} coina dodato korisniku {user_address}", "balance": wallets[user_address]}), 200

# 📌 Kupovina resursa i kreiranje zahtjeva za resurse
def buy_resources(buyer, cpu, ram, seller):
    wallets = load_wallets()

    # Osiguraj da kupac i prodavač imaju wallet
    wallets[buyer] = wallets.get(buyer, 0)
    wallets[seller] = wallets.get(seller, 0)

    total_price = (cpu + ram) * 2
    if wallets.get(buyer, 0) < total_price:
        return jsonify({"error": "Nedovoljno coina"}), 400

    wallets[buyer] -= total_price
    wallets[seller] += total_price

    save_wallets(wallets)
    
    # Spremanje kupljenih resursa u globalni rječnik
    if buyer not in USER_RESOURCES:
        USER_RESOURCES[buyer] = {"cpu": 0, "ram": 0}
    USER_RESOURCES[buyer]["cpu"] += cpu
    USER_RESOURCES[buyer]["ram"] += ram

    # Kreiraj zahtjev za resurse i dodaj ga u RESOURCE_REQUESTS
    RESOURCE_REQUESTS.append({
        "buyer": buyer,
        "cpu": cpu,
        "ram": ram,
        "timestamp": int(time.time())
    })

    return jsonify({"message": "Resursi kupljeni", "balance": wallets[buyer]}), 200

# 📌 Preuzimanje balansa korisnika
def get_balance(address):
    wallets = load_wallets()
    return wallets.get(address, 0)

# 📌 Preuzimanje korisničkih resursa
def get_user_resources(user):
    resources = USER_RESOURCES.get(user, {"cpu": 0, "ram": 0})
    return jsonify({"message": "Resursi korisnika", "resources": resources}), 200

# 📌 Preuzimanje zahtjeva za resurse
def get_resource_requests():
    return jsonify({"requests": RESOURCE_REQUESTS}), 200

# 📌 Čuvanje i učitavanje wallet-a
def load_wallets():
    try:
        with open(WALLETS_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_wallets(wallets):
    with open(WALLETS_FILE, "w") as f:
        json.dump(wallets, f, indent=4)
