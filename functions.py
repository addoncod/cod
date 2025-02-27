import time
import json
import logging
import threading
from flask import Flask, request, jsonify

# Konfiguracija logiranja
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Datoteke za pohranu podataka
BLOCKCHAIN_FILE = "blockchain_data.json"
WALLETS_FILE = "wallets.json"

# Globalni rječnici i liste
USER_RESOURCES = {}         # Resursi korisnika (npr. CPU, RAM)
RESOURCE_REQUESTS = []      # Lista zahtjeva za resurse
REGISTERED_MINERS = {}      # Evidencija aktivnih minera

# Parametri za izračun vrijednosti resursa (u smislu izrudarenih Monera)
# Cilj: 2 CPU i 2GB RAM (2048 MB) daje potencijalni prinos ≈ 0.00001 XMR u 24 sata,
# tj. oko 4.17e-7 XMR po satu, prije primjene diskonta.
MONERO_PER_CPU_PER_HOUR = 1.0e-7       # XMR po CPU jedinici u satu
MONERO_PER_RAM_PER_HOUR = 1.058e-10     # XMR po MB RAM-a u satu
DISCOUNT_FACTOR = 0.6                  # Kupac dobiva 60% potencijalnog prinosa

# Glavni wallet (gdje se skuplja fee)
MAIN_WALLET = "MAIN_WALLET"

app = Flask(__name__)

# --- Funkcije za rad s blockchainom i walletovima ---

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

    if not REGISTERED_MINERS:
        return jsonify({"error": "❌ Nema aktivnih minera"}), 400

    miner_contributions = {}
    remaining_cpu = cpu
    remaining_ram = ram

    miners = []
    for miner_id, resources in REGISTERED_MINERS.items():
        miners.append({
            "miner_id": miner_id,
            "cpu": resources["cpu"],
            "ram": resources["ram"]
        })
        miner_contributions[miner_id] = {"cpu": 0, "ram": 0}

    num_miners = len(miners)
    ideal_cpu = remaining_cpu / num_miners
    ideal_ram = remaining_ram / num_miners

    for miner in miners:
        allocated_cpu = min(ideal_cpu, miner["cpu"])
        allocated_ram = min(ideal_ram, miner["ram"])
        miner_contributions[miner["miner_id"]]["cpu"] += allocated_cpu
        miner_contributions[miner["miner_id"]]["ram"] += allocated_ram
        remaining_cpu -= allocated_cpu
        remaining_ram -= allocated_ram

        REGISTERED_MINERS[miner["miner_id"]]["cpu"] -= allocated_cpu
        REGISTERED_MINERS[miner["miner_id"]]["ram"] -= allocated_ram
        miner["cpu"] -= allocated_cpu
        miner["ram"] -= allocated_ram

    while (remaining_cpu > 0 or remaining_ram > 0) and any(m["cpu"] > 0 or m["ram"] > 0 for m in miners):
        available_miners = [m for m in miners if m["cpu"] > 0 or m["ram"] > 0]
        n_avail = len(available_miners)
        extra_cpu_share = remaining_cpu / n_avail if n_avail else 0
        extra_ram_share = remaining_ram / n_avail if n_avail else 0

        for miner in available_miners:
            additional_cpu = min(extra_cpu_share, miner["cpu"])
            additional_ram = min(extra_ram_share, miner["ram"])
            miner_contributions[miner["miner_id"]]["cpu"] += additional_cpu
            miner_contributions[miner["miner_id"]]["ram"] += additional_ram
            remaining_cpu -= additional_cpu
            remaining_ram -= additional_ram

            REGISTERED_MINERS[miner["miner_id"]]["cpu"] -= additional_cpu
            REGISTERED_MINERS[miner["miner_id"]]["ram"] -= additional_ram
            miner["cpu"] -= additional_cpu
            miner["ram"] -= additional_ram

        if not any(m["cpu"] > 0 or m["ram"] > 0 for m in available_miners):
            break

    if remaining_cpu > 0 or remaining_ram > 0:
        return jsonify({"error": "❌ Nedovoljno resursa kod aktivnih minera za isporuku traženih resursa."}), 400

    if buyer not in USER_RESOURCES:
        USER_RESOURCES[buyer] = {"cpu": 0, "ram": 0}
    USER_RESOURCES[buyer]["cpu"] += cpu
    USER_RESOURCES[buyer]["ram"] += ram

    logging.info(f"✅ Resursi dodijeljeni kupcu {buyer}: CPU {cpu}, RAM {ram} MB.")
    logging.info(f"Distribucija po rudarima: {miner_contributions}")

    return jsonify({
        "message": "✅ Resursi dodijeljeni",
        "user_resources": USER_RESOURCES[buyer],
        "miner_contributions": miner_contributions
    }), 200

def register_miner(miner_id, cpu_available, ram_available):
    if not miner_id or cpu_available is None or ram_available is None:
        return jsonify({"error": "❌ Neispravni podaci za rudara"}), 400

    if miner_id not in REGISTERED_MINERS:
        REGISTERED_MINERS[miner_id] = {"cpu": cpu_available, "ram": ram_available}
        wallets = load_wallets()
        wallets.setdefault(miner_id, 0)
        save_wallets(wallets)
        logging.info(f"⛏️ Rudar {miner_id} uspešno registrovan sa {cpu_available} CPU i {ram_available} MB RAM-a.")
    else:
        logging.info(f"ℹ️ Rudar {miner_id} je već registrovan sa {REGISTERED_MINERS[miner_id]['cpu']} CPU i {REGISTERED_MINERS[miner_id]['ram']} MB RAM-a.")

    return jsonify({"message": "✅ Rudar uspešno registrovan", "miners": REGISTERED_MINERS}), 200


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

