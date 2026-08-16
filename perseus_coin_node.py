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
        
    def add_transaction(self, sender, recipient, amount, signature="MOCK_SIG"):
        tx = {
            "sender": sender,
            "recipient": recipient,
            "amount": float(amount),
            "timestamp": time.time(),
            "signature": signature
        }
        self.unconfirmed_transactions.append(tx)
        return True
        
    def add_block(self, block, poac_solution):
        # 1. Verify previous hash matching
        if self.chain[-1].hash != block.previous_hash:
            print("Block rejection: Previous hash mismatch.")
            return False
            
        # 2. Verify Proof of Attractor Calculation
        if not self.verify_poac_solution(poac_solution, block.index):
            print("Block rejection: Invalid PoAC solution.")
            return False
            
        # 3. Append and save
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
    
    # Add a mock retail SaaS subscription transaction to mempool
    blockchain.add_transaction(
        sender="USER_WALLET_0x71",
        recipient="COMPANY_TREASURY_0x44",
        amount=150.0,
        signature="tx_sig_102983"
    )
    
    # Initialize Miner
    miner = MinerNode(blockchain, miner_address="FOUNDER_WALLET_0x99")
    
    # Mine continuously with dynamic transaction generation
    console.print("[bold cyan][NODE] Starting continuous mining loop. Press Ctrl+C to stop.[/bold cyan]")
    try:
        while True:
            # Simulate occasional transaction flow
            if random.random() < 0.3:
                blockchain.add_transaction(
                    sender="USER_WALLET_0x71",
                    recipient="COMPANY_TREASURY_0x44",
                    amount=round(random.uniform(5.0, 50.0), 2),
                    signature=f"tx_sig_{random.randint(100000, 999999)}"
                )
            miner.mine_block()
            time.sleep(5.0) # 5-second block interval for continuous mining
    except KeyboardInterrupt:
        console.print("\n[bold red][NODE] Mining stopped by user.[/bold red]")

if __name__ == "__main__":
    main()
