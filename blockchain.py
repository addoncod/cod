import time
import json
import hashlib
import threading
import logging
import requests
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from functions import (
    add_balance, 
    buy_resources, 
    get_balance, 
    get_user_resources, 
    get_resource_requests, 
    save_blockchain, 
    load_blockchain,
    load_wallets,
    save_wallets,
    assign_resources_to_user,
    register_miner,
    REGISTERED_MINERS,
    RESOURCE_REQUESTS
)
TRANSACTIONS = []

# Konfiguracija logiranja
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Parametri blockchaina
DIFFICULTY = 4
RESOURCE_REWARD = 5

# Parametri za kupnju Rakia Coina (fiksni peg: 1 XMR = 1 Rakia Coin)
FEE_PERCENTAGE = 0.1

# Parametri za izračun vrijednosti resursa u smislu izrudarenih Monera u 1 sat
# Cilj: 2 CPU i 2GB RAM (2048 MB) daje potencijalni prinos ≈ 0.00001 XMR u 24 sata,
# tj. oko 4.17e-7 XMR po satu, prije primjene diskonta.
MONERO_PER_CPU_PER_HOUR = 0.0000001       # XMR po CPU jedinici u satu
MONERO_PER_RAM_PER_HOUR = 0.0000000001058     # XMR po MB RAM-a u satu
DISCOUNT_FACTOR = 0.6  # Kupac dobiva 60% potencijalnog prinosa

# Globalna varijabla za praćenje shareova rudara – tj. rudari koji su isporučili resurse
MINER_SHARES = {}

# Definiramo glavni wallet (za fee) i glavnu Monero adresu (informativno)
MAIN_WALLET_ADDRESS = "2Ub5eqoKGRjmEGov9dzqNsX4LA7Erd3joSBB"
MAIN_MONERO_ADDRESS = "4AF4YJufiiy2CAekHuunVmc12yR2wNQjHdKse7HwqSWGTdZsrDAwGvv55Fmht6VfsEXFw3RxR95yhXV9Rk5mR1JK67FkhVd"

app = Flask(__name__)
socketio = SocketIO(app)

def get_monero_price():
    """Dohvaća trenutnu cijenu Monera u USD s CoinGecko API-ja."""
    url = "https://api.coingecko.com/api/v3/simple/price?ids=monero&vs_currencies=usd"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            return data.get("monero", {}).get("usd")
        else:
            logging.error("Neuspješno dohvaćanje monero cijene.")
            return None
    except Exception as e:
        logging.error(f"Greška pri dohvaćanju monero cijene: {e}")
        return None

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

    def to_dict(self):
        return self.__dict__

class Blockchain:
    def __init__(self):
        self.chain = []
        chain_data = load_blockchain()
        for block in chain_data:
            if isinstance(block, dict):
                new_block = Block(
                    index=block["index"],
                    previous_hash=block["previous_hash"],
                    timestamp=block["timestamp"],
                    transactions=block.get("transactions", []),
                    resource_tasks=block.get("resource_tasks", []),
                    miner=block["miner"],
                    reward=block["reward"],
                    nonce=block["nonce"]
                )
                if block.get("hash") and block.get("hash") != new_block.hash:
                    logging.warning(f"⚠️  Neusklađen hash za blok {new_block.index}")
                self.chain.append(new_block)
            else:
                self.chain.append(block)

    def validate_block(self, new_block, previous_block):
        if previous_block.index + 1 != new_block.index:
            return False
        if previous_block.hash != new_block.previous_hash:
            return False
        if new_block.calculate_hash() != new_block.hash:
            return False
        if not new_block.hash.startswith("0" * DIFFICULTY):
            return False
        return True

