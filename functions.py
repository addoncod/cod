import json
import time
import hashlib
import requests
from flask import jsonify

# 🔧 Globalne promenljive
RESOURCE_REQUESTS = []  # Lista CPU/RAM zahteva
WALLETS = {}  # Balansi korisnika
RESOURCE_PRICE = 2  # Cena resursa
BLOCKCHAIN_FILE = "blockchain_data.json"


def save_blockchain(blockchain):
    """Snimanje blockchain podataka na disk"""
    with open(BLOCKCHAIN_FILE, "w") as f:
        json.dump([block.__dict__ for block in blockchain.chain], f, indent=4)


def load_blockchain(blockchain_class):
    """Učitavanje blockchain podataka sa diska"""
    try:
        with open(BLOCKCHAIN_FILE, "r") as f:
            return [blockchain_class(**block) for block in json.load(f)]
    except (FileNotFoundError, json.JSONDecodeError):
        return [blockchain_class(0, "0", int(time.time()), [], [], "GENESIS", 0, 0)]


def get_balance(user_address):
    """Vraća balans korisnika"""
    return WALLETS.get(user_address, 0)


def add_balance(user_address, amount):
    """Dodaje balans korisniku"""
    if user_address not in WALLETS:
        WALLETS[user_address] = 0
    WALLETS[user_address] += amount
    return jsonify({"message": f"{amount} coina dodato korisniku {user_address}", "balance": WALLETS[user_address]})


def buy_resources(buyer, cpu, ram, seller):
    """Kupovina CPU/RAM resursa koristeći coin"""
    total_price = (cpu + ram) * RESOURCE_PRICE

    if WALLETS.get(buyer, 0) < total_price:
        return jsonify({"error": "Nedovoljno coina za kupovinu"}), 400

    # Prenos coina
    WALLETS[buyer] -= total_price
    WALLETS[seller] += total_price

    # Dodavanje resursa kupcu
    RESOURCE_REQUESTS.append({
        "requester": buyer,
        "cpu": cpu,
        "ram": ram
    })

    return jsonify({
        "message": "Uspešno kupljeni resursi",
        "balance": WALLETS[buyer],
        "resources": RESOURCE_REQUESTS
    }), 200


def get_user_resources(user):
    """Pregled kupljenih resursa korisnika"""
    user_res = [r for r in RESOURCE_REQUESTS if r["requester"] == user]
    return jsonify({"message": "Pregled resursa", "resources": user_res}), 200


def get_resource_requests():
    """Vraća listu svih CPU/RAM zahteva"""
    return jsonify({"requests": RESOURCE_REQUESTS}), 200
