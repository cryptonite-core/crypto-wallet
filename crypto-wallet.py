"""
Crypto Wallet

This script generates random cryptocurrency wallets (BTC, ETH, BNB) and checks their balances using public APIs.
It supports proxy usage for network requests and multi-threading for faster scanning.

Usage:
    Run the script and follow prompts to select the chain, number of wallets, threads, and delay.

Dependencies:
    - eth_account
    - web3
    - requests
    - rich
    - ecdsa
    - base58
    - coincurve (optional, for faster cryptography)

Author: Muhammad Hridoy
Date: 2025-08-08
License: MIT

Warning:
    This tool is for educational and research purposes only.
    Finding funded wallets randomly is extremely unlikely.
"""
import os
import sys
import time
import secrets
import queue
import random
import hashlib
from concurrent.futures import ThreadPoolExecutor
import requests
from eth_account import Account
from web3 import Web3
from rich.console import Console
import ecdsa
import base58

console = Console()
bsc_rpc_url = "https://bsc-dataseed.binance.org/"
w3_bsc = Web3(Web3.HTTPProvider(bsc_rpc_url))
result_queue = queue.Queue()

def fetch_proxies():
    url = "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            proxies = resp.text.strip().split('\n')
            proxies = [p.strip() for p in proxies if p.strip()]
            console.print(f"[bold white]\n Fetched [bold green]{len(proxies)} [bold white]proxies from ProxyScrape[/]\n");time.sleep(3)
            return proxies
    except Exception as e:
        console.print(f"[bold white]\n Failed to fetch proxies: [bold red]{e}[/]\n");time.sleep(3)
    return []

proxy_list = fetch_proxies()

def get_random_proxy():
    if proxy_list:
        return random.choice(proxy_list)
    return None

def request_with_proxy(url):
    for _ in range(5):
        proxy = get_random_proxy()
        if not proxy:
            return requests.get(url, timeout=6)
        proxies = {
            "http": f"http://{proxy}",
            "https": f"http://{proxy}"
        }
        try:
            resp = requests.get(url, proxies=proxies, timeout=6)
            if resp.status_code == 200:
                return resp
        except:
            continue
    return requests.get(url, timeout=6)

def generate_eth_wallet():
    acct = Account.create(secrets.token_hex(32))
    return acct.address, acct.key.hex()

def generate_bnb_wallet():
    return generate_eth_wallet()

def generate_btc_wallet():
    private_key = secrets.token_bytes(32)
    sk = ecdsa.SigningKey.from_string(private_key, curve=ecdsa.SECP256k1)
    vk = sk.get_verifying_key()
    pubkey = b'\x04' + vk.to_string()

    sha256_pk = hashlib.sha256(pubkey).digest()
    ripemd160_pk = hashlib.new('ripemd160', sha256_pk).digest()
    payload = b'\x00' + ripemd160_pk
    checksum = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    address = base58.b58encode(payload + checksum).decode()

    wif_payload = b'\x80' + private_key
    wif_checksum = hashlib.sha256(hashlib.sha256(wif_payload).digest()).digest()[:4]
    wif = base58.b58encode(wif_payload + wif_checksum).decode()

    return address, wif

def check_eth_balance(address):
    url = f"https://api.blockcypher.com/v1/eth/main/addrs/{address}/balance"
    try:
        resp = request_with_proxy(url)
        if resp.status_code == 200:
            data = resp.json()
            balance = data.get("final_balance", 0)
            return balance / 1e18
    except:
        pass
    return 0

def check_bnb_balance(address):
    try:
        balance_wei = w3_bsc.eth.get_balance(address)
        return w3_bsc.fromWei(balance_wei, 'ether')
    except:
        return 0

def check_btc_balance(address):
    url = f"https://blockstream.info/api/address/{address}"
    try:
        resp = request_with_proxy(url)
        if resp.status_code == 200:
            data = resp.json()
            confirmed = data.get('chain_stats', {}).get('funded_txo_sum', 0)
            unconfirmed = data.get('mempool_stats', {}).get('funded_txo_sum', 0)
            balance_sats = confirmed + unconfirmed
            return balance_sats / 1e8
    except:
        pass
    return 0

def worker(chain, n, delay):
    for _ in range(n):
        try:
            if chain == "ETH":
                addr, priv = generate_eth_wallet()
                bal = check_eth_balance(addr)
                console.print(f"[bold blue]ETH Wallet:[/] Address: {addr} | PrivKey: {priv} | Balance: {bal:.8f} ETH")
                if bal > 0:
                    console.print(f"[bold green][ETH FOUND][/]: {addr} balance: {bal:.8f} ETH")
                    result_queue.put((chain, addr, priv, bal))
            elif chain == "BNB":
                addr, priv = generate_bnb_wallet()
                bal = check_bnb_balance(addr)
                console.print(f"[bold blue]BNB Wallet:[/] Address: {addr} | PrivKey: {priv} | Balance: {bal:.8f} BNB")
                if bal > 0:
                    console.print(f"[bold green][BNB FOUND][/]: {addr} balance: {bal:.8f} BNB")
                    result_queue.put((chain, addr, priv, bal))
            elif chain == "BTC":
                addr, priv = generate_btc_wallet()
                bal = check_btc_balance(addr)
                console.print(f"[bold blue]BTC Wallet:[/] Address: {addr} | PrivKey: {priv} | Balance: {bal:.8f} BTC")
                if bal > 0:
                    console.print(f"[bold green][BTC FOUND][/]: {addr} balance: {bal:.8f} BTC")
                    result_queue.put((chain, addr, priv, bal))
            else:
                console.print(f"[red]Unknown chain: {chain}[/]")
                return
        except Exception as e:
            console.print(f"[red]Error in worker: {e}[/]")
        time.sleep(delay)

def main():
    os.system('cls' if os.name == 'nt' else 'clear')
    print()
    console.print("[bold purple]Crypto Wallet Scanner with Proxy Support[/]\n")
    console.print("[bold red]Warning:[/] [bold white]Finding funded wallets randomly is almost impossible.")
    console.print("[bold white]Use this tool responsibly and for research only.\n")

    chains = ["BTC", "ETH", "BNB"]
    chain = console.input("Choose chain to scan [BTC/ETH/BNB]: ").strip().upper()
    if chain not in chains:
        console.print("[red]Invalid chain selected.[/]")
        sys.exit(1)

    try:
        total = int(console.input("Number of addresses to generate and check: ").strip())
        threads = int(console.input("Number of parallel threads: ").strip())
        delay = float(console.input("Delay between checks (seconds, e.g. 0.1): ").strip())
    except:
        console.print("[red]Invalid input for numbers.[/]")
        sys.exit(1)

    per_thread = total // threads
    console.print(f"\nScanning {total} {chain} addresses using {threads} threads with {delay}s delay...\n")

    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = []
        for _ in range(threads):
            futures.append(executor.submit(worker, chain, per_thread, delay))
        for future in futures:
            future.result()

    if result_queue.empty():
        console.print("[bold red]No funded wallets found.[/]")
    else:
        filename = f"found_{chain}_wallets.txt"
        with open(filename, "a") as f:
            while not result_queue.empty():
                ch, addr, priv, bal = result_queue.get()
                f.write(f"{ch} {addr} {priv} Balance: {bal:.8f}\n")
        console.print(f"[bold green]Saved found wallets with balances to {filename}[/]")

if __name__ == "__main__":
    main()
