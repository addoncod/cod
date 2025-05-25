import json 
import logging
import hashlib
from datetime import datetime
from flask import Flask, request, jsonify
import threading
import os
import sys

from flask_socketio import SocketIO, emit, join_room

# ---------- Forsirani logging na stdout -----------
logging.getLogger().handlers.clear()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logging.info("=== Blockchain LOG TEST: start ===")

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")
state_lock = threading.Lock()

SYSTEM_WALLET = "HJckCeSKpYsMA9CDZ7SxkKEKygdD6pAWxZZ58wA1gBKz"
WALLETS_FILE = "wallets.json"
REQUESTS_FILE = "bandwidth_requests.json"
CHAIN_FILE = "chain.json"

# ----------------- CHAIN (blockchain knjiga) ----------------------

def load_chain():
    if not os.path.exists(CHAIN_FILE):
        with open(CHAIN_FILE, "w") as f:
            json.dump([], f)
    with open(CHAIN_FILE) as f:
        return json.load(f)

def save_chain(chain):
    with open(CHAIN_FILE, "w") as f:
        json.dump(chain, f, indent=2)

def add_block(data):
    chain = load_chain()
    last_hash = chain[-1]["hash"] if chain else "0"*64
    block = {
        "index": len(chain)+1,
        "timestamp": int(datetime.now().timestamp()),
        "data": data,
        "prev_hash": last_hash,
    }
    block_raw = f"{block['index']}{block['timestamp']}{json.dumps(data)}{last_hash}"
    block["hash"] = hashlib.sha256(block_raw.encode()).hexdigest()
    chain.append(block)
    save_chain(chain)

# ------------------ NOTIFIKACIJE -------------------------

def notify_user(address, message):
    socketio.emit('notification', {"address": address, "message": message}, room=address)
    logging.info(f"Notification sent to {address}: {message}")

@socketio.on('join')
def on_join(data):
    address = data.get("address")
    if address:
        join_room(address)
        emit("notification", {"address": address, "message": "Joined room for notifications."})

# ------------------ BANDWIDTH CIJENA ---------------------