def add_block(self, transactions, resource_tasks, miner):
    wallets = load_wallets()
    valid_transactions = []
    total_mining_fee = 0  # Ukupni fee za rudara

    for tx in transactions:
        sender, recipient, amount = tx["from"], tx["to"], tx["amount"]
        fee = tx.get("fee", amount * 0.03)  # Ako nema fee-a, dodaj 3%

        if wallets.get(sender, 0) >= amount + fee:
            wallets[sender] -= (amount + fee)
            wallets[recipient] = wallets.get(recipient, 0) + amount
            wallets[miner] = wallets.get(miner, 0) + fee  # Rudari dobijaju fee
            valid_transactions.append(tx)
            total_mining_fee += fee
        else:
            logging.error(f"🚨 Nedovoljno balansa za transakciju {sender} -> {recipient}")

    save_wallets(wallets)

    new_block = self.mine_block(self.chain[-1], valid_transactions, resource_tasks, miner)

    if self.validate_block(new_block, self.chain[-1]):
        self.chain.append(new_block)
        save_blockchain([block.to_dict() for block in self.chain])
        logging.info(f"✅ Blok {new_block.index} dodan | Transakcije: {len(new_block.transactions)} | Rudarski fee: {total_mining_fee}")

        return new_block
    else:
        logging.error("❌ Neuspješna validacija bloka")
        return None




    def mine_block(self, previous_block, resource_tasks, miner):
        """Proces rudarenja bloka koji uključuje transakcije."""
        index = previous_block.index + 1
        timestamp = int(time.time())
        previous_hash = previous_block.hash
        nonce = 0
        prefix = "0" * DIFFICULTY
    
        global TRANSACTIONS  # Koristimo globalnu listu transakcija
        transactions = TRANSACTIONS.copy()  # Kopiramo transakcije pre rudarenja
    
        if not transactions:  
            logging.warning("⛔ Nema transakcija za dodavanje u blok.")
        
        TRANSACTIONS.clear()  # Brišemo transakcije nakon rudarenja
    
        while True:
            new_block = Block(index, previous_hash, timestamp, transactions, resource_tasks, miner, RESOURCE_REWARD, nonce)
            if new_block.hash.startswith(prefix):
                logging.info(f"⛏️  Blok {index} iskopan | Rudar: {miner} | Transakcije: {len(transactions)} | Hash: {new_block.hash}")
                return new_block
            nonce += 1




blockchain = Blockchain()

# NOVO: Funkcija koja provjerava status rudara (simulirano)
def get_active_miners():
    """
    Pokušava dohvatiti status svakog rudara putem simuliranog endpointa /miner_status.
    Rudari koji odgovore (status 200) smatraju se aktivnima.
    """
    active_miners = {}
    for miner_id in REGISTERED_MINERS.keys():
        try:
            # Simulacija: pretpostavljamo da rudari odgovaraju. U stvarnosti, implementirajte stvarnu provjeru.
            response = requests.get(f"{NODE_URL}/miner_status?miner_id={miner_id}", timeout=2)
            if response.status_code == 200:
                active_miners[miner_id] = REGISTERED_MINERS[miner_id]
            else:
                logging.error(f"Miner {miner_id} nije aktivan (status {response.status_code}).")
        except Exception as e:
            logging.error(f"Miner {miner_id} offline ili nije dostupan: {e}")
    return active_miners

