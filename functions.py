import json
import time
import requests
import hashlib

# 🔧 Konfiguracija
RESOURCE_REQUESTS = []
WALLETS = {}
PEERS = []
BLOCKCHAIN_FILE = "blockchain_data.json"

# 📡 **Čuvanje i učitavanje blockchain podataka**
def load_blockchain():
    try:
        with open(BLOCKCHAIN_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_blockchain(chain):
    with open(BLOCKCHAIN_FILE, "w") as f:
        json.dump(chain, f, indent=4)

# 📡 **Pregled kupljenih resursa korisnika**
def get_user_resources(user):
    user_res = [req for req in RESOURCE_REQUESTS if req["requester"] == user]
    if not user_res:
        return None
    return user_res

# 📡 **Dodavanje CPU/RAM zahteva**
def add_resource_request(requester, cpu_needed, ram_needed):
    RESOURCE_REQUESTS.append({"requester": requester, "cpu": cpu_needed, "ram": ram_needed})
    return RESOURCE_REQUESTS

# 📡 **Provera balansa korisnika**
def get_user_balance(user_address):
    return WALLETS.get(user_address, 0)

# 📡 **Dodavanje balansa korisniku**
def add_user_balance(user_address, amount):
    WALLETS[user_address] = WALLETS.get(user_address, 0) + amount
    return WALLETS[user_address]

# 📡 **Emitovanje bloka u P2P mrežu**
def broadcast_block(block):
    for peer in PEERS:
        try:
            requests.post(f"{peer}/new_block", json=block)
        except requests.exceptions.RequestException:
            pass