# --- Novi endpointi: resource_usage i resource_value ---

@app.route("/resource_usage", methods=["POST"])
def resource_usage():
    """
    Endpoint za naplatu korištenja CPU i RAM resursa tijekom određenog vremena.
    Klijent plaća ukupni trošak, a nakon oduzimanja 10% fee (koji ide u glavni wallet),
    preostalih 90% se distribuira među rudarima.
    """
    data = request.get_json()
    buyer = data.get("buyer")
    try:
        cpu = float(data.get("cpu", 0))
        ram = float(data.get("ram", 0))
        duration = float(data.get("duration", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Neispravne vrijednosti za CPU, RAM ili trajanje"}), 400

    if not buyer or cpu <= 0 or ram <= 0 or duration <= 0:
        return jsonify({"error": "Kupac, CPU, RAM i trajanje moraju biti zadani i veći od 0"}), 400

    # Osiguraj minimalno trajanje od 60 minuta (1 sat)
    if duration < 60:
        duration = 60
    elif duration > 60:
        duration = 60  # Fiksiramo na 60 minuta za ovaj model

    # Izračun troška: primjer formule – (cpu + ram) * 2 (vrijednost se može prilagoditi)
    total_cost = (cpu + ram) * 2

    wallets = load_wallets()
    buyer_balance = wallets.get(buyer, 0)
    if buyer_balance < total_cost:
        return jsonify({"error": "Nedovoljno sredstava u kupčevom walletu"}), 400

    # Skinemo ukupni trošak s kupčevog walleta
    wallets[buyer] = buyer_balance - total_cost

    # Računamo fee (10%) i miner pool (90%)
    fee = total_cost * 0.1
    miner_pool = total_cost - fee
    wallets[MAIN_WALLET] = wallets.get(MAIN_WALLET, 0) + fee

    # Distribucija miner nagrada – ovdje se koristi jednostavna raspodjela (možete zamijeniti s share sistemom)
    num_miners = len(REGISTERED_MINERS)
    if num_miners == 0:
        return jsonify({"error": "Nema aktivnih minera"}), 400

    miner_share = miner_pool / num_miners
    miner_rewards = {}
    for miner_id in REGISTERED_MINERS.keys():
        wallets[miner_id] = wallets.get(miner_id, 0) + miner_share
        miner_rewards[miner_id] = miner_share

    save_wallets(wallets)
    logging.info(f"💰 Resource usage: Kupac {buyer} plati {total_cost} coina, fee {fee} coina, "
                 f"raspodijeljeno među {num_miners} rudar(a) ({miner_share} po rudaru).")

    return jsonify({
        "message": "Resource usage obračunat",
        "buyer": buyer,
        "total_cost": total_cost,
        "fee": fee,
        "miner_rewards": miner_rewards
    }), 200

@app.route("/resource_value", methods=["POST"])
def resource_value():
    """
    Endpoint za izračun vrijednosti CPU i RAM resursa u Rakia Coin.
    Izračun:
      - Potencijalni prinos u 1 satu rudarenja = (cpu * MONERO_PER_CPU_PER_HOUR) + (ram * MONERO_PER_RAM_PER_HOUR)
      - Vrijednost za kupca = potencijalni prinos * DISCOUNT_FACTOR
    """
    try:
        cpu = float(request.json.get("cpu", 0))
        ram = float(request.json.get("ram", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Neispravne vrijednosti za CPU ili RAM"}), 400

    potential_monero = cpu * MONERO_PER_CPU_PER_HOUR + ram * MONERO_PER_RAM_PER_HOUR
    resource_value_rakia = potential_monero * DISCOUNT_FACTOR
    resource_value_rakia = min(resource_value_rakia, potential_monero)
    return jsonify({
        "cpu": cpu,
        "ram": ram,
        "potential_monero": potential_monero,
        "resource_value_rakia": resource_value_rakia,
        "discount_factor": DISCOUNT_FACTOR
    }), 200


def distribute_mining_rewards():
    """Dodeljuje rudarske nagrade svake minute na osnovu CPU i RAM resursa rudara."""
    while True:
        wallets = load_wallets()
        total_rewards = {}

        for miner, resources in REGISTERED_MINERS.items():
            cpu = resources.get("cpu", 0)
            ram = resources.get("ram", 0)

            # 🛠 Izračunavanje nagrade na osnovu 24h rudarenja, podeljeno na minute
            reward_per_minute = ((cpu * MONERO_PER_CPU_PER_HOUR) + (ram * MONERO_PER_RAM_PER_HOUR)) / 60

            wallets[miner] = wallets.get(miner, 0) + reward_per_minute
            total_rewards[miner] = reward_per_minute

        save_wallets(wallets)
        logging.info(f"⛏️ Rudarske nagrade distribuirane: {total_rewards}")
        time.sleep(60)

# Pokreni nit za distribuciju rudarskih nagrada
reward_thread = threading.Thread(target=distribute_mining_rewards, daemon=True)
reward_thread.start()

if __name__ == "__main__":
    app.run(port=5000)