# NOVO: Gradualna 24-satna sesija naplate resursa (1440 minuta)
def resource_usage_session_thread(buyer, cpu, ram, total_minutes=1440):
    total_cost = 0.00009 * (cpu / 2) * (ram / 2048.0)
    minute_cost = total_cost / total_minutes
    fee_rate = 0.1
    fee_per_minute = minute_cost * fee_rate
    miner_reward_per_minute = minute_cost - fee_per_minute

    logging.info(f"Resource usage session pokrenut za {buyer}: minute_cost = {minute_cost:.2e} XMR")
    
    for i in range(total_minutes):
        wallets = load_wallets()
        buyer_balance = wallets.get(buyer, 0)

        if buyer_balance >= minute_cost:
            wallets[buyer] -= minute_cost  # Oduzimamo cijenu iz korisnikovog walleta
            wallets[MAIN_WALLET_ADDRESS] = wallets.get(MAIN_WALLET_ADDRESS, 0) + fee_per_minute

            active_miners = get_active_miners()
            delivering_miners = {m_id: active_miners[m_id] for m_id in MINER_SHARES if m_id in active_miners}
            num_delivering = len(delivering_miners)

            if num_delivering > 0:
                reward_each = miner_reward_per_minute / num_delivering
                for miner_id in delivering_miners:
                    wallets[miner_id] = wallets.get(miner_id, 0) + reward_each
            else:
                logging.error("Nema rudara koji su aktivni i isporučili resurse.")

            save_wallets(wallets)
            logging.info(f"Minute {i+1}/{total_minutes}: {buyer} - oduzeto {minute_cost:.2e} XMR")
        else:
            logging.error(f"Minute {i+1}/{total_minutes}: Nedovoljno sredstava za {buyer} (balans: {buyer_balance:.2e} XMR)")
        time.sleep(60)

    logging.info(f"Resource usage session za {buyer} završena.")


