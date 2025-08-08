<h1 align="center">Crypto Wallet</h1>

**A tool for generating and scanning cryptocurrency wallets (BTC, ETH, BNB) for balances using proxy servers. Intended for research and educational use.**

## Features

- Supports Bitcoin, Ethereum, and Binance Smart Chain wallet generation  
- Checks wallet balances via public APIs and blockchain nodes  
- Utilizes proxy servers to reduce rate limiting and IP blocking  
- Multi-threaded scanning for improved performance  
- Saves any wallets found with balances to a file

## Demonstration
[![asciicast](https://asciinema.org/a/732451.svg)](https://asciinema.org/a/732451)
  
## Required packages for Termux (Android)

```bash
pkg update && pkg upgrade
pkg install -y git curl clang python libffi openssl libsecp256k1
```

## Required packages for Linux

```bash
sudo apt update && sudo apt upgrade
sudo apt install build-essential python3-dev libffi-dev libssl-dev libsecp256k1-dev
```

## Installation
```bash
git clone https://github.com/cryptonite-core/crypto-wallet.git
cd crypto-wallet
pip install -r requirements.txt
```

## Usage
```bash
python crypto-wallet.py
```

## Disclaimer
**This tool is provided for educational and research purposes only. The author is not responsible for any damage, loss, or legal issues resulting from its misuse. Use responsibly and at your own.**
