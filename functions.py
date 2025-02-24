import json
import hashlib
import requests
import time
import ecdsa

# 🔧 Globalne promenljive (biće povezane sa blockchain.py)
RESOURCE_REQUESTS = []
PENDING_TRANSACTIONS = []
PEERS = []
WALLETS = {}

RESOURCE_REWARD = 5
RESOURCE_PRICE = 2


# 📡 **CPU/RAM tržište - Pregled zahteva**
def get_resource_requests():
    return {"requests": RESOURCE_REQUESTS}


# 📡 **Dodavanje CPU/RAM zahteva**
def add_resource_request(data):
    requester = data.get("requester")
    cpu_needed = data.get("cpu_needed")
    ram_needed = data.get("ram_needed")

    if not all([requester, cpu_needed, ram_needed]):
        return {"error": "Neispravni podaci"}, 400

    RESOURCE_REQUESTS.append({"requester": requester, "cpu": cpu_needed, "ram": ram_needed})
    return {"message": "Zahtev za CPU/RAM dodat"}, 200


# 📡 **Kupovina CPU/RAM resursa koristeći coin**
def buy_resources(data):
    buyer = data.get("buyer")
    cpu_amount = data.get("cpu")
    ram_amount = data.get("ram")
    seller = data.get("seller")

    if not all([buyer, cpu_amount, ram_amount, seller]):
        return {"error": "Neispravni podaci"}, 400

    total_price = (cpu_amount + ram_amount) * RESOURCE_PRICE

    if WALLETS.get(buyer, 0) < total_price:
        return {"error": "Nedovoljno coina za kupovinu"}, 400

    WALLETS[buyer] -= total_price
    WALLETS[seller] += total_price

    RESOURCE_REQUESTS.append({
        "requester": buyer,
        "cpu": cpu_amount,
        "ram": ram_amount
    })

    return {"message": "Uspešno kupljeni resursi"}, 200


# 📡 **Validacija transakcija koristeći ECDSA**
def validate_transaction(transaction):
    sender_pub_key = ecdsa.VerifyingKey.from_string(bytes.fromhex(transaction["public_key"]), curve=ecdsa.SECP256k1)
    signature = bytes.fromhex(transaction["signature"])
    transaction_data = json.dumps({
        "sender": transaction["sender"],
        "recipient": transaction["recipient"],
        "amount": transaction["amount"]
    })

    return sender_pub_key.verify(signature, transaction_data.encode())


# 📡 **Dodavanje transakcije**
def add_transaction(data):
    if validate_transaction(data):
        PENDING_TRANSACTIONS.append(data)
        return {"message": "Transakcija validna i dodata"}, 200
    return {"error": "Nevalidna transakcija"}, 400


# 📡 **Pregled transakcija**
def get_transactions():
    return {"transactions": PENDING_TRANSACTIONS}


# 📡 **Pregled čvorova**
def get_peers():
    return {"peers": PEERS}


# 📡 **Dodavanje P2P čvora**
def register_peer(data):
    peer = data.get("peer")
    if peer and peer not in PEERS:
        PEERS.append(peer)
        return {"message": "Čvor dodat"}, 200
    return {"error": "Neispravan čvor"}, 400


# 📡 **Pregled balansa korisnika**
def get_balance(address):
    balance = WALLETS.get(address, 0)
    return {"balance": balance}, 200


# 📡 **Dodavanje balansa korisniku (za testiranje)**
def add_balance(data):
    user_address = data.get("user")
    amount = data.get("amount")

    if not all([user_address, amount]):
        return {"message": "Nedostaju parametri"}, 400

    WALLETS[user_address] = WALLETS.get(user_address, 0) + amount
    return {"message": f"{amount} coina dodato korisniku {user_address}", "balance": WALLETS[user_address]}, 200
