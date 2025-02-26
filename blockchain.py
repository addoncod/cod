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
    REGISTERED_MINERS
)

# Konfiguracija logiranja
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Parametri blockchaina
DIFFICULTY = 4
RESOURCE_REWARD = 5

# Parametri za kupnju Rakia Coina s Monerom (fiksni peg: 1 XMR = 1 Rakia Coin)
# BASE_CONVERSION_RATE ovdje se ne koristi za dinamički model, već se direktno prenosi potrošeni XMR,
# uz naplatu fee-ja od 10%.
FEE_PERCENTAGE = 0.1

# Parametri za izračun vrijednosti CPU i RAM resursa u smislu izrudarenih Monera u 1 sat
# (primjerice: koliko se Monera izrudari po CPU jedinici i po MB RAM-a u 1 satu rudarenja)
MONERO_PER_CPU_PER_HOUR = 0.05    # primjer: 0.05 Monera po CPU jedinici (u satu)
MONERO_PER_RAM_PER_HOUR = 0.001    # primjer: 0.001 Monera po MB RAM-a (u satu)
# Rakia Coin vrijednost se računa kao 60% potencijalnog prinosa Monera (40% niža)
DISCOUNT_FACTOR = 0.6

# Globalne varijable vezane uz kupnju Rakia Coina
total_monero_purchased = 0.0    # Ako se želi pratiti statistika (ovdje se ne koristi u fiksnom modelu)

# Definiramo glavni wallet (gdje se skuplja fee) – stvarna adresa
MAIN_WALLET_ADDRESS = "2Ub5eqoKGRjmEGov9dzqNsX4LA7Erd3joSBB"
# Glavna Monero adresa – za informativne svrhe (transakcije kupnje/prodaje Rakia Coina)
MAIN_MONERO_ADDRESS = "4AF4YJufiiy2CAekHuunVmc12yR2wNQjHdKse7HwqSWGTdZsrDAwGvv55Fmht6VfsEXFw3RxR95yhXV9Rk5mR1JK67FkhVd"

app = Flask(__name__)
socketio = SocketIO(app)

def get_monero_price():
    """
    Dohvaća trenutnu cijenu Monera u USD s CoinGecko API-ja.
    """
    url = "https://api.coingecko.com/api/v3/simple/price?ids=monero&vs_currencies=usd"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            monero_price = data.get("monero", {}).get("usd")
            return monero_price
        else:
            logging.error("Neuspješno dohvaćanje monero cijene.")
            return None
    except Exception as e:
        logging.error(f"Greška prilikom dohvaćanja monero cijene: {e}")
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
        new_block = self.mine_block(self.chain[-1], transactions, resource_tasks, miner)
        if self.validate_block(new_block, self.chain[-1]):
            self.chain.append(new_block)
            save_blockchain([block.to_dict() for block in self.chain])
            logging.info(f"✅ Blok {new_block.index} uspješno dodan")
            return new_block
        else:
            logging.error("❌ Neuspješna validacija novog bloka")
            return None

    def mine_block(self, previous_block, transactions, resource_tasks, miner):
        index = previous_block.index + 1
        timestamp = int(time.time())
        previous_hash = previous_block.hash
        nonce = 0
        prefix = "0" * DIFFICULTY
        while True:
            new_block = Block(index, previous_hash, timestamp, transactions, resource_tasks, miner, RESOURCE_REWARD, nonce)
            if new_block.hash.startswith(prefix):
                logging.info(f"⛏️  Blok {index} iskopan | Rudar: {miner} | Nagrada: {RESOURCE_REWARD} coins | Hash: {new_block.hash}")
                return new_block
            nonce += 1

blockchain = Blockchain()

# API endpointi

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

TRANSACTIONS = []

@app.route('/transaction', methods=['POST'])
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

@app.route('/register_miner', methods=['POST'])
def api_register_miner():
    data = request.json
    return register_miner(data.get("miner_id"), data.get("cpu_available"), data.get("ram_available"))

@app.route('/user_resources/<user>', methods=['GET'])
def api_get_user_resources(user):
    return get_user_resources(user)

