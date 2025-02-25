import time
import json
import logging
from flask import jsonify

# Konfiguracija logiranja
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

BLOCKCHAIN_FILE = "blockchain_data.json"
WALLETS_FILE = "wallets.json"

# Globalni rječnik za korisničke resurse
USER_RESOURCES = {}

# Globalna lista za zahtjeve resursa
RESOURCE_REQUESTS = []

# Globalna lista rudara
REGISTERED_MINERS = {}

def save_blockchain(blockchain):
    try:
        with open(BLOCKCHAIN_FILE, "w") as f:
            json.dump([block for block in blockchain], f, indent=4)
        logging.info("✅ Blockchain uspješno spremljen.")
    except Exception as e:
        logging.error(f"❌ Greška pri spremanju blockchaina: {e}")

def load_blockchain():
    try:
        with open(BLOCKCHAIN_FILE, "r") as f:
            blockchain = json.load(f)
            logging.info("✅ Blockchain uspješno učitan.")
            return blockchain
    except (FileNotFoundError, json.JSONDecodeError):
        logging.warning("⚠️  Blockchain datoteka ne postoji ili je oštećena, kreiram GENESIS blok.")
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

def add_balance(user_address, amount):
    if not user_address or amount is None:
        return jsonify({"message": "❌ Nedostaju parametri"}), 400

    wallets = load_wallets()
    wallets[user_address] = wallets.get(user_address, 0) + amount
    save_wallets(wallets)
    logging.info(f"✅ Dodano {amount} coina korisniku {user_address}.")
    return jsonify({"message": f"{amount} coina dodato korisniku {user_address}", "balance": wallets[user_address]}), 200

def buy_resources(buyer, cpu, ram, seller):
    wallets = load_wallets()

    # Osiguraj da kupac i prodavač imaju wallet
    wallets[buyer] = wallets.get(buyer, 0)
    wallets[seller] = wallets.get(seller, 0)

    total_price = (cpu + ram) * 2
    if wallets.get(buyer, 0) < total_price:
        return jsonify({"error": "❌ Nedovoljno coina"}), 400

    wallets[buyer] -= total_price
    wallets[seller] += total_price
    save_wallets(wallets)

    if buyer not in USER_RESOURCES:
        USER_RESOURCES[buyer] = {"cpu": 0, "ram": 0}
    USER_RESOURCES[buyer]["cpu"] += cpu
    USER_RESOURCES[buyer]["ram"] += ram

    RESOURCE_REQUESTS.append({
        "buyer": buyer,
        "cpu": cpu,
        "ram": ram,
        "timestamp": int(time.time())
    })
    logging.info(f"✅ Resursi kupljeni: Kupac {buyer}, CPU {cpu}, RAM {ram} MB, Prodavač {seller}")
    return jsonify({"message": "Resursi kupljeni", "balance": wallets[buyer]}), 200

def get_balance(address):
    wallets = load_wallets()
    return wallets.get(address, 0)

def get_user_resources(user):
    resources = USER_RESOURCES.get(user, {"cpu": 0, "ram": 0})
    return jsonify({"message": "📊 Resursi korisnika", "resources": resources}), 200

def get_resource_requests():
    return jsonify({"requests": RESOURCE_REQUESTS}), 200

def assign_resources_to_user(buyer, cpu, ram):
    if not buyer or cpu is None or ram is None:
        return jsonify({"error": "❌ Neispravni parametri"}), 400

    if buyer not in USER_RESOURCES:
        USER_RESOURCES[buyer] = {"cpu": 0, "ram": 0}

    USER_RESOURCES[buyer]["cpu"] += cpu
    USER_RESOURCES[buyer]["ram"] += ram

    logging.info(f"✅ Resursi dodijeljeni: {cpu} CPU i {ram} MB RAM-a kupcu {buyer}.")
    return jsonify({"message": "✅ Resursi dodijeljeni", "resources": USER_RESOURCES[buyer]}), 200

def register_miner(miner_id, cpu_available, ram_available):
    if not miner_id or cpu_available is None or ram_available is None:
        return jsonify({"error": "❌ Neispravni podaci za rudara"}), 400

    REGISTERED_MINERS[miner_id] = {"cpu": cpu_available, "ram": ram_available}
    wallets = load_wallets()
    wallets.setdefault(miner_id, 0)  # Ako miner nema wallet, postavi ga na 0
    save_wallets(wallets)

    logging.info(f"⛏️  Rudar {miner_id} registriran sa {cpu_available} CPU i {ram_available} MB RAM-a.")
    return jsonify({"message": "✅ Rudar uspješno registriran", "miners": REGISTERED_MINERS}), 200

def load_wallets():
    try:
        with open(WALLETS_FILE, "r") as f:
            wallets = json.load(f)
            logging.info("✅ Walletovi uspješno učitani.")
            return wallets
    except (FileNotFoundError, json.JSONDecodeError):
        logging.warning("⚠️  Wallet datoteka ne postoji ili je oštećena, kreiram novu.")
        return {}

def save_wallets(wallets):
    try:
        with open(WALLETS_FILE, "w") as f:
            json.dump(wallets, f, indent=4)
        logging.info("✅ Walletovi uspješno spremljeni.")
    except Exception as e:
        logging.error(f"❌ Greška pri spremanju walletova: {e}")
