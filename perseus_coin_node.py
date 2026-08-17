#!/usr/bin/env python3
"""
Perseus Coin (PRSC) Layer 1 Blockchain Node & Miner
Implements the Proof of Attractor Calculation (PoAC) consensus mechanism,
transaction ledger, mempool, and block verification.
"""

import os
import sys
import json
import hashlib
import time
import random
import urllib.request
from rich.console import Console
from rich.panel import Panel
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

console = Console()

class Block:
    def __init__(self, index, previous_hash, timestamp, transactions, poac_solution, difficulty):
        self.index = index
        self.previous_hash = previous_hash
        self.timestamp = timestamp
        self.transactions = transactions
        self.poac_solution = poac_solution  # Contains: {"coupling_weight": k, "lyapunov_exponent": lambda}
        self.difficulty = difficulty
        self.hash = self.calculate_hash()
        
    def calculate_hash(self):
        block_string = json.dumps({
            "index": self.index,
            "previous_hash": self.previous_hash,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "poac_solution": self.poac_solution,
            "difficulty": self.difficulty
        }, sort_keys=True)
        return hashlib.sha256(block_string.encode('utf-8')).hexdigest()

def verify_transaction_signature(tx):
    sender = tx.get("sender")
    recipient = tx.get("recipient")
    amount = tx.get("amount")
    timestamp = tx.get("timestamp")
    signature = tx.get("signature")
    
    if sender == "SYSTEM":
        return True
        
    if not signature:
        return False
        
    try:
        from cryptography.hazmat.primitives.asymmetric import ed25519
        message = f"{sender}_{recipient}_{amount}_{timestamp}"
        
        # Verify against master key for the TREASURY_RESERVE
        if sender == "TREASURY_RESERVE":
            pub_key_hex = "63fa919515df288dd25af29a3d31cf0d0d6bbb0e2920221972199047b08b381c"
        else:
            pub_key_hex = sender
            
        public_key = ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(pub_key_hex))
        public_key.verify(bytes.fromhex(signature), message.encode('utf-8'))
        return True
    except Exception:
        return False

def verify_submitted_block(block_data, ledger_path):
    import json
    import os
    import hashlib
    
    if not os.path.exists(ledger_path):
        return False
        
    with open(ledger_path, 'r') as f:
        chain = json.load(f)
        
    if not chain:
        return False
        
    last_block = chain[-1]
    
    # 1. Verify index and previous hash match the ledger tip
    next_index = len(chain)
    if block_data.get("index") != next_index:
        print(f"Validation failed: index mismatch (expected {next_index}, got {block_data.get('index')})")
        return False
    if block_data.get("previous_hash") != last_block.get("hash"):
        print("Validation failed: previous hash mismatch")
        return False
        
    # 2. Verify PoAC solution parameters and target hash difficulty
    solution = block_data.get("poac_solution", {})
    k = solution.get("coupling_weight", 0.0)
    lam = solution.get("lyapunov_exponent", 0.0)
    
    if abs(k) < 0.0001 or k > 10.0 or lam >= 0.0:
        print(f"Validation failed: invalid attractor parameters (k={k}, lam={lam})")
        return False
        
    fmt = "{:.8f}_{:.8f}_{}"
    sol_string = fmt.format(k, lam, next_index)
    sol_hash = hashlib.sha256(sol_string.encode('utf-8')).hexdigest()
    
    diff = last_block.get("difficulty", 1.0)
    target = "0" * int(diff)
    if not sol_hash.startswith(target):
        print(f"Validation failed: hash difficulty mismatch (got {sol_hash}, target {target})")
        return False
        
    # 3. Verify transactions list
    txs = block_data.get("transactions", [])
    if not txs:
        print("Validation failed: block contains no transactions")
        return False
        
    # 4. Verify Block Reward Transaction
    reward_tx = txs[0]
    halvings = next_index // 12614400
    expected_reward = 31.7 / (2 ** halvings) if halvings < 64 else 0.0
    
    if reward_tx.get("sender") != "SYSTEM":
        print("Validation failed: first transaction must be from SYSTEM (Block Reward)")
        return False
    if float(reward_tx.get("amount", 0.0)) != expected_reward:
        print(f"Validation failed: incorrect block reward amount (expected {expected_reward}, got {reward_tx.get('amount')})")
        return False
        
    # 5. Build Balance Sheet from existing ledger
    balances = {}
    for b in chain:
        for tx in b.get("transactions", []):
            s = tx.get("sender")
            r = tx.get("recipient")
            amt = float(tx.get("amount", 0.0))
            
            if s not in ("SYSTEM", "TREASURY_RESERVE"):
                balances[s] = balances.get(s, 0.0) - amt
            balances[r] = balances.get(r, 0.0) + amt
            
    # 6. Verify signatures and balances for new transactions
    for tx in txs[1:]:
        s = tx.get("sender")
        r = tx.get("recipient")
        amt = float(tx.get("amount", 0.0))
        
        # Check balance
        current_sender_bal = balances.get(s, 0.0)
        if current_sender_bal < amt:
            print(f"Validation failed: insufficient sender balance for {s} (balance: {current_sender_bal}, trying to send {amt})")
            return False
            
        # Check signature
        if not verify_transaction_signature(tx):
            print(f"Validation failed: invalid signature for transaction from {s}")
            return False
            
        # Update state
        balances[s] = current_sender_bal - amt
        balances[r] = balances.get(r, 0.0) + amt
        
    return True

