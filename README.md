# 🦙 Perseus Protocol: Proof-of-Attractor Layer 1 Blockchain

This repository contains the open-source validator node implementation of the **Perseus Coin (PRSC)** Layer 1 blockchain, utilizing the **Proof of Attractor Calculation (PoAC)** consensus mechanism.

---

## 🪙 Core Token Metrics & Economics

*   **Token Name**: Perseus Protocol Token
*   **Symbol**: `PRSC`
*   **Total Supply Cap**: 1,000,000,000 (1 Billion) fixed supply.
*   **Genesis Treasury Allocation**: 200,000,000 PRSC (20.0%) allocated to `TREASURY_RESERVE` for corporate operations, ecosystem development, and liquidity.
*   **Mining Pool Allocation**: 800,000,000 PRSC (80.0%) reserved strictly for node verification rewards.
*   **Emission Schedule**: 4-year halving cycle (every 12,614,400 blocks at 10s target block time).
    *   *Starting Block Reward:* 31.7 PRSC
    *   *Halving Rate:* cuts in half every 4 years, extending the mining lifetime to over 100+ years.

---

## 🔬 How to Verify This is Real (No Wasted Energy)

Unlike traditional cryptocurrencies that use energy-wasting hashing puzzles (SHA-256), the Perseus network uses **Proof of Useful Work (PoUW)**. Miners secure the network by solving continuous delay differential equations (DDE) representing dynamic attractor states.

The validator node codebase is fully open-source. Anyone can verify the cryptographic integrity of the ledger and the correctness of the solutions. However, the high-performance GPU mining solver client (`perseus-miner`) is distributed as a pre-compiled binary to protect the platform's proprietary simulation algorithms and trading mathematical moats.

### The Verification Rules:
Any open-source node can cryptographically verify that a block is valid by checking two mathematical rules in the block's `poac_solution`:
1.  **Viscoelastic Coupling Weight ($k$)**: Must reside within stable bounds ($0.0001 <= k <= 10.0$).
2.  **Lyapunov Stability Exponent (\lambda)**: Must be strictly negative (\lambda < 0). A negative exponent mathematically proves the DDE trajectory is stable and converges to a single attractor point, rather than diverging chaotically.

---

## 📂 Project Structure

*   `perseus_coin_node.py`: The open-source Layer 1 ledger node codebase.
*   `perseus_ledger.json`: The live blockchain ledger database containing the Genesis Block and the early GPU-mined history.

---

## 🚀 How to Run and Verify Locally

### 1. Prerequisites
Ensure you have Python installed, along with the `rich` styling library and `cryptography` package:
```bash
pip install rich cryptography
```

### 2. Run the Blockchain Node
Initialize the ledger and check the current block status:
```bash
python perseus_coin_node.py
```
This will load `perseus_ledger.json` and verify the cryptographic integrity of all blocks on the chain.