@app.route("/resource_usage_session", methods=["POST"])
def resource_usage_session():
    """
    Endpoint za pokretanje 24-satne sesije naplate korištenja resursa.
    Trošak se raspoređuje jednoliko po minutama (1440 minuta):
      - Svake minute se s kupčevog walleta oduzima minute_cost.
      - 10% ide u MAIN_WALLET.
      - Preostalih 90% se raspodjeljuje samo među aktivnim rudarima koji su isporučili resurse (prema MINER_SHARES).
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

    # Dodajemo "dummy" zahtjev u RESOURCE_REQUESTS kako bi miner mogao dohvatiti zahtjev (ako je potrebno)
    RESOURCE_REQUESTS.append({
        "buyer": buyer,
        "cpu": cpu,
        "ram": ram,
        "timestamp": int(time.time())
    })
    thread = threading.Thread(target=resource_usage_session_thread, args=(buyer, cpu, ram))
    thread.start()
    return jsonify({"message": "Resource usage session za 24 sata je pokrenuta."}), 200

# Ostali API endpointi

@app.route('/add_balance', methods=['POST'])
def api_add_balance():
    data = request.json
    return add_balance(data.get("user"), data.get("amount"))

@app.route('/buy_resources', methods=['POST'])
def api_buy_resources():
    data = request.json
    return buy_resources(data.get("buyer"), data.get("cpu"), data.get("ram"), data.get("seller"))

@app.route('/balance/<address>', methods=['GET'])
def api_get_balance(address):
    return jsonify({"balance": get_balance(address)})

@app.route('/transactions', methods=['GET'])
def get_pending_transactions():
    """Vraća samo transakcije koje nisu dodate u blokchain."""
    chain_transaction_hashes = {
        hashlib.sha256(json.dumps(tx, sort_keys=True).encode()).hexdigest()
        for block in blockchain.chain for tx in block.transactions
    }

    pending_transactions = [
        tx for tx in TRANSACTIONS if hashlib.sha256(json.dumps(tx, sort_keys=True).encode()).hexdigest() not in chain_transaction_hashes
    ]

    logging.info(f"📜 Vraćam {len(pending_transactions)} transakcija za rudarenje.")
    return jsonify({"transactions": pending_transactions}), 200

@app.route('/register_miner', methods=["POST"])
def api_register_miner():
    data = request.json
    return register_miner(data.get("miner_id"), data.get("cpu_available"), data.get("ram_available"))

@app.route('/user_resources/<user>', methods=["GET"])
def api_get_user_resources(user):
    return get_user_resources(user)

@app.route('/resource_request', methods=["POST"])
def api_send_resource_request():
    data = request.json
    buyer = data.get("buyer")
    cpu = data.get("cpu")
    ram = data.get("ram")
    if not buyer or cpu is None or ram is None:
        return jsonify({"error": "❌ Nedostaju parametri"}), 400
    return buy_resources(buyer, cpu, ram, "miner")

@app.route('/resource_request', methods=["GET"])
def api_get_resource_requests():
    return get_resource_requests()

@app.route('/miners', methods=["GET"])
def get_miners():
    return jsonify({"miners": REGISTERED_MINERS}), 200

@app.route('/assign_resources', methods=["POST"])
def api_assign_resources():
    data = request.json
    return assign_resources_to_user(data.get("buyer"), data.get("cpu"), data.get("ram"))

@app.route('/mine', methods=["POST"])
def api_submit_block():
    block_data = request.json
    required_fields = ["index", "previous_hash", "timestamp", "transactions", "resource_tasks", "nonce", "hash", "miner"]

    # Proveri da li nedostaju neka polja
    missing_fields = [field for field in required_fields if field not in block_data]
    if missing_fields:
        logging.error(f"❌ Nedostaju polja u bloku: {missing_fields}")
        return jsonify({"error": "Neispravni podaci bloka", "missing_fields": missing_fields}), 400

    try:
        # ✅ Koristi transakcije koje je miner poslao, umesto TRANSACTIONS
        transactions = block_data.get("transactions", [])

        # ✅ Kreiranje novog bloka sa tačnim podacima
        new_block = Block(
            index=block_data["index"],
            previous_hash=block_data["previous_hash"],
            timestamp=block_data["timestamp"],
            transactions=transactions,  # 📌 Koristi transakcije iz bloka
            resource_tasks=block_data.get("resource_tasks", []),
            miner=block_data["miner"],
            reward=RESOURCE_REWARD,
            nonce=block_data["nonce"]
        )

        # ✅ Proveri hash koristeći istu metodu kao miner
        calculated_hash = new_block.calculate_hash()
        if calculated_hash != block_data["hash"]:
            logging.error(f"❌ Neispravan hash: Očekivan {calculated_hash}, primljen {block_data['hash']}")
            return jsonify({"error": "Neispravan hash", "expected": calculated_hash, "received": block_data["hash"]}), 400

    except Exception as e:
        logging.error(f"❌ Greška pri kreiranju bloka: {e}")
        return jsonify({"error": f"Greška pri kreiranju bloka: {e}"}), 400

    # ✅ Validacija bloka
    last_block = blockchain.chain[-1]
    if not blockchain.validate_block(new_block, last_block):
        logging.error("❌ Validacija novog bloka nije uspjela.")
        return jsonify({"error": "Validacija bloka nije uspjela"}), 400

    # ✅ Dodavanje bloka u lanac i čuvanje
    blockchain.chain.append(new_block)
    save_blockchain([block.to_dict() for block in blockchain.chain])

    logging.info(f"✅ Blok {new_block.index} primljen i dodan u lanac.")

    # ✅ Beleženje rudarskih shareova
    if new_block.resource_tasks:
        miner_id = new_block.miner
        MINER_SHARES[miner_id] = MINER_SHARES.get(miner_id, 0) + 1
        logging.info(f"🔢 Share zabilježen za rudara {miner_id}. Ukupno shareova: {MINER_SHARES[miner_id]}")

    # ✅ Ažuriranje balansa korisnika iz transakcija
    wallets = load_wallets()
    for tx in transactions:
        sender, recipient, amount = tx["from"], tx["to"], tx["amount"]

        if wallets.get(sender, 0) >= amount:  # ✅ Proveri da li pošiljalac ima dovoljno balansa
            wallets[sender] -= amount  # ✅ Skidamo sredstva sa računa
            wallets[recipient] = wallets.get(recipient, 0) + amount  # ✅ Dodajemo primatelju
            logging.info(f"💰 Transakcija obrađena: {sender} -> {recipient} ({amount} coins)")
        else:
            logging.error(f"🚨 Nedovoljno balansa za transakciju {sender} -> {recipient}")

    save_wallets(wallets)  # ✅ Snimamo novi balans

    return jsonify({"message": "✅ Blok primljen", "block": new_block.to_dict()}), 200



@app.route('/buy_rakia', methods=["POST"])
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

@app.route('/resource_value', methods=["POST"])
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

@app.route('/resource_usage', methods=["POST"])
def resource_usage():
    """
    Endpoint za naplatu korištenja resursa tijekom 1 sata.
    Klijent plaća ukupni trošak, od čega:
      - 10% ide u glavni wallet (fee)
      - Preostalih 90% se dijeli među rudarima proporcionalno broju shareova (koji su isporučili resurse)
    Nakon raspodjele, shareovi se resetiraju.
    """
    data = request.json
    buyer = data.get("buyer")
    try:
        cpu = float(data.get("cpu", 0))
        ram = float(data.get("ram", 0))
        duration = 60  # Fiksirano na 60 minuta
    except (TypeError, ValueError):
        return jsonify({"error": "Neispravne vrijednosti za CPU, RAM ili trajanje"}), 400
    if not buyer or cpu <= 0 or ram <= 0:
        return jsonify({"error": "Kupac, CPU i RAM moraju biti zadani i veći od 0"}), 400
    total_cost = (cpu + ram) * 2
    wallets = load_wallets()
    buyer_balance = wallets.get(buyer, 0)
    if buyer_balance < total_cost:
        return jsonify({"error": "Nedovoljno sredstava u kupčevom walletu"}), 400
    wallets[buyer] = buyer_balance - total_cost
    fee = total_cost * 0.1
    miner_pool = total_cost - fee
    wallets[MAIN_WALLET_ADDRESS] = wallets.get(MAIN_WALLET_ADDRESS, 0) + fee
    total_shares = sum(MINER_SHARES.values())
    if total_shares == 0:
        return jsonify({"error": "Nema shareova za raspodjelu"}), 400
    miner_rewards = {}
    for miner_id, shares in MINER_SHARES.items():
        reward = miner_pool * (shares / total_shares)
        wallets[miner_id] = wallets.get(miner_id, 0) + reward
        miner_rewards[miner_id] = reward
    save_wallets(wallets)
    logging.info(f"💰 Resource usage: Kupac {buyer} plati {total_cost} coina, fee {fee} coina, raspodijeljeno po shareovima: {miner_rewards}")
    MINER_SHARES.clear()
    return jsonify({
        "message": "Resource usage obračunat",
        "buyer": buyer,
        "total_cost": total_cost,
        "fee": fee,
        "miner_rewards": miner_rewards,
        "total_shares": total_shares
    }), 200

@app.route('/chain', methods=["GET"])
def get_chain():
    return jsonify([block.to_dict() for block in blockchain.chain]), 200

@app.route("/transaction", methods=['POST'])
def new_transaction():
    data = request.json
    sender = data.get("from")
    recipient = data.get("to")
    amount = data.get("amount")

    if not sender or not recipient or amount is None:
        return jsonify({"error": "Neispravni podaci za transakciju"}), 400

    fee = amount * 0.03  # 3% naknade za rudarenje

    wallets = load_wallets()
    sender_balance = wallets.get(sender, 0)

    if sender_balance < (amount + fee):
        return jsonify({"error": "Nedovoljno sredstava"}), 400

    wallets[sender] -= (amount + fee)  # Oduzimamo ukupan iznos (iznos + fee)
    wallets[recipient] = wallets.get(recipient, 0) + amount

    TRANSACTIONS.append({"from": sender, "to": recipient, "amount": amount, "fee": fee})

    save_wallets(wallets)
    logging.info(f"✅ Transakcija dodata: {sender} -> {recipient} ({amount} coins) | Fee: {fee}")

    return jsonify({"message": "Transakcija zabilježena"}), 200




if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