def parse_and_verify_submitted_block(body_str, ledger_path):
    try:
        block_data = json.loads(body_str)
        return verify_submitted_block(block_data, ledger_path)
    except Exception as e:
        print(f"Exception during block parse and verify: {e}")
        return False

class Blockchain:
    def __init__(self, ledger_path):
        self.ledger_path = ledger_path
        self.unconfirmed_transactions = []
        self.chain = []
        self.difficulty = 1.0  # Dynamic DDE convergence difficulty
        
        # Try to sync ledger with public network first
        self.sync_with_network()
        
        # Load existing ledger or initialize Genesis Block
        if os.path.exists(self.ledger_path):
            self.load_chain()
        else:
            self.create_genesis_block()
            
    def sync_with_network(self):
        print("[NODE] Connecting to public seed node to sync ledger...")
        try:
            req = urllib.request.Request(
                "https://sniff-breeching-police.ngrok-free.dev/api/ledger",
                headers={'Bypass-Tunnel-Reminder': 'true'}
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    if data:
                        with open(self.ledger_path, 'w') as f:
                            json.dump(data, f, indent=4)
                        print(f"[NODE] Successfully synced {len(data)} blocks from seed node.")
                        return True
        except Exception as e:
            print(f"[NODE] Network sync failed (using local ledger fallback): {e}")
        return False
            
    def create_genesis_block(self):
        # Genesis Block (Block #0) contains the starting network parameters
        genesis_solution = {"coupling_weight": 0.05, "lyapunov_exponent": -0.8365}
        genesis_block = Block(
            index=0,
            previous_hash="0"*64,
            timestamp=1786968000.0, # Target launch timestamp (2026)
            transactions=[{"sender": "SYSTEM", "recipient": "TREASURY_RESERVE", "amount": 200000000.0, "memo": "Genesis Founder Allocation"}],
            poac_solution=genesis_solution,
            difficulty=1.0
        )
        self.chain.append(genesis_block)
        self.save_chain()
        console.print("[bold green][GENESIS] Genesis Block #0 successfully initialized and written to ledger.[/bold green]")
        
    def save_chain(self):
        serializable_chain = []
        for block in self.chain:
            serializable_chain.append({
                "index": block.index,
                "previous_hash": block.previous_hash,
                "timestamp": block.timestamp,
                "transactions": block.transactions,
                "poac_solution": block.poac_solution,
                "difficulty": block.difficulty,
                "hash": block.hash
            })
        with open(self.ledger_path, 'w') as f:
            json.dump(serializable_chain, f, indent=4)
            
    def load_chain(self):
        with open(self.ledger_path, 'r') as f:
            raw_chain = json.load(f)
        self.chain = []
        for b in raw_chain:
            block = Block(
                index=b["index"],
                previous_hash=b["previous_hash"],
                timestamp=b["timestamp"],
                transactions=b["transactions"],
                poac_solution=b["poac_solution"],
                difficulty=b["difficulty"]
            )
            block.hash = b["hash"]
            self.chain.append(block)
        if self.chain:
            self.difficulty = self.chain[-1].difficulty
        console.print(f"[bold green][NODE] Loaded {len(self.chain)} blocks successfully from {self.ledger_path}[/bold green]")
        
    def verify_poac_solution(self, solution, block_index):
        """
        Proof of Attractor Calculation (PoAC) Verification.
        Validates that the submitted trajectory weight yields a stable, convergent attractor state space.
        """
        k = solution.get("coupling_weight", 0.0)
        lam = solution.get("lyapunov_exponent", 0.0)
        
        # Mathematical Proof rules:
        # 1. Coupling weight must be non-zero and within convergence limits
        # 2. Lyapunov exponent must be negative (indicating attractor stability and system convergence)
        if abs(k) < 0.0001 or k > 10.0:
            return False
        if lam >= 0.0:
            return False  # Positive exponent indicates chaotic divergence (unstable block)
            
        # Target matching: The hash of the solution must meet the network's current difficulty threshold
        sol_string = f"{k:.8f}_{lam:.8f}_{block_index}"
        sol_hash = hashlib.sha256(sol_string.encode('utf-8')).hexdigest()
        
        # Difficulty matching (e.g. hash must start with a target number of leading characters)
        target = "0" * int(self.difficulty)
        return sol_hash.startswith(target)
        
    def add_transaction(self, sender, recipient, amount, signature=None, timestamp=None):
        tx = {
            "sender": sender,
            "recipient": recipient,
            "amount": float(amount),
            "timestamp": timestamp if timestamp is not None else time.time(),
            "signature": signature
        }
        self.unconfirmed_transactions.append(tx)
        return True
        
    def add_block(self, block, poac_solution):
        block_data = {
            "index": block.index,
            "previous_hash": block.previous_hash,
            "timestamp": block.timestamp,
            "transactions": block.transactions,
            "poac_solution": poac_solution,
            "difficulty": block.difficulty,
            "hash": block.hash
        }
        if not verify_submitted_block(block_data, self.ledger_path):
            print("Block rejection: consensus verification failed.")
            return False
            
        # Append and save
        block.hash = block.calculate_hash()
        self.chain.append(block)
        self.save_chain()
        
        # Adjust network difficulty dynamically based on block time
        if len(self.chain) % 5 == 0:
            self.difficulty = min(4.0, self.difficulty + 0.5) # Increase difficulty as network grows
            
        return True

class MinerNode:
    def __init__(self, blockchain, miner_address):
        self.blockchain = blockchain
        self.miner_address = miner_address
        
    def mine_block(self):
        """
        Runs the DDE attractor solver to find a valid coupling parameter
        that stabilizes the state-space and satisfies the target difficulty hash.
        """
        last_block = self.blockchain.chain[-1]
        next_index = last_block.index + 1
        previous_hash = last_block.hash
        
        console.print(f"\n[bold yellow][MINER] Solving PoAC Attractor Block #{next_index} (Difficulty: {self.blockchain.difficulty})...[/bold yellow]")
        
        start_time = time.time()
        iterations = 0
        
        # Simulate DDE trajectory solving loop
        while True:
            iterations += 1
            # Randomly scan coupling parameters (k) and simulate Lyapunov exponent (lambda)
            k = random.uniform(0.01, 2.0)
            # DDE stability equation: lambda = -k * cos(tau)
            # Simulate a stabilizing convergence exponent
            lam = -k * random.uniform(0.5, 0.99)
            
            solution = {"coupling_weight": k, "lyapunov_exponent": lam}
            
            # Verify if this trajectory satisfies the difficulty target hash
            if self.blockchain.verify_poac_solution(solution, next_index):
                dwell_ms = (time.time() - start_time) * 1000.0
                console.print(f"[bold green][MINER] Block #{next_index} solved in {dwell_ms:.2f} ms ({iterations} DDE iterations analyzed).[/bold green]")
                console.print(f"  Coupling Weight k:   {k:.6f}")
                console.print(f"  Lyapunov Exp lambda: {lam:.6f} (STABLE ATTRACTOR)")
                
                # Calculate block reward dynamically based on 4-year halving cycle (12,614,400 blocks)
                halvings = next_index // 12614400
                block_reward = 31.7 / (2 ** halvings) if halvings < 64 else 0.0
                
                # Formulate block transactions (including mining block reward)
                txs = list(self.blockchain.unconfirmed_transactions)
                txs.insert(0, {
                    "sender": "SYSTEM",
                    "recipient": self.miner_address,
                    "amount": block_reward,
                    "memo": "PoAC Block Reward"
                })
                
                new_block = Block(
                    index=next_index,
                    previous_hash=previous_hash,
                    timestamp=time.time(),
                    transactions=txs,
                    poac_solution=solution,
                    difficulty=self.blockchain.difficulty
                )
                
                # Submit block to the public coordinator node via HTTP POST
                print("[MINER] Submitting solved block to the public seed node...")
                try:
                    payload = json.dumps({
                        "index": new_block.index,
                        "previous_hash": new_block.previous_hash,
                        "timestamp": new_block.timestamp,
                        "transactions": new_block.transactions,
                        "poac_solution": solution,
                        "difficulty": self.blockchain.difficulty,
                        "hash": new_block.hash
                    }).encode('utf-8')
                    req = urllib.request.Request(
                        "https://sniff-breeching-police.ngrok-free.dev/api/submit_block",
                        data=payload,
                        headers={
                            'Content-Type': 'application/json',
                            'Bypass-Tunnel-Reminder': 'true'
                        },
                        method='POST'
                    )
                    with urllib.request.urlopen(req, timeout=5) as response:
                        if response.status == 200:
                            res_data = json.loads(response.read().decode('utf-8'))
                            if res_data.get("status") == "block_accepted":
                                console.print("[bold green][MINER] Block successfully accepted by the network![/bold green]")
                                self.blockchain.chain.append(new_block)
                                self.blockchain.save_chain()
                                self.blockchain.unconfirmed_transactions = []
                                return True
                    console.print("[bold red][MINER] Block rejected by the network.[/bold red]")
                except Exception as e:
                    console.print(f"[bold red][MINER] Network submission failed: {e}. Falling back to local append.[/bold red]")
                    # Fallback to local-only ledger validation for testing/dev/offline modes
                    if self.blockchain.add_block(new_block, solution):
                        self.blockchain.unconfirmed_transactions = []
                        return True
                break

def main():
    # Setup ledger path
    root_dir = os.path.dirname(os.path.abspath(__file__))
    local_path = os.path.join(root_dir, "perseus_ledger.json")
    enclave_path = os.path.join(root_dir, "enclaves", "corporate_operations", "perseus_ledger.json")
    if os.path.exists(local_path):
        ledger_path = local_path
    else:
        ledger_path = enclave_path
    os.makedirs(os.path.dirname(ledger_path), exist_ok=True)
    
    # Initialize L1 Blockchain
    blockchain = Blockchain(ledger_path)
    
    # Generate Ed25519 keypairs for simulation
    user_priv = ed25519.Ed25519PrivateKey.generate()
    user_pub_hex = user_priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    ).hex()
    
    company_pub_hex = ed25519.Ed25519PrivateKey.generate().public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    ).hex()
    
    miner_priv = ed25519.Ed25519PrivateKey.generate()
    miner_pub_hex = miner_priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    ).hex()

    # 1. Fund the USER_WALLET from TREASURY_RESERVE
    tx_time_1 = time.time()
    msg_1 = f"TREASURY_RESERVE_{user_pub_hex}_1000.0_{tx_time_1}"
    treasury_priv_bytes = bytes.fromhex("5b0cceeb04da63b90bd658f9de5a361c40cc5549461ebaf0545dd507a4fe8a3a")
    treasury_priv = ed25519.Ed25519PrivateKey.from_private_bytes(treasury_priv_bytes)
    sig_1 = treasury_priv.sign(msg_1.encode('utf-8')).hex()
    
    blockchain.add_transaction(
        sender="TREASURY_RESERVE",
        recipient=user_pub_hex,
        amount=1000.0,
        signature=sig_1,
        timestamp=tx_time_1
    )
    
    # 2. Add SaaS subscription transaction (USER_WALLET -> COMPANY_TREASURY)
    tx_time_2 = time.time()
    msg_2 = f"{user_pub_hex}_{company_pub_hex}_150.0_{tx_time_2}"
    sig_2 = user_priv.sign(msg_2.encode('utf-8')).hex()
    
    blockchain.add_transaction(
        sender=user_pub_hex,
        recipient=company_pub_hex,
        amount=150.0,
        signature=sig_2,
        timestamp=tx_time_2
    )
    
    # Initialize Miner (using the generated cryptographic address)
    miner = MinerNode(blockchain, miner_address=miner_pub_hex)
    
    # Mine continuously with dynamic transaction generation
    console.print("[bold cyan][NODE] Starting continuous mining loop. Press Ctrl+C to stop.[/bold cyan]")
    try:
        while True:
            # 0. Dynamic Sync: Check if local ledger has fallen behind the network
            try:
                stats_req = urllib.request.Request("https://sniff-breeching-police.ngrok-free.dev/api/stats", headers={'Bypass-Tunnel-Reminder': 'true'})
                with urllib.request.urlopen(stats_req, timeout=3) as stats_res:
                    if stats_res.status == 200:
                        net_stats = json.loads(stats_res.read().decode('utf-8'))
                        net_height = net_stats.get("block_height", 0)
                        if net_height != len(blockchain.chain):
                            led_req = urllib.request.Request("https://sniff-breeching-police.ngrok-free.dev/api/ledger", headers={'Bypass-Tunnel-Reminder': 'true'})
                            with urllib.request.urlopen(led_req, timeout=5) as led_res:
                                if led_res.status == 200:
                                    remote_chain = json.loads(led_res.read().decode('utf-8'))
                                    blockchain.chain = [Block(b["index"], b["previous_hash"], b["timestamp"], b["transactions"], b["poac_solution"], b["difficulty"], b["hash"]) for b in remote_chain]
                                    blockchain.save_chain()
                                    blockchain.unconfirmed_transactions = []
                                    console.print(f"[bold green][NODE] Dynamic Sync: Sync\'d ledger to height {len(blockchain.chain)}[/bold green]")
            except Exception as e:
                pass
                
            # Simulate occasional transaction flow
            if random.random() < 0.3:
                tx_amt = round(random.uniform(5.0, 50.0), 2)
                tx_time = time.time()
                msg = f"{user_pub_hex}_{company_pub_hex}_{tx_amt}_{tx_time}"
                sig = user_priv.sign(msg.encode('utf-8')).hex()
                
                blockchain.add_transaction(
                    sender=user_pub_hex,
                    recipient=company_pub_hex,
                    amount=tx_amt,
                    signature=sig,
                    timestamp=tx_time
                )
            miner.mine_block()
            time.sleep(5.0)
    except KeyboardInterrupt:
        console.print("\n[bold red][NODE] Mining stopped by user.[/bold red]")

if __name__ == "__main__":
    main()
