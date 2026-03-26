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
Date  : 26-03-2026
License: MIT

Warning:
    This tool is for educational and research purposes only.
    Finding funded wallets randomly is extremely unlikely.
"""
import os
import sys
import time
import queue
import random
import ecdsa
import base58
import hashlib
import logging
import secrets
import threading
import requests
from rich import box
from web3 import Web3
from typing import Optional
from datetime import datetime
from eth_account import Account
from rich.panel import Panel
from rich.table import Table
from rich.console import Console
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor

console = Console()

logging.basicConfig(
    filename="scanner_debug.log",
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

BSC_RPC_URLS = [
    "https://bsc-dataseed.binance.org/",
    "https://bsc-dataseed1.defibit.io/",
    "https://bsc-dataseed1.ninicoin.io/",
    "https://bsc-dataseed2.defibit.io/",
]

PROXY_SOURCES = [
    "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
]

ETH_BALANCE_APIS = [
    "https://api.blockcypher.com/v1/eth/main/addrs/{address}/balance",
    "https://api.ethplorer.io/getAddressInfo/{address}?apiKey=freekey",
]

BTC_BALANCE_APIS = [
    "https://blockstream.info/api/address/{address}",
    "https://blockchain.info/rawaddr/{address}?limit=0",
    "https://api.blockcypher.com/v1/btc/main/addrs/{address}/balance",
]

DEFAULT_TIMEOUT  = 8
RATE_LIMIT_SLEEP = 2.5

@dataclass
class WalletResult:
    chain:   str
    address: str
    privkey: str
    balance: float
    ts:      str = field(default_factory=lambda: datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))

@dataclass
class ScanStats:
    total:  int = 0
    found:  int = 0
    errors: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def inc_total(self):
        with self._lock: self.total += 1

    def inc_found(self):
        with self._lock: self.found += 1

    def inc_errors(self):
        with self._lock: self.errors += 1

def _make_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.6,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=50)
    session.mount("https://", adapter)
    session.mount("http://",  adapter)
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; CryptoScanner/2.0)",
        "Accept": "application/json",
    })
    return session

_session = _make_session()
_session_lock = threading.Lock()

def _get(url: str, proxy: Optional[str] = None, retries: int = 4) -> Optional[requests.Response]:
    proxies = {"http": f"http://{proxy}", "https": f"http://{proxy}"} if proxy else None
    for attempt in range(retries):
        try:
            with _session_lock:
                resp = _session.get(url, proxies=proxies, timeout=DEFAULT_TIMEOUT)
            if resp.status_code == 429:
                time.sleep(RATE_LIMIT_SLEEP * (attempt + 1))
                continue
            if resp.status_code == 200:
                return resp
        except requests.RequestException:
            time.sleep(0.3 * (attempt + 1))
    return None

def fetch_proxies() -> list:
    collected = []
    for source in PROXY_SOURCES:
        try:
            resp = requests.get(source, timeout=10)
            if resp.status_code == 200:
                lines = [p.strip() for p in resp.text.strip().splitlines() if p.strip()]
                collected.extend(lines)
        except Exception:
            continue
    seen = list(dict.fromkeys(collected))
    console.print(f"[bold white]\n Fetched [bold green]{len(seen)}[/bold green] proxies from {len(PROXY_SOURCES)} sources[/]\n")
    time.sleep(2)
    return seen

proxy_list = fetch_proxies()

def _init_bsc_web3() -> Web3:
    for url in BSC_RPC_URLS:
        try:
            w3 = Web3(Web3.HTTPProvider(url, request_kwargs={"timeout": DEFAULT_TIMEOUT}))
            if w3.is_connected():
                return w3
        except Exception:
            continue
    return Web3(Web3.HTTPProvider(BSC_RPC_URLS[0]))

w3_bsc = _init_bsc_web3()

def get_random_proxy() -> Optional[str]:
    return random.choice(proxy_list) if proxy_list else None

def generate_eth_wallet():
    acct = Account.create(secrets.token_hex(32))
    return acct.address, acct.key.hex()

def generate_bnb_wallet():
    return generate_eth_wallet()

def generate_btc_wallet():
    private_key = secrets.token_bytes(32)

    try:
        import coincurve
        pubkey = coincurve.PublicKey.from_valid_secret(private_key).format(compressed=False)
    except ImportError:
        sk     = ecdsa.SigningKey.from_string(private_key, curve=ecdsa.SECP256k1)
        pubkey = b'\x04' + sk.get_verifying_key().to_string()

    sha256_pk   = hashlib.sha256(pubkey).digest()
    ripemd160   = hashlib.new('ripemd160', sha256_pk).digest()
    payload     = b'\x00' + ripemd160
    checksum    = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    address     = base58.b58encode(payload + checksum).decode()

    wif_payload  = b'\x80' + private_key
    wif_checksum = hashlib.sha256(hashlib.sha256(wif_payload).digest()).digest()[:4]
    wif          = base58.b58encode(wif_payload + wif_checksum).decode()
    return address, wif

def check_eth_balance(address: str) -> float:
    for template in ETH_BALANCE_APIS:
        url  = template.format(address=address)
        resp = _get(url, proxy=get_random_proxy())
        if resp is None:
            continue
        try:
            data = resp.json()
            if "blockcypher" in url:
                return data.get("final_balance", 0) / 1e18
            if "ethplorer" in url:
                return float(data.get("ETH", {}).get("balance", 0))
        except Exception:
            continue
    return 0.0

def check_bnb_balance(address: str) -> float:
    for url in BSC_RPC_URLS:
        try:
            w3 = Web3(Web3.HTTPProvider(url, request_kwargs={"timeout": DEFAULT_TIMEOUT}))
            if w3.is_connected():
                bal = w3.eth.get_balance(address)
                return float(w3.from_wei(bal, "ether"))
        except Exception:
            continue
    return 0.0

def check_btc_balance(address: str) -> float:
    for template in BTC_BALANCE_APIS:
        url  = template.format(address=address)
        resp = _get(url, proxy=get_random_proxy())
        if resp is None:
            continue
        try:
            data = resp.json()
            if "blockstream" in url:
                c = data.get("chain_stats",  {}).get("funded_txo_sum", 0)
                m = data.get("mempool_stats", {}).get("funded_txo_sum", 0)
                return (c + m) / 1e8
            if "blockchain.info" in url:
                return data.get("final_balance", 0) / 1e8
            if "blockcypher" in url:
                return data.get("final_balance", 0) / 1e8
        except Exception:
            continue
    return 0.0

def worker(chain: str, n: int, delay: float, stats: ScanStats, result_queue: queue.Queue) -> None:
    balance_fns = {"ETH": check_eth_balance, "BNB": check_bnb_balance, "BTC": check_btc_balance}
    gen_fns     = {"ETH": generate_eth_wallet, "BNB": generate_bnb_wallet, "BTC": generate_btc_wallet}

    balance_fn = balance_fns[chain]
    gen_fn     = gen_fns[chain]

    for _ in range(n):
        try:
            addr, priv = gen_fn()
            bal        = balance_fn(addr)
            stats.inc_total()

            console.print(
                f"[bold blue]{chain} Wallet:[/] Address: {addr} | "
                f"PrivKey: {priv} | Balance: {bal:.8f} {chain}"
            )

            if bal > 0:
                console.print(f"[bold green][{chain} FOUND][/]: {addr} balance: {bal:.8f} {chain}")
                stats.inc_found()
                result_queue.put(WalletResult(chain=chain, address=addr, privkey=priv, balance=bal))

        except Exception as e:
            stats.inc_errors()
            console.print(f"[red]Error in worker: {e}[/]")
            logging.warning("worker error: %s", e)

        time.sleep(delay)

def _print_summary(stats: ScanStats, chain: str, filename: Optional[str]) -> None:
    console.print(f"\n[bold white]Chain:[/]    [bold cyan]{chain}[/]")
    console.print(f"[bold white]Scanned:[/]  [bold cyan]{stats.total}[/]")
    console.print(f"[bold white]Found:[/]    [bold green]{stats.found}[/]")
    console.print(f"[bold white]Errors:[/]   [bold red]{stats.errors}[/]\n")
    if filename:
        console.print(f"[bold white]Saved to:[/] [bold yellow]{filename}[/]")

def main():
    os.system('cls' if os.name == 'nt' else 'clear')
    print()
    console.print("[bold purple]Crypto Wallet Scanner with Proxy Support[/]\n")
    console.print("[bold red]Warning:[/] [bold white]Finding funded wallets randomly is almost impossible.")
    console.print("[bold white]Use this tool responsibly and for research only.\n")

    chains = {"BTC", "ETH", "BNB"}
    chain  = console.input("Choose chain to scan [BTC/ETH/BNB]: ").strip().upper()
    if chain not in chains:
        console.print("[red]Invalid chain selected.[/]")
        sys.exit(1)

    try:
        total   = int(console.input("Number of addresses to generate and check: ").strip())
        threads = int(console.input("Number of parallel threads: ").strip())
        delay   = float(console.input("Delay between checks (seconds, e.g. 0.1): ").strip())
    except ValueError:
        console.print("[red]Invalid input for numbers.[/]")
        sys.exit(1)

    threads    = max(1, min(threads, total))
    per_thread = total // threads
    remainder  = total % threads

    stats        = ScanStats()
    result_queue = queue.Queue()

    console.print(
        f"\nScanning [bold cyan]{total}[/] {chain} addresses using "
        f"[bold cyan]{threads}[/] threads with [bold cyan]{delay}s[/] delay…\n"
    )

    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = [
            executor.submit(worker, chain, per_thread + (1 if i < remainder else 0), delay, stats, result_queue)
            for i in range(threads)
        ]
        for f in futures:
            f.result()

    filename = None
    if not result_queue.empty():
        filename = f"found_{chain}_wallets.txt"
        with open(filename, "a") as fh:
            while not result_queue.empty():
                r = result_queue.get()
                fh.write(f"{r.chain} {r.address} {r.privkey} Balance: {r.balance:.8f} [{r.ts}]\n")
        console.print(f"[bold green]Saved found wallets to {filename}[/]")
    else:
        console.print("\n[bold red]No funded wallets found.[/]")

    _print_summary(stats, chain, filename)

if __name__ == "__main__":
    main()