@app.route('/resource_request', methods=['POST'])
def api_send_resource_request():
    data = request.json
    buyer = data.get("buyer")
    cpu = data.get("cpu")
    ram = data.get("ram")
    if not buyer or cpu is None or ram is None:
        return jsonify({"error": "❌ Nedostaju parametri"}), 400
    return buy_resources(buyer, cpu, ram, "miner")

@app.route('/resource_request', methods=['GET'])
def api_get_resource_requests():
    return get_resource_requests()

@app.route('/miners', methods=['GET'])
def get_miners():
    return jsonify({"miners": REGISTERED_MINERS}), 200

@app.route('/assign_resources', methods=['POST'])
def api_assign_resources():
    data = request.json
    return assign_resources_to_user(data.get("buyer"), data.get("cpu"), data.get("ram"))

@app.route('/mine', methods=['POST'])
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
    if new_block.resource_tasks:
        task = new_block.resource_tasks[0]
        buyer = task.get("buyer")
        cpu_req = task.get("cpu")
        ram_req = task.get("ram")
        total_price = (cpu_req + ram_req) * 2
        fee = total_price * FEE_PERCENTAGE
        miner_reward = total_price - fee
        wallets = load_wallets()
        if wallets.get(buyer, 0) >= total_price:
            wallets[buyer] -= total_price
            wallets[new_block.miner] = wallets.get(new_block.miner, 0) + miner_reward
            wallets[MAIN_WALLET_ADDRESS] = wallets.get(MAIN_WALLET_ADDRESS, 0) + fee
            save_wallets(wallets)
            logging.info(f"💰 Transakcija: Od kupca {buyer} skinuto {total_price} coina, miner {new_block.miner} dobio {miner_reward} coina, glavni wallet ({MAIN_WALLET_ADDRESS}) dobio {fee} coina.")
        else:
            logging.error(f"❌ Kupac {buyer} nema dovoljno coina za plaćanje nagrade.")
    return jsonify({"message": "✅ Blok primljen", "block": new_block.to_dict()}), 200

@app.route('/buy_rakia', methods=['POST'])
def buy_rakia():
    """
    Endpoint za kupnju Rakia Coina s Monerom (fiksni peg: 1 XMR = 1 Rakia Coin).
    Ulazni parametri (JSON):
      - buyer: adresa kupca (wallet)
      - monero_amount: količina Monera koju kupac želi potrošiti
    Rezultat:
      - Rakia Coin primljen = potrošeni XMR umanjen za fee (10%)
      - Informativno: cijena Monera, glavna Monero adresa, i provjera izvršenja transakcije
    """
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

@app.route('/resource_value', methods=['POST'])
def resource_value():
    """
    Endpoint za izračun vrijednosti CPU i RAM resursa u Rakia Coin.
    Ulazni parametri (JSON):
      - cpu: broj CPU jedinica kupljenih od strane klijenta
      - ram: količina RAM-a (u MB) kupljena od strane klijenta
    Izračun:
      - Potencijalni prinos Monera u 1 satu rudarenja = (cpu * MONERO_PER_CPU_PER_HOUR) + (ram * MONERO_PER_RAM_PER_HOUR)
      - Vrijednost resursa u Rakia Coin = potencijalni prinos * DISCOUNT_FACTOR
        (odnosno, 40% manje od potencijalnog prinosa)
    """
    try:
        cpu = float(request.json.get("cpu", 0))
        ram = float(request.json.get("ram", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Neispravne vrijednosti za CPU ili RAM"}), 400
    potential_monero = cpu * MONERO_PER_CPU_PER_HOUR + ram * MONERO_PER_RAM_PER_HOUR
    resource_value_rakia = potential_monero * DISCOUNT_FACTOR
    # Osiguravamo da vrijednost Rakia Coina ne prelazi potencijalni prinos (mada DISCOUNT_FACTOR < 1)
    resource_value_rakia = min(resource_value_rakia, potential_monero)
    return jsonify({
        "cpu": cpu,
        "ram": ram,
        "potential_monero": potential_monero,
        "resource_value_rakia": resource_value_rakia,
        "discount_factor": DISCOUNT_FACTOR
    }), 200

@app.route('/chain', methods=['GET'])
def get_chain():
    return jsonify([block.to_dict() for block in blockchain.chain]), 200

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
