import time
import json
import logging
from flask import Flask, request, jsonify

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

    REGISTERED_MINERS[miner_id] = {"cpu": cpu_available, "ram": ram_available}
    wallets = load_wallets()
    wallets.setdefault(miner_id, 0)
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

# --- Novi dio: Endpoint za resource_usage ---

MAIN_WALLET = "MAIN_WALLET"  # Adresa glavnog walleta za fee

app = Flask(__name__)

@app.route("/resource_usage", methods=["POST"])
def resource_usage():
    data = request.get_json()
    buyer = data.get("buyer")
    cpu = data.get("cpu")
    ram = data.get("ram")
    duration = data.get("duration")

    if not buyer or cpu is None or ram is None or duration is None:
        return jsonify({"error": "❌ Nedostaju parametri"}), 400

    # Osiguraj minimalno trajanje od 60 minuta
    if duration < 60:
        duration = 60

    # Izračun teoretskog dobitka rudarenja:
    # Pretpostavimo: teoretski_dobitak = cpu + (ram / 1024)
    theoretical_yield = cpu + (ram / 1024.0)
    effective_yield = theoretical_yield * 0.6  # 40% se oduzima

    # Rate rudarenja po minuti:
    per_minute_rate = effective_yield / 60.0

    # Ukupni trošak za trajanje korištenja:
    total_cost = per_minute_rate * duration

    wallets = load_wallets()
    buyer_balance = wallets.get(buyer, 0)
    if buyer_balance < total_cost:
        return jsonify({"error": "❌ Nedovoljno coina na walletu"}), 400

    # Skinemo ukupni trošak s buyerovog walleta
    wallets[buyer] -= total_cost

    # 10% fee ide u glavni wallet, ostatak (90%) ide rudarskoj nagradnoj kasi
    fee = total_cost * 0.1
    miner_pool = total_cost * 0.9

    wallets[MAIN_WALLET] = wallets.get(MAIN_WALLET, 0) + fee

    # Distribucija nagrada rudara svakih 30 minuta
    intervals = int(duration / 30)  # npr. za 60 minuta ima 2 intervala
    reward_per_interval = miner_pool / intervals if intervals > 0 else miner_pool

    # Izračunamo ukupnu težinu rudara (na temelju CPU i RAM, pretvarajući RAM u jedinice)
    total_weight = 0
    for miner_id, resources in REGISTERED_MINERS.items():
        total_weight += resources["cpu"] + (resources["ram"] / 1024.0)

    miner_rewards = {}
    if total_weight > 0:
        for miner_id, resources in REGISTERED_MINERS.items():
            weight = resources["cpu"] + (resources["ram"] / 1024.0)
            # Ukupna nagrada za ovog minera preko svih intervala:
            reward = reward_per_interval * intervals * (weight / total_weight)
            wallets[miner_id] = wallets.get(miner_id, 0) + reward
            miner_rewards[miner_id] = reward

    save_wallets(wallets)

    result = {
        "message": "✅ Resource usage processed successfully",
        "total_cost": total_cost,
        "fee": fee,
        "miner_pool": miner_pool,
        "miner_rewards": miner_rewards,
        "duration": duration,
        "per_minute_rate": per_minute_rate
    }
    return jsonify(result), 200

if __name__ == "__main__":
    app.run(port=5000)