def calculate_price(mbps, minutes):
    price_per_minute = int(mbps // 5)
    if price_per_minute < 1:
        price_per_minute = 1
    return price_per_minute * int(minutes)

# ------------------ LOAD / SAVE STATE ----------------------

# --- Automatsko kreiranje fileova ako ne postoje ---
if not os.path.exists(WALLETS_FILE):
    with open(WALLETS_FILE, "w") as f:
        json.dump({}, f)
try:
    with open(WALLETS_FILE) as f:
        wallets = json.load(f)
except Exception as e:
    logging.warning(f"Failed to load wallets: {e}")
    wallets = {}
    with open(WALLETS_FILE, "w") as f:
        json.dump(wallets, f, indent=4)

if not os.path.exists(REQUESTS_FILE):
    with open(REQUESTS_FILE, "w") as f:
        json.dump([], f)
try:
    with open(REQUESTS_FILE) as f:
        req_queue = json.load(f)
except Exception as e:
    logging.warning(f"Failed to load requests: {e}")
    req_queue = []
    with open(REQUESTS_FILE, "w") as f:
        json.dump(req_queue, f, indent=4)

assignments = []

def save_wallets():
    with open(WALLETS_FILE, "w") as f:
        json.dump(wallets, f, indent=4)

def save_requests():
    with open(REQUESTS_FILE, "w") as f:
        json.dump(req_queue, f, indent=4)

# ----------------- API UNIVERSAL LOGGING -----------------------

@app.before_request
def log_request_info():
    try:
        data = request.get_json(silent=True)
    except Exception:
        data = None
    logging.info(
        f"API call: {request.method} {request.path} | "
        f"Data: {data if data else dict(request.args)}"
    )

# ----------------- API ENDPOINTS -------------------------------

@app.route("/balance/<user>", methods=["GET"])
def get_balance(user):
    with state_lock:
        result = wallets.get(user, 0)
    return jsonify({"balance": result}), 200

@app.route("/add_balance", methods=["POST"])
def add_balance():
    data = request.json or {}
    u = data.get("user"); amt = data.get("amount", 0)
    if not u or amt <= 0:
        return jsonify({"error": "user + positive amount required"}), 400
    with state_lock:
        wallets[u] = wallets.get(u, 0) + amt
        save_wallets()
        result = wallets[u]
    add_block({"type": "add_balance", "user": u, "amount": amt})
    logging.info(f"Balance added: {amt} coins to {u} (new balance {result})")
    notify_user(u, f"Balance updated! New balance: {result}")
    return jsonify({"balance": result}), 200

@app.route("/buy_bandwidth", methods=["POST"])
def buy_bandwidth():
    data    = request.json or {}
    buyer   = data.get("buyer")
    mbps    = data.get("bandwidth", 0)
    minutes = data.get("minutes", 1)
    seller  = data.get("seller")
    cost    = calculate_price(mbps, minutes)

    if not buyer or not seller or mbps <= 0 or minutes <= 0:
        logging.warning(f"Invalid buy_bandwidth request: {data}")
        return jsonify({"error": "buyer, seller, positive bandwidth and minutes required"}), 400

    with state_lock:
        if wallets.get(buyer, 0) < cost:
            logging.info(f"Insufficient funds for user {buyer}: has {wallets.get(buyer, 0)}, needs {cost}")
            return jsonify({"error": "insufficient funds"}), 400

        req_id = f"{buyer}_{int(datetime.now().timestamp())}"
        req = {
            "id": req_id,
            "buyer": buyer,
            "bandwidth": mbps,
            "minutes": minutes,
            "timestamp": int(datetime.now().timestamp()),
            "bids": []
        }
        req_queue.append(req)
        save_requests()
        logging.info(f"Bandwidth request: {buyer} requests {mbps} Mbps for {minutes} min = {cost} coins (pending)")
    notify_user(buyer, f"Bandwidth request {mbps} Mbps/{minutes}min created! Awaiting bids...")
    add_block({"type": "buy_bandwidth", "buyer": buyer, "mbps": mbps, "minutes": minutes, "cost": cost, "req_id": req_id})
    return jsonify({"pending_balance": wallets[buyer], "pending_price": cost, "task_id": req_id}), 200

@app.route("/resource_request", methods=["GET"])
def resource_request():
    with state_lock:
        if req_queue:
            return jsonify(req_queue[0]), 200
    return jsonify({}), 404

@app.route("/bids/<task_id>", methods=["GET"])
def get_bids(task_id):
    with state_lock:
        for req in req_queue:
            if req.get("id") == task_id:
                return jsonify(req.get("bids", [])), 200
    return jsonify([]), 200

@app.route("/bid", methods=["POST"])
def place_bid():
    data = request.json or {}
    task_id = data.get("task_id")
    miner = data.get("miner")
    price = float(data.get("price", 0))
    proxy_ip = data.get("proxy_ip")
    proxy_port = data.get("proxy_port")
    if not task_id or not miner or price <= 0 or not proxy_ip or not proxy_port:
        return jsonify({"error": "task_id, miner, price, proxy_ip, proxy_port required"}), 400

    with state_lock:
        for req in req_queue:
            if req.get("id") == task_id:
                if "bids" not in req:
                    req["bids"] = []
                req["bids"].append({
                    "miner": miner,
                    "price": price,
                    "timestamp": int(datetime.now().timestamp()),
                    "proxy_ip": proxy_ip,
                    "proxy_port": proxy_port
                })
                save_requests()
                notify_user(req["buyer"], f"New bid: {miner} offers for {price} coins (proxy: {proxy_ip}:{proxy_port})")
                add_block({"type": "bid", "task_id": task_id, "miner": miner, "price": price, "proxy_ip": proxy_ip, "proxy_port": proxy_port})
                return jsonify({"message": "Bid placed"}), 200
    return jsonify({"error": "task not found"}), 404

@app.route("/accept_bid", methods=["POST"])
def accept_bid():
    data = request.json or {}
    task_id = data.get("task_id")
    miner = data.get("miner")
    price = float(data.get("price", 0))

    if not task_id or not miner or price <= 0:
        return jsonify({"error": "task_id, miner, price required"}), 400

    with state_lock:
        for req in req_queue:
            if req.get("id") == task_id:
                buyer = req["buyer"]
                mbps = req["bandwidth"]
                minutes = req.get("minutes", 1)
                # Pronađi proxy podatke iz odabranog bida
                bid = next((b for b in req["bids"] if b["miner"] == miner and float(b["price"]) == price), None)
                if not bid:
                    return jsonify({"error": "bid not found"}), 404
                proxy_ip = bid.get("proxy_ip")
                proxy_port = bid.get("proxy_port")
                if not proxy_ip or not proxy_port:
                    return jsonify({"error": "miner nije poslao proxy info"}), 400

                # Provjeri balance
                if wallets.get(buyer, 0) < price:
                    return jsonify({"error": "user has insufficient funds"}), 400
                fee = round(price * 0.15, 2)
                reward = price - fee
                wallets[buyer] -= price
                wallets[SYSTEM_WALLET] = wallets.get(SYSTEM_WALLET, 0) + fee
                wallets[miner] = wallets.get(miner, 0) + reward
                save_wallets()

                req["miner"] = miner
                req["proxy_ip"] = proxy_ip
                req["proxy_port"] = proxy_port
                assignments.append(req)
                req_queue.remove(req)
                save_requests()
                add_block({
                    "type": "mining",
                    "miner": miner,
                    "buyer": buyer,
                    "mbps": mbps,
                    "minutes": minutes,
                    "reward": reward,
                    "fee": fee,
                    "price": price,
                    "proxy_ip": proxy_ip,
                    "proxy_port": proxy_port,
                    "task_id": task_id
                })
                notify_user(buyer, f"Accepted bid from {miner} for {price} coins! Bandwidth assigned. Proxy: {proxy_ip}:{proxy_port}")
                notify_user(miner, f"Your bid for {buyer} accepted! You earned {reward} coins.")
                return jsonify({
                    "message": "Bid accepted and bandwidth assigned",
                    "reward": reward,
                    "system_fee": fee,
                    "minutes": minutes,
                    "mbps": mbps,
                    "proxy_ip": proxy_ip,
                    "proxy_port": proxy_port
                }), 200
    return jsonify({"error": "task or bid not found"}), 404

@app.route("/task_assignment/<task_id>", methods=["GET"])
def task_assignment(task_id):
    with state_lock:
        for a in reversed(assignments):
            if a.get("id") == task_id:
                return jsonify({
                    "miner": a.get("miner"),
                    "buyer": a.get("buyer"),
                    "proxy_ip": a.get("proxy_ip"),
                    "proxy_port": a.get("proxy_port"),
                    "bandwidth": a.get("bandwidth"),
                    "minutes": a.get("minutes"),
                }), 200
    return jsonify({"error": "not found"}), 404

@app.route("/chain", methods=["GET"])
def get_chain():
    chain = load_chain()
    return jsonify(chain), 200

@app.route("/active_miner/<user>", methods=["GET"])
def active_miner(user):
    with state_lock:
        for a in reversed(assignments):
            if a["buyer"] == user:
                return jsonify({"active_miner": a["miner"]}), 200
    return jsonify({"active_miner": None}), 200

@app.route("/user_bandwidth/<user>", methods=["GET"])
def user_bandwidth(user):
    with state_lock:
        total = sum(a["bandwidth"] for a in assignments if a["buyer"] == user)
    return jsonify({"bandwidth": total}), 200

# ------------------ START --------------------------

if __name__ == "__main__":
    logging.info("Starting bandwidth blockchain node with HTTP proxy support, bidding, chain, p2p, notifications…")
    socketio.run(app, host="0.0.0.0", port=8080, allow_unsafe_werkzeug=True)
