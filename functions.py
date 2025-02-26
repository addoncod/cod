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

# --- Osnovne funkcije za rad s blockchainom i walletovima (ne mijenjati) ---
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

def resource_value():
    """
    Izračun vrijednosti resursa u Rakia Coin.
    Potencijalni prinos u 1 satu rudarenja:
      = (cpu * MONERO_PER_CPU_PER_HOUR) + (ram * MONERO_PER_RAM_PER_HOUR)
    Vrijednost koja kupcu "ostaje" primjenom DISCOUNT_FACTOR:
      = potencijalni_prinos * DISCOUNT_FACTOR
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

# --- NOVO: Gradualno naplaćivanje resursa tijekom 24 sata (po minuti) ---

def resource_usage_session_thread(buyer, cpu, ram, total_minutes=1440):
    """
    Izračunava ukupni trošak za 24 sata prema fiksnoj vrijednosti:
      Za 2 CPU i 2GB RAM: 0.00009 XMR u 24 sata.
    Trošak se skalira proporcionalno unesenim vrijednostima.
    Svake minute se oduzima minute_cost s kupčevog walleta, a od toga se 10% ide kao fee,
    a 90% se raspoređuje među rudarima (jednako).
    """
    # Izračun ukupnog troška za 24 sata:
    # Skalujemo: za 2 CPU i 2048 MB RAM: 0.00009 XMR, pa za ostale vrijednosti:
    total_cost = 0.00009 * (cpu / 2) * (ram / 2048.0)
    minute_cost = total_cost / total_minutes
    fee_rate = 0.1
    fee_per_minute = minute_cost * fee_rate
    miner_reward_per_minute = minute_cost - fee_per_minute

    logging.info(f"Resource usage session pokrenut za {buyer}: minute_cost={minute_cost:.2e} XMR")
    for i in range(total_minutes):
        wallets = load_wallets()
        buyer_balance = wallets.get(buyer, 0)
        if buyer_balance >= minute_cost:
            wallets[buyer] = buyer_balance - minute_cost
            # Dodaj fee u glavni wallet
            wallets[MAIN_WALLET] = wallets.get(MAIN_WALLET, 0) + fee_per_minute
            # Distribuiraj miner nagradu jednako među svim aktivnim rudarima
            num_miners = len(REGISTERED_MINERS)
            if num_miners > 0:
                reward_each = miner_reward_per_minute / num_miners
                for miner_id in REGISTERED_MINERS.keys():
                    wallets[miner_id] = wallets.get(miner_id, 0) + reward_each
            save_wallets(wallets)
            logging.info(f"Minute {i+1}/{total_minutes}: {buyer} - oduzeto {minute_cost:.2e} XMR")
        else:
            logging.error(f"Minute {i+1}/{total_minutes}: Nedovoljno sredstava za {buyer} (trenutni balans: {buyer_balance:.2e} XMR)")
        # Za produkciju: sleep 60 sekundi; za testiranje možete smanjiti vrijeme
        time.sleep(60)
    logging.info(f"Resource usage session za {buyer} završena.")

@app.route("/resource_usage_session", methods=["POST"])
def resource_usage_session():
    """
    Endpoint koji pokreće 24-satnu sesiju naplate korištenja resursa.
    Trošak se raspoređuje jednoliko po minutama (1440 minuta).
    Svake minute se oduzima minute_cost s kupčevog walleta, a rudari dobivaju nagradu prema modelu:
      - 10% fee ide u MAIN_WALLET
      - 90% se raspodjeljuje među aktivnim rudarima jednako.
    """
    data = request.get_json()
    buyer = data.get("buyer")
    try:
        cpu = float(data.get("cpu", 0))
        ram = float(data.get("ram", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Neispravne vrijednosti za CPU ili RAM"}), 400
    if not buyer or cpu <= 0 or ram <= 0:
        return jsonify({"error": "Buyer, CPU i RAM moraju biti zadani i veći od 0"}), 400

    # Pokrećemo sesiju u zasebnoj niti
    thread = threading.Thread(target=resource_usage_session_thread, args=(buyer, cpu, ram))
    thread.start()
    return jsonify({"message": "Resource usage session za 24 sata je pokrenuta."}), 200

# --- Ostali endpointi (transakcije, rudarenje, kupnja itd.) ---

@app.route("/transaction", methods=["POST"])
def new_transaction():
    data = request.json
    sender = data.get("from")
    recipient = data.get("to")
    amount = data.get("amount")
    if not sender or not recipient or amount is None:
        return jsonify({"error": "Neispravni podaci za transakciju"}), 400
    TRANSACTIONS.append({"from": sender, "to": recipient, "amount": amount})
    logging.info(f"✅ Nova transakcija: {sender} -> {recipient} ({amount} coins)")
    return jsonify({"message": "Transakcija zabilježena"}), 200

@app.route("/register_miner", methods=["POST"])
def api_register_miner():
    data = request.json
    return register_miner(data.get("miner_id"), data.get("cpu_available"), data.get("ram_available"))

@app.route("/balance/<address>", methods=["GET"])
def api_get_balance(address):
    return jsonify({"balance": get_balance(address)})

@app.route("/buy_resources", methods=["POST"])
def api_buy_resources():
    data = request.json
    return buy_resources(data.get("buyer"), data.get("cpu"), data.get("ram"), data.get("seller"))

@app.route("/user_resources/<user>", methods=["GET"])
def api_get_user_resources(user):
    return get_user_resources(user)

@app.route("/resource_request", methods=["POST"])
def api_send_resource_request():
    data = request.json
    buyer = data.get("buyer")
    cpu = data.get("cpu")
    ram = data.get("ram")
    if not buyer or cpu is None or ram is None:
        return jsonify({"error": "❌ Nedostaju parametri"}), 400
    return buy_resources(buyer, cpu, ram, "miner")

@app.route("/resource_request", methods=["GET"])
def api_get_resource_requests():
    return get_resource_requests()

@app.route("/miners", methods=["GET"])
def get_miners():
    return jsonify({"miners": REGISTERED_MINERS}), 200

@app.route("/assign_resources", methods=["POST"])
def api_assign_resources():
    data = request.json
    return assign_resources_to_user(data.get("buyer"), data.get("cpu"), data.get("ram"))

@app.route("/mine", methods=["POST"])
def api_submit_block():
    block_data = request.json
    required_fields = ["index", "previous_hash", "timestamp", "resource_tasks", "nonce", "hash", "miner"]
    missing_fields = [field for field in required_fields if field not in block_data]
    if missing_fields:
        logging.error(f"❌ Nedostaju polja u bloku: {missing_fields}")
        return jsonify({"error": "Neispravni podaci bloka", "missing_fields": missing_fields}), 400
    try:
        new_block = Block(
            index=block_data["index"],
            previous_hash=block_data["previous_hash"],
            timestamp=block_data["timestamp"],
            transactions=block_data.get("transactions", []),
            resource_tasks=block_data.get("resource_tasks", []),
            miner=block_data["miner"],
            reward=RESOURCE_REWARD,
            nonce=block_data["nonce"]
        )
        calculated_hash = new_block.calculate_hash()
        if calculated_hash != block_data["hash"]:
            logging.error(f"❌ Neispravan hash: Očekivan {calculated_hash}, primljen {block_data['hash']}")
            return jsonify({"error": "Neispravan hash", "expected": calculated_hash, "received": block_data["hash"]}), 400
    except Exception as e:
        logging.error(f"❌ Greška pri kreiranju bloka: {e}")
        return jsonify({"error": f"Greška pri kreiranju bloka: {e}"}), 400
    last_block = blockchain.chain[-1]
    if not blockchain.validate_block(new_block, last_block):
        logging.error("❌ Validacija novog bloka nije uspjela.")
        return jsonify({"error": "Validacija bloka nije uspjela"}), 400
    blockchain.chain.append(new_block)
    save_blockchain([block.to_dict() for block in blockchain.chain])
    logging.info(f"✅ Blok {new_block.index} primljen i dodan u lanac.")
    # Ako blok sadrži resource_tasks, bilježimo share rudara
    if new_block.resource_tasks:
        miner_id = new_block.miner
        # Evidentiramo jedan share za rudara
        try:
            MINER_SHARES[miner_id] = MINER_SHARES.get(miner_id, 0) + 1
            logging.info(f"🔢 Share zabilježen za rudara {miner_id}. Ukupno shareova: {MINER_SHARES[miner_id]}")
        except Exception as e:
            logging.error(f"Greška pri evidentiranju shareova: {e}")
    return jsonify({"message": "✅ Blok primljen", "block": new_block.to_dict()}), 200

@app.route("/buy_rakia", methods=["POST"])
def buy_rakia():
    data = request.json
    buyer = data.get("buyer")
    try:
        monero_amount = float(data.get("monero_amount", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Neispravna količina Monera"}), 400
    if not buyer or monero_amount <= 0:
        return jsonify({"error": "Kupac i količina Monera moraju biti zadani"}), 400
    monero_price = get_monero_price()
    if monero_price is None:
        return jsonify({"error": "Nije moguće dohvatiti cijenu Monera"}), 500
    fee = monero_amount * FEE_PERCENTAGE
    rakia_received = monero_amount - fee
    wallets = load_wallets()
    previous_balance = wallets.get(buyer, 0)
    wallets[buyer] = previous_balance + rakia_received
    wallets[MAIN_MONERO_ADDRESS] = wallets.get(MAIN_MONERO_ADDRESS, 0) + fee
    save_wallets(wallets)
    wallets_after = load_wallets()
    new_balance = wallets_after.get(buyer, 0)
    transaction_executed = (new_balance >= previous_balance + rakia_received)
    logging.info(f"💰 Kupnja Rakia Coina: Kupac {buyer} potrošio je {monero_amount} Monera, primio {rakia_received} Rakia Coina.")
    logging.info(f"Glavna Monero adresa za transakcije: {MAIN_MONERO_ADDRESS}")
    logging.info(f"Trenutna cijena Monera: {monero_price} USD (informativno)")
    return jsonify({
        "message": "Kupnja uspješna",
        "buyer": buyer,
        "monero_spent": monero_amount,
        "rakia_received": rakia_received,
        "fee": fee,
        "main_monero_address": MAIN_MONERO_ADDRESS,
        "transaction_executed": transaction_executed
    }), 200

@app.route("/chain", methods=["GET"])
def get_chain():
    return jsonify([block.to_dict() for block in blockchain.chain]), 200

if __name__ == "__main__":
    app.run(port=5000)
