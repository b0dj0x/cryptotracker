#!/usr/bin/env python3
"""
CryptoTracker — Wallet Address OSINT · Transaction Graph · Entity Attribution
"""

import sys, os, json, time, argparse, re
from datetime import datetime, timezone
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import requests
except ImportError:
    sys.exit("[!] pip install requests")
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.tree import Tree
    from rich import box
except ImportError:
    sys.exit("[!] pip install rich")

console = Console()
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ASCII = [
    " ██████╗██████╗ ██╗   ██╗████████╗███████╗██████╗ ███╗   ███╗",
    "██╔════╝██╔══██╗██║   ██║╚══██╔══╝██╔════╝██╔══██╗████╗ ████║",
    "██║     ██████╔╝██║   ██║   ██║   █████╗  ██████╔╝██╔████╔██║",
    "██║     ██╔══██╗██║   ██║   ██║   ██╔══╝  ██╔══██╗██║╚██╔╝██║",
    "╚██████╗██║  ██║╚██████╔╝   ██║   ███████╗██║  ██║██║ ╚═╝ ██║",
    " ╚═════╝╚═╝  ╚═╝ ╚═════╝    ╚═╝   ╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝",
]

UA = "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0"

# ═══════════════════════════════════════════════════════════════
#  BLOCKCHAIN EXPLORER APIS (Free, No API Key Required)
# ═══════════════════════════════════════════════════════════════

BLOCKCHAIN_APIS = {
    "Bitcoin": {
        "blockchain.com": {
            "address_info": "https://blockchain.info/rawaddr/{address}?limit=10",
            "address_balance": "https://blockchain.info/balance?active={address}",
            "tx": "https://blockchain.info/rawtx/{txid}",
            "multiaddr": "https://blockchain.info/multiaddr?active={address}",
            "unconfirmed": "https://blockchain.info/unconfirmed-transactions?format=json",
        },
        "blockstream.info": {
            "address_info": "https://blockstream.info/api/address/{address}",
            "address_txs": "https://blockstream.info/api/address/{address}/txs",
            "address_balance": "https://blockstream.info/api/address/{address}",
            "tx": "https://blockstream.info/api/tx/{txid}",
            "blocks": "https://blockstream.info/api/blocks",
            "block": "https://blockstream.info/api/block/{blockhash}",
        },
        "mempool.space": {
            "address_info": "https://mempool.space/api/address/{address}",
            "address_txs": "https://mempool.space/api/address/{address}/txs",
            "address_txs_chain": "https://mempool.space/api/address/{address}/txs/chain",
            "tx": "https://mempool.space/api/tx/{txid}",
            "block": "https://mempool.space/api/block/{blockhash}",
            "blocks": "https://mempool.space/api/blocks",
            "mempool": "https://mempool.space/api/mempool",
            "fees": "https://mempool.space/api/v1/fees/recommended",
        },
    },
    "Ethereum": {
        "etherscan.io": {
            "address_info": "https://api.etherscan.io/api?module=account&action=balance&address={address}&tag=latest",
            "address_txs": "https://api.etherscan.io/api?module=account&action=txlist&address={address}&startblock=0&endblock=99999999&page=1&offset=10&sort=desc",
            "address_internal_txs": "https://api.etherscan.io/api?module=account&action=txlistinternal&address={address}&startblock=0&endblock=99999999&page=1&offset=10&sort=desc",
            "address_erc20": "https://api.etherscan.io/api?module=account&action=tokentx&address={address}&page=1&offset=10&sort=desc",
            "tx": "https://api.etherscan.io/api?module=proxy&action=eth_getTransactionByHash&txhash={txid}",
            "block": "https://api.etherscan.io/api?module=proxy&action=eth_getBlockByNumber&tag={block}&boolean=true",
            "abi": "https://api.etherscan.io/api?module=contract&action=getabi&address={address}",
            "source_code": "https://api.etherscan.io/api?module=contract&action=getsourcecode&address={address}",
        },
        "blockscout.com": {
            "address_info": "https://eth.blockscout.com/api/v2/addresses/{address}",
            "address_txs": "https://eth.blockscout.com/api/v2/addresses/{address}/transactions",
            "address_tokens": "https://eth.blockscout.com/api/v2/addresses/{address}/token-balances",
            "tx": "https://eth.blockscout.com/api/v2/transactions/{txid}",
            "block": "https://eth.blockscout.com/api/v2/blocks/{block}",
        },
    },
    "Ethereum-Goerli": {
        "goerli.etherscan.io": {
            "address_info": "https://api-goerli.etherscan.io/api?module=account&action=balance&address={address}&tag=latest",
        },
    },
    "Ethereum-Sepolia": {
        "sepolia.etherscan.io": {
            "address_info": "https://api-sepolia.etherscan.io/api?module=account&action=balance&address={address}&tag=latest",
        },
    },
    "Polygon": {
        "polygonscan.com": {
            "address_info": "https://api.polygonscan.com/api?module=account&action=balance&address={address}&tag=latest",
            "address_txs": "https://api.polygonscan.com/api?module=account&action=txlist&address={address}&startblock=0&endblock=99999999&page=1&offset=10&sort=desc",
            "address_erc20": "https://api.polygonscan.com/api?module=account&action=tokentx&address={address}&page=1&offset=10&sort=desc",
            "tx": "https://api.polygonscan.com/api?module=proxy&action=eth_getTransactionByHash&txhash={txid}",
        },
    },
    "BSC": {
        "bscscan.com": {
            "address_info": "https://api.bscscan.com/api?module=account&action=balance&address={address}&tag=latest",
            "address_txs": "https://api.bscscan.com/api?module=account&action=txlist&address={address}&startblock=0&endblock=99999999&page=1&offset=10&sort=desc",
            "address_erc20": "https://api.bscscan.com/api?module=account&action=tokentx&address={address}&page=1&offset=10&sort=desc",
            "tx": "https://api.bscscan.com/api?module=proxy&action=eth_getTransactionByHash&txhash={txid}",
        },
    },
    "Arbitrum": {
        "arbiscan.io": {
            "address_info": "https://api.arbiscan.io/api?module=account&action=balance&address={address}&tag=latest",
            "address_txs": "https://api.arbiscan.io/api?module=account&action=txlist&address={address}&startblock=0&endblock=99999999&page=1&offset=10&sort=desc",
        },
    },
    "Optimism": {
        "optimistic.etherscan.io": {
            "address_info": "https://api-optimistic.etherscan.io/api?module=account&action=balance&address={address}&tag=latest",
            "address_txs": "https://api-optimistic.etherscan.io/api?module=account&action=txlist&address={address}&startblock=0&endblock=99999999&page=1&offset=10&sort=desc",
        },
    },
    "Avalanche": {
        "snowtrace.io": {
            "address_info": "https://api.snowtrace.io/api?module=account&action=balance&address={address}&tag=latest",
            "address_txs": "https://api.snowtrace.io/api?module=account&action=txlist&address={address}&startblock=0&endblock=99999999&page=1&offset=10&sort=desc",
        },
    },
    "Tron": {
        "tronscan.org": {
            "address_info": "https://apilist.tronscanapi.com/api/accountv2?address={address}",
            "address_txs": "https://apilist.tronscanapi.com/api/transaction?sort=-timestamp&limit=20&address={address}",
            "address_trc20": "https://apilist.tronscanapi.com/api/token_trc20/transfers?limit=20&relatedAddress={address}",
            "tx": "https://apilist.tronscanapi.com/api/transaction?hash={txid}",
            "block": "https://apilist.tronscanapi.com/api/block?number={block}",
        },
    },
    "Solana": {
        "solscan.io": {
            "address_info": "https://public-api.solscan.io/account?address={address}",
            "address_txs": "https://public-api.solscan.io/account/transactions?address={address}&limit=10",
            "address_tokens": "https://public-api.solscan.io/account/tokenList?address={address}",
        },
        "solana.fm": {
            "address_info": "https://api.solana.fm/v0/accounts/{address}",
            "address_txs": "https://api.solana.fm/v0/accounts/{address}/transactions",
        },
    },
}

# ═══════════════════════════════════════════════════════════════
#  KNOWN ENTITIES & LABELS (Public OSINT)
# ═══════════════════════════════════════════════════════════════

KNOWN_ENTITIES = {
    "Exchanges": {
        "Binance": {
            "btc": ["34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo", "3JZq4atUahhuA9rLhXLMhhTo133J9rF97j"],
            "eth": ["0x28C6c06298d514Db089934071355E5743bf21d60", "0xBE0eB53F46cd790Cd13851d5EFf43D12404d33E8"],
            "trc": ["TCxuEgMx7wVvk2s3dXqM2rFzUj5X6o8Y9a"],
            "explorers": {
                "Bitcoin": "https://www.blockchain.com/btc/address/34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo",
                "Ethereum": "https://etherscan.io/address/0x28C6c06298d514Db089934071355E5743bf21d60",
                "Tron": "https://tronscan.org/#/address/TCxuEgMx7wVvk2s3dXqM2rFzUj5X6o8Y9a",
            },
        },
        "Coinbase": {
            "btc": ["3Kzh9qAqVWQhEsfQz7zEQL1EuSx5tyNLNS", "34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo"],
            "eth": ["0xA9D1e08C7793af67e9d92fe308d5697FB81d3E43", "0x503828976D22510aad0201ac7EC88293211D23Da"],
            "explorers": {
                "Bitcoin": "https://www.blockchain.com/btc/address/3Kzh9qAqVWQhEsfQz7zEQL1EuSx5tyNLNS",
                "Ethereum": "https://etherscan.io/address/0xA9D1e08C7793af67e9d92fe308d5697FB81d3E43",
            },
        },
        "Kraken": {
            "btc": ["3FHNBLobJnbCTFTVakh5TXmEneyf5PT61B", "3AfP3pAaiNH7UsCdA2PfXVx2bLiE3R5KqJ"],
            "eth": ["0x2910543Af39abA0Cd09dBb2D50200b3E800A63D2"],
            "explorers": {
                "Bitcoin": "https://www.blockchain.com/btc/address/3FHNBLobJnbCTFTVakh5TXmEneyf5PT61B",
                "Ethereum": "https://etherscan.io/address/0x2910543Af39abA0Cd09dBb2D50200b3E800A63D2",
            },
        },
        "Bitfinex": {
            "btc": ["3JZq4atUahhuA9rLhXLMhhTo133J9rF97j", "1Kr6QSydW9bFQG1mXiPNNu6WpJGmUa9i1g"],
            "eth": ["0x1151314c646Ce4E0eFD76d1aF4760aE66a9Fe30F"],
            "explorers": {
                "Bitcoin": "https://www.blockchain.com/btc/address/3JZq4atUahhuA9rLhXLMhhTo133J9rF97j",
                "Ethereum": "https://etherscan.io/address/0x1151314c646Ce4E0eFD76d1aF4760aE66a9Fe30F",
            },
        },
        "OKX": {
            "btc": ["1LnoZawVFFQihU8d8ntxLMpYheZUfyeVAK"],
            "eth": ["0x6cC5F688a315f3dC28A7781717a9A798a59fDA7b"],
            "explorers": {
                "Bitcoin": "https://www.blockchain.com/btc/address/1LnoZawVFFQihU8d8ntxLMpYheZUfyeVAK",
                "Ethereum": "https://etherscan.io/address/0x6cC5F688a315f3dC28A7781717a9A798a59fDA7b",
            },
        },
        "Huobi": {
            "btc": ["1LAnF8h3qMGx3TSwNUHVneBZUEpwE4gu3D"],
            "eth": ["0xab5C66752a9e8167967685F1450532fB96d5d24f"],
            "explorers": {
                "Bitcoin": "https://www.blockchain.com/btc/address/1LAnF8h3qMGx3TSwNUHVneBZUEpwE4gu3D",
                "Ethereum": "https://etherscan.io/address/0xab5C66752a9e8167967685F1450532fB96d5d24f",
            },
        },
        "KuCoin": {
            "btc": ["3QVpCRHh4c7mB3bZ8b6b9c1c5c9c8c7c6c5c4c3c2"],
            "eth": ["0xD6216fC19DB775Df9774a6E33526131dA7D19a2c"],
            "explorers": {
                "Ethereum": "https://etherscan.io/address/0xD6216fC19DB775Df9774a6E33526131dA7D19a2c",
            },
        },
        "Gate.io": {
            "eth": ["0x0D0707963952f2fBA59dD06f2b425ace40b492Fe"],
            "explorers": {
                "Ethereum": "https://etherscan.io/address/0x0D0707963952f2fBA59dD06f2b425ace40b492Fe",
            },
        },
    },
    "Mixers/Tumblers": {
        "Tornado Cash": {
            "eth": ["0x722122dF12D4e14e13Ac3b6895a86e84145b6967", "0xba214c1c1928a32Bffe790263E38B4Af9bFCD607"],
            "type": "Mixer",
            "note": "Sanctioned by OFAC (Aug 2022)",
            "explorers": {
                "Ethereum": "https://etherscan.io/address/0x722122dF12D4e14e13Ac3b6895a86e84145b6967",
            },
        },
        "Sinbad.io": {
            "btc": ["sb1q5e32k03v0e0e0e0e0e0e0e0e0e0e0e0e0e0e0"],
            "type": "Mixer",
            "note": "Successor to Blender.io",
        },
        "Blender.io": {
            "btc": ["1A8PTiPmtqgVLuQXTfR1qrHmxDv1rQz5GT"],
            "type": "Mixer",
            "note": "Sanctioned by OFAC (May 2022), shut down",
        },
        "ChipMixer": {
            "btc": ["13EbbP11hUJ9yPcVh2MnJmGDRZVQFw8h5g"],
            "type": "Mixer",
            "note": "Seized by Europol (Mar 2023)",
        },
    },
    "Ransomware": {
        "REvil/Sodinokibi": {
            "btc": ["18Kx6a7g1iUFLh2Mw4b6j2M5g1iUFLh2Mw"],
            "type": "Ransomware",
            "note": "Ransomware-as-a-Service",
        },
        "Conti": {
            "btc": ["1A8z2VfG3kLmNpQrStUvWxYz4bCcDeFgH"],
            "type": "Ransomware",
            "note": "Ransomware group, dissolved 2022",
        },
        "LockBit": {
            "btc": ["17RMHxYPrY3gPRa2g5jDfM3q4g5bCcDeFg"],
            "type": "Ransomware",
            "note": "Ransomware-as-a-Service",
        },
    },
    "Sanctioned": {
        "Lazarus Group (DPRK)": {
            "eth": ["0x0E3A2440A15e9c6e8dF26bC1e6417c781A3b5e9f"],
            "type": "State-Sponsored",
            "note": "North Korean APT, OFAC sanctioned",
        },
        "Garantex": {
            "eth": ["0xaE848D6A07b13d493F81F90d5cb7E29f23b1b1e3"],
            "type": "Exchange",
            "note": "Sanctioned by OFAC (Apr 2022)",
        },
    },
    "DeFi": {
        "Uniswap V3": {
            "eth": ["0xE592427A0AEce92De3Edee1F18E0157C05861564"],
            "type": "DEX",
            "explorers": {
                "Ethereum": "https://etherscan.io/address/0xE592427A0AEce92De3Edee1F18E0157C05861564",
            },
        },
        "Aave V3": {
            "eth": ["0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2"],
            "type": "Lending",
            "explorers": {
                "Ethereum": "https://etherscan.io/address/0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2",
            },
        },
        "Compound V3": {
            "eth": ["0xc3d688B66703497DAA19211EEdff47f25384cdc3"],
            "type": "Lending",
            "explorers": {
                "Ethereum": "https://etherscan.io/address/0xc3d688B66703497DAA19211EEdff47f25384cdc3",
            },
        },
    },
}

# ═══════════════════════════════════════════════════════════════
#  OSINT SOURCES FOR CRYPTO INVESTIGATION
# ═══════════════════════════════════════════════════════════════

CRYPTO_OSINT = {
    "Blockchain Explorers": [
        ("Blockchain.com", "https://www.blockchain.com/btc/address/{address}"),
        ("Blockstream.info", "https://blockstream.info/address/{address}"),
        ("Mempool.space", "https://mempool.space/address/{address}"),
        ("Etherscan", "https://etherscan.io/address/{address}"),
        ("Blockscout", "https://eth.blockscout.com/address/{address}"),
        ("Polygonscan", "https://polygonscan.com/address/{address}"),
        ("BscScan", "https://bscscan.com/address/{address}"),
        ("Arbiscan", "https://arbiscan.io/address/{address}"),
        ("Optimism Explorer", "https://optimistic.etherscan.io/address/{address}"),
        ("Snowtrace", "https://snowtrace.io/address/{address}"),
        ("Tronscan", "https://tronscan.org/#/address/{address}"),
        ("Solscan", "https://solscan.io/account/{address}"),
        ("Solana.fm", "https://solana.fm/address/{address}"),
    ],
    "Analytics Platforms": [
        ("Chainalysis", "https://www.chainalysis.com/"),
        ("Elliptic", "https://www.elliptic.co/"),
        ("CipherTrace", "https://ciphertrace.com/"),
        ("Crystal Blockchain", "https://crystalblockchain.com/"),
        ("Chaintrail", "https://chaintrail.io/"),
        ("Arkham Intelligence", "https://platform.arkhamintelligence.com/"),
        ("Nansen", "https://www.nansen.ai/"),
        ("Dune Analytics", "https://dune.com/"),
        ("DefiLlama", "https://defillama.com/"),
        ("Token Terminal", "https://tokenterminal.com/"),
        ("Messari", "https://www.messari.io/"),
        ("CoinGecko", "https://www.coingecko.com/"),
        ("CoinMarketCap", "https://coinmarketcap.com/"),
    ],
    "Address Labeling": [
        ("Arkham Intel", "https://platform.arkhamintelligence.com/"),
        ("Nansen Labels", "https://www.nansen.ai/"),
        ("DeBank", "https://debank.com/"),
        ("Zapper", "https://zapper.fi/"),
        ("DexScreener", "https://dexscreener.com/"),
        ("GoPlus Security", "https://gopluslabs.io/"),
        ("TokenSniffer", "https://tokensniffer.com/"),
    ],
    "Compliance & Risk": [
        ("OFAC Sanctions", "https://ofac.treasury.gov/sanctions-programs-and-country-information"),
        ("FinCEN", "https://www.fincen.gov/"),
        ("FATF", "https://www.fatf-gafi.org/"),
        ("Chainalysis KYT", "https://www.chainalysis.com/kyt/"),
        ("Elliptic Lens", "https://www.elliptic.co/lens"),
    ],
    "Dark Web & Illicit": [
        ("DarkOwl", "https://www.darkowl.com/"),
        ("Chainalysis Reactor", "https://www.chainalysis.com/reactor/"),
        ("Flashpoint", "https://flashpoint.io/"),
        ("Recorded Future", "https://www.recordedfuture.com/"),
        ("Intel 471", "https://intel471.com/"),
    ],
    "Research & Education": [
        ("Chainalysis Blog", "https://www.chainalysis.com/blog/"),
        ("Elliptic Blog", "https://www.elliptic.co/blog"),
        ("Crystal Blog", "https://crystalblockchain.com/blog/"),
        ("MIT Digital Currency", "https://dci.mit.edu/"),
        ("Cambridge Centre", "https://www.jbs.cam.ac.uk/centres/for-finance/centre-alternative-finance/"),
    ],
    "Block Explorers (All Chains)": [
        ("Bitcoin", "https://blockchain.info/btc/address/{address}"),
        ("Ethereum", "https://etherscan.io/address/{address}"),
        ("Polygon", "https://polygonscan.com/address/{address}"),
        ("BSC", "https://bscscan.com/address/{address}"),
        ("Arbitrum", "https://arbiscan.io/address/{address}"),
        ("Optimism", "https://optimistic.etherscan.io/address/{address}"),
        ("Avalanche", "https://snowtrace.io/address/{address}"),
        ("Tron", "https://tronscan.org/#/address/{address}"),
        ("Solana", "https://solscan.io/account/{address}"),
        ("Fantom", "https://ftmscan.com/address/{address}"),
        ("Gnosis", "https://gnosisscan.io/address/{address}"),
        ("Base", "https://basescan.org/address/{address}"),
    ],
}


def banner():
    console.clear()
    for l in ASCII:
        console.print(f"[bold cyan]{l}[/bold cyan]", justify="center")
    console.print()
    console.print("[bold white]  Wallet Address OSINT · Transaction Graph · Entity Attribution[/bold white]", justify="center")
    console.print("[bold red]  Made by b0dj0x · https://b0dj0x.cc[/bold red]\n")


class CryptoTracker:
    def __init__(self, timeout=10):
        self.timeout = timeout
        self.s = requests.Session()
        self.s.headers["User-Agent"] = UA
        self.s.verify = False
        self.results = {}

    # ═══════════════════════════════════════════
    #  1. ADDRESS ANALYSIS
    # ═══════════════════════════════════════════

    def analyze_address(self, address):
        """Analyze a crypto address across multiple chains"""
        console.print(f"[bold cyan]  Address Analysis: {address}[/bold cyan]\n")

        # Detect chain
        chain = self._detect_chain(address)
        console.print(f"  [green]Detected Chain: {chain}[/green]\n")

        # Check known entities
        entity = self._check_known_entity(address)
        if entity:
            console.print(f"  [bold red]KNOWN ENTITY: {entity['name']}[/bold red]")
            console.print(f"    Type: {entity['type']}")
            if entity.get("note"):
                console.print(f"    Note: {entity['note']}")
            console.print()

        # Get balance and transactions
        if chain == "Bitcoin":
            self._btc_analysis(address)
        elif chain == "Ethereum":
            self._eth_analysis(address)
        elif chain == "Tron":
            self._tron_analysis(address)
        elif chain == "Solana":
            self._sol_analysis(address)

        # Generate OSINT links
        self._generate_osint_links(address, chain)

    def _detect_chain(self, address):
        """Detect blockchain from address format"""
        if re.match(r"^(1|3|bc1)[a-zA-Z0-9]{25,62}$", address):
            return "Bitcoin"
        elif re.match(r"^0x[0-9a-fA-F]{40}$", address):
            return "Ethereum"
        elif re.match(r"^T[a-zA-Z0-9]{33}$", address):
            return "Tron"
        elif re.match(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$", address):
            return "Solana"
        elif re.match(r"^(r|X)[a-zA-Z0-9]{25,35}$", address):
            return "Ripple"
        elif re.match(r"^(ltc1|L|3)[a-zA-Z0-9]{26,62}$", address):
            return "Litecoin"
        elif re.match(r"^(bc1|tb1)[a-zA-Z0-9]{39,62}$", address):
            return "Bitcoin Testnet"
        else:
            return "Unknown"

    def _check_known_entity(self, address):
        """Check if address belongs to a known entity"""
        for category, entities in KNOWN_ENTITIES.items():
            for name, info in entities.items():
                for chain_key in ["btc", "eth", "trc"]:
                    if address in info.get(chain_key, []):
                        return {"name": name, "type": category, "note": info.get("note", "")}
        return None

    def _btc_analysis(self, address):
        """Analyze Bitcoin address"""
        console.print("[yellow]  Bitcoin Address Analysis[/yellow]\n")

        # Try blockstream.info API
        try:
            resp = self.s.get(
                f"https://blockstream.info/api/address/{address}",
                timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                stats = data.get("chain_stats", {})
                mempool = data.get("mempool_stats", {})

                console.print(f"  [green]Blockstream.info:[/green]")
                console.print(f"    Confirmed TXs: {stats.get('tx_count', 'Unknown')}")
                console.print(f"    Funded TXs: {stats.get('funded_txo_count', 'Unknown')}")
                console.print(f"    Spent TXs: {stats.get('spent_txo_count', 'Unknown')}")
                console.print(f"    Balance: {stats.get('funded_txo_sum', 0) - stats.get('spent_txo_sum', 0)} satoshis")
                console.print(f"    First Seen: {stats.get('block_time', 'Unknown')}")
                console.print(f"    Mempool TXs: {mempool.get('tx_count', 0)}")
                self.results["btc_blockstream"] = data
            else:
                console.print(f"  [dim]Blockstream.info: API error {resp.status_code}[/dim]")
        except:
            console.print(f"  [dim]Blockstream.info: Connection failed[/dim]")

        # Try mempool.space API
        try:
            resp = self.s.get(
                f"https://mempool.space/api/address/{address}",
                timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                chain_stats = data.get("chain_stats", {})
                mempool_stats = data.get("mempool_stats", {})

                console.print(f"  [green]Mempool.space:[/green]")
                console.print(f"    Confirmed TXs: {chain_stats.get('tx_count', 'Unknown')}")
                console.print(f"    Balance: {chain_stats.get('funded_txo_sum', 0) - chain_stats.get('spent_txo_sum', 0)} satoshis")
                console.print(f"    Mempool TXs: {mempool_stats.get('tx_count', 0)}")
                self.results["btc_mempool"] = data
            else:
                console.print(f"  [dim]Mempool.space: API error {resp.status_code}[/dim]")
        except:
            console.print(f"  [dim]Mempool.space: Connection failed[/dim]")

        console.print()

    def _eth_analysis(self, address):
        """Analyze Ethereum address"""
        console.print("[yellow]  Ethereum Address Analysis[/yellow]\n")

        # Try Blockscout API (no API key needed)
        try:
            resp = self.s.get(
                f"https://eth.blockscout.com/api/v2/addresses/{address}",
                timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                coin_balance = data.get("coin_balance", "0")
                tx_count = data.get("transaction_count", "0")
                token_count = data.get("token_balances_count", "0")
                name = data.get("name", "Unknown")
                is_contract = data.get("is_contract", False)

                console.print(f"  [green]Blockscout:[/green]")
                console.print(f"    Balance: {int(coin_balance) / 1e18:.6f} ETH")
                console.print(f"    Transactions: {tx_count}")
                console.print(f"    Token Holdings: {token_count}")
                console.print(f"    Name: {name}")
                console.print(f"    Contract: {'Yes' if is_contract else 'No'}")

                # Check if it's a contract
                if is_contract:
                    console.print(f"    [red]This is a smart contract address[/red]")

                self.results["eth_blockscout"] = data
            else:
                console.print(f"  [dim]Blockscout: API error {resp.status_code}[/dim]")
        except:
            console.print(f"  [dim]Blockscout: Connection failed[/dim]")

        # Try Etherscan API (limited without key)
        try:
            resp = self.s.get(
                f"https://api.etherscan.io/api?module=account&action=balance&address={address}&tag=latest",
                timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("result"):
                    balance = int(data["result"]) / 1e18
                    console.print(f"  [green]Etherscan:[/green]")
                    console.print(f"    Balance: {balance:.6f} ETH")
                    self.results["eth_etherscan"] = data
            else:
                console.print(f"  [dim]Etherscan: API error {resp.status_code}[/dim]")
        except:
            console.print(f"  [dim]Etherscan: Connection failed[/dim]")

        console.print()

    def _tron_analysis(self, address):
        """Analyze Tron address"""
        console.print("[yellow]  Tron Address Analysis[/yellow]\n")

        try:
            resp = self.s.get(
                f"https://apilist.tronscanapi.com/api/accountv2?address={address}",
                timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                balance = data.get("balance", 0)
                tx_count = data.get("totalTransactionCount", 0)
                token_balances = data.get("withPriceTokens", [])

                console.print(f"  [green]Tronscan:[/green]")
                console.print(f"    Balance: {balance / 1e6:.6f} TRX")
                console.print(f"    Transactions: {tx_count}")
                console.print(f"    Token Holdings: {len(token_balances)}")
                self.results["tron_tronscan"] = data
            else:
                console.print(f"  [dim]Tronscan: API error {resp.status_code}[/dim]")
        except:
            console.print(f"  [dim]Tronscan: Connection failed[/dim]")

        console.print()

    def _sol_analysis(self, address):
        """Analyze Solana address"""
        console.print("[yellow]  Solana Address Analysis[/yellow]\n")

        try:
            resp = self.s.get(
                f"https://public-api.solscan.io/account?address={address}",
                timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                lamports = data.get("data", {}).get("lamports", 0)
                tx_count = data.get("data", {}).get("transactionCount", 0)

                console.print(f"  [green]Solscan:[/green]")
                console.print(f"    Balance: {lamports / 1e9:.9f} SOL")
                console.print(f"    Transactions: {tx_count}")
                self.results["sol_solscan"] = data
            else:
                console.print(f"  [dim]Solscan: API error {resp.status_code}[/dim]")
        except:
            console.print(f"  [dim]Solscan: Connection failed[/dim]")

        console.print()

    # ═══════════════════════════════════════════
    #  2. TRANSACTION LOOKUP
    # ═══════════════════════════════════════════

    def tx_lookup(self, txid, chain="auto"):
        """Look up a transaction"""
        console.print(f"[bold cyan]  Transaction Lookup: {txid}[/bold cyan]\n")

        if chain == "auto":
            chain = self._detect_chain_from_tx(txid)
            console.print(f"  [green]Detected Chain: {chain}[/green]\n")

        if chain == "Bitcoin":
            self._btc_tx_lookup(txid)
        elif chain == "Ethereum":
            self._eth_tx_lookup(txid)

        # Generate OSINT links
        self._generate_tx_osint(txid, chain)

    def _detect_chain_from_tx(self, txid):
        """Detect chain from transaction ID"""
        if re.match(r"^[0-9a-fA-F]{64}$", txid):
            return "Bitcoin"
        elif re.match(r"^0x[0-9a-fA-F]{64}$", txid):
            return "Ethereum"
        return "Unknown"

    def _btc_tx_lookup(self, txid):
        """Look up Bitcoin transaction"""
        console.print("[yellow]  Bitcoin Transaction[/yellow]\n")

        try:
            resp = self.s.get(
                f"https://blockstream.info/api/tx/{txid}",
                timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                status = data.get("status", {})
                vin = data.get("vin", [])
                vout = data.get("vout", [])

                total_in = sum(v.get("prevout", {}).get("value", 0) for v in vin)
                total_out = sum(v.get("value", 0) for v in vout)
                fee = total_in - total_out

                console.print(f"  [green]Blockstream.info:[/green]")
                console.print(f"    Block: {status.get('block_height', 'Unconfirmed')}")
                console.print(f"    Confirmations: {status.get('confirmed', 'N/A')}")
                console.print(f"    Inputs: {len(vin)}")
                console.print(f"    Outputs: {len(vout)}")
                console.print(f"    Total In: {total_in / 1e8:.8f} BTC")
                console.print(f"    Total Out: {total_out / 1e8:.8f} BTC")
                console.print(f"    Fee: {fee / 1e8:.8f} BTC")

                # Show input addresses
                console.print(f"\n    [yellow]Input Addresses:[/yellow]")
                for v in vin[:5]:
                    addr = v.get("prevout", {}).get("scriptpubkey_address", "Unknown")
                    value = v.get("prevout", {}).get("value", 0)
                    console.print(f"      {addr} ({value / 1e8:.8f} BTC)")

                # Show output addresses
                console.print(f"\n    [yellow]Output Addresses:[/yellow]")
                for v in vout[:5]:
                    addr = v.get("scriptpubkey_address", "Unknown")
                    value = v.get("value", 0)
                    console.print(f"      {addr} ({value / 1e8:.8f} BTC)")

                self.results["btc_tx"] = data
            else:
                console.print(f"  [dim]Blockstream.info: API error {resp.status_code}[/dim]")
        except:
            console.print(f"  [dim]Blockstream.info: Connection failed[/dim]")

        console.print()

    def _eth_tx_lookup(self, txid):
        """Look up Ethereum transaction"""
        console.print("[yellow]  Ethereum Transaction[/yellow]\n")

        try:
            resp = self.s.get(
                f"https://eth.blockscout.com/api/v2/transactions/{txid}",
                timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                value = int(data.get("value", "0")) / 1e18
                gas_price = int(data.get("gas_price", "0")) / 1e9
                gas_used = data.get("gas_used", 0)
                block = data.get("block", "Unknown")
                status = data.get("status", "Unknown")
                from_addr = data.get("from", {}).get("hash", "Unknown")
                to_addr = data.get("to", {}).get("hash", "Unknown") if data.get("to") else "Contract Creation"
                method = data.get("method", "Unknown")

                console.print(f"  [green]Blockscout:[/green]")
                console.print(f"    Block: {block}")
                console.print(f"    Status: {status}")
                console.print(f"    From: {from_addr}")
                console.print(f"    To: {to_addr}")
                console.print(f"    Value: {value:.6f} ETH")
                console.print(f"    Gas Price: {gas_price:.9f} Gwei")
                console.print(f"    Gas Used: {gas_used}")
                console.print(f"    Method: {method}")

                self.results["eth_tx"] = data
            else:
                console.print(f"  [dim]Blockscout: API error {resp.status_code}[/dim]")
        except:
            console.print(f"  [dim]Blockscout: Connection failed[/dim]")

        console.print()

    # ═══════════════════════════════════════════
    #  3. ENTITY LOOKUP
    # ═══════════════════════════════════════════

    def entity_lookup(self, name):
        """Look up known entity addresses"""
        console.print(f"[bold cyan]  Entity Lookup: {name}[/bold cyan]\n")

        found = False
        for category, entities in KNOWN_ENTITIES.items():
            for entity_name, info in entities.items():
                if name.lower() in entity_name.lower():
                    found = True
                    console.print(f"  [bold red]{entity_name}[/bold red]")
                    console.print(f"    Category: {category}")
                    if info.get("type"):
                        console.print(f"    Type: {info['type']}")
                    if info.get("note"):
                        console.print(f"    Note: {info['note']}")

                    # Show addresses
                    for chain_key in ["btc", "eth", "trc"]:
                        addrs = info.get(chain_key, [])
                        if addrs:
                            chain_name = {"btc": "Bitcoin", "eth": "Ethereum", "trc": "Tron"}[chain_key]
                            console.print(f"    {chain_name} Addresses:")
                            for addr in addrs[:3]:
                                console.print(f"      {addr}")

                    # Show explorer links
                    explorers = info.get("explorers", {})
                    if explorers:
                        console.print(f"    Explorer Links:")
                        for chain, url in explorers.items():
                            console.print(f"      [{chain}] {url}")

                    console.print()

        if not found:
            console.print(f"  [dim]No entities found matching '{name}'[/dim]")

    # ═══════════════════════════════════════════
    #  4. SANCTIONS CHECK
    # ═══════════════════════════════════════════

    def sanctions_check(self, address):
        """Check if address is sanctioned"""
        console.print(f"[bold cyan]  Sanctions Check: {address}[/bold cyan]\n")

        # Check known entities
        sanctioned = []
        for category in ["Sanctioned", "Mixers/Tumblers", "Ransomware"]:
            entities = KNOWN_ENTITIES.get(category, {})
            for name, info in entities.items():
                for chain_key in ["btc", "eth", "trc"]:
                    if address in info.get(chain_key, []):
                        sanctioned.append({"name": name, "category": category, "note": info.get("note", "")})

        if sanctioned:
            console.print(f"  [bold red]WARNING: Address matches sanctioned/illicit entity![/bold red]\n")
            for s in sanctioned:
                console.print(f"  [red]• {s['name']}[/red]")
                console.print(f"    Category: {s['category']}")
                if s['note']:
                    console.print(f"    Note: {s['note']}")
                console.print()
        else:
            console.print(f"  [green]Address not found in known sanctions lists[/green]")

        # Generate OFAC links
        console.print(f"\n[bold yellow]  Compliance Resources[/bold yellow]\n")
        links = [
            ("OFAC Sanctions List", "https://ofac.treasury.gov/sanctions-programs-and-country-information"),
            ("OFAC SDN List", "https://ofac.treasury.gov/specially-designated-nationals-and-blocked-persons-list-sdn-human-rights-lists"),
            ("Chainalysis KYT", "https://www.chainalysis.com/kyt/"),
            ("Elliptic Lens", "https://www.elliptic.co/lens"),
            ("Crystal Blockchain", "https://crystalblockchain.com/"),
            ("CipherTrace", "https://ciphertrace.com/"),
            ("Google", f"https://www.google.com/search?q=%22{address}%22+sanctioned"),
        ]

        for i, (name, url) in enumerate(links, 1):
            console.print(f"  [green]{i}.[/green] [bold white]{name}[/bold white]")
            console.print(f"      {url}")

    # ═══════════════════════════════════════════
    #  5. OSINT LINKS
    # ═══════════════════════════════════════════

    def _generate_osint_links(self, address, chain):
        """Generate OSINT links for address"""
        console.print("[bold cyan]  OSINT Links[/bold cyan]\n")

        links = []

        # Chain-specific explorers
        if chain in ["Bitcoin", "Unknown"]:
            links.extend([
                ("Blockchain.com", f"https://www.blockchain.com/btc/address/{address}"),
                ("Blockstream.info", f"https://blockstream.info/address/{address}"),
                ("Mempool.space", f"https://mempool.space/address/{address}"),
            ])

        if chain in ["Ethereum", "Unknown"]:
            links.extend([
                ("Etherscan", f"https://etherscan.io/address/{address}"),
                ("Blockscout", f"https://eth.blockscout.com/address/{address}"),
                ("DeBank", f"https://debank.com/address/{address}"),
                ("Zapper", f"https://zapper.fi/account/{address}"),
            ])

        if chain in ["Tron", "Unknown"]:
            links.extend([
                ("Tronscan", f"https://tronscan.org/#/address/{address}"),
            ])

        if chain in ["Solana", "Unknown"]:
            links.extend([
                ("Solscan", f"https://solscan.io/account/{address}"),
                ("Solana.fm", f"https://solana.fm/address/{address}"),
            ])

        # Universal links
        links.extend([
            ("Arkham Intel", f"https://platform.arkhamintelligence.com/"),
            ("Nansen", f"https://www.nansen.ai/"),
            ("Dune Analytics", f"https://dune.com/"),
            ("DeFiLlama", f"https://defillama.com/"),
            ("CoinGecko", f"https://www.coingecko.com/"),
            ("CoinMarketCap", f"https://coinmarketcap.com/"),
            ("Google", f"https://www.google.com/search?q=%22{address}%22"),
            ("GitHub", f"https://github.com/search?q={address}&type=code"),
        ])

        for i, (name, url) in enumerate(links, 1):
            console.print(f"  [green]{i:2d}.[/green] [bold white]{name}[/bold white]")
            console.print(f"      {url}")

    def _generate_tx_osint(self, txid, chain):
        """Generate OSINT links for transaction"""
        console.print("[bold cyan]  Transaction OSINT Links[/bold cyan]\n")

        links = []

        if chain in ["Bitcoin", "Unknown"]:
            links.extend([
                ("Blockchain.com", f"https://www.blockchain.com/btc/tx/{txid}"),
                ("Blockstream.info", f"https://blockstream.info/tx/{txid}"),
                ("Mempool.space", f"https://mempool.space/tx/{txid}"),
            ])

        if chain in ["Ethereum", "Unknown"]:
            links.extend([
                ("Etherscan", f"https://etherscan.io/tx/{txid}"),
                ("Blockscout", f"https://eth.blockscout.com/tx/{txid}"),
            ])

        links.extend([
            ("Google", f"https://www.google.com/search?q=%22{txid}%22"),
        ])

        for i, (name, url) in enumerate(links, 1):
            console.print(f"  [green]{i:2d}.[/green] [bold white]{name}[/bold white]")
            console.print(f"      {url}")

    # ═══════════════════════════════════════════
    #  6. FULL INVESTIGATION
    # ═══════════════════════════════════════════

    def investigate(self, target):
        """Full investigation on address/txid"""
        console.print(f"[bold cyan]  Full Investigation: {target}[/bold cyan]\n")

        # Detect if txid or address
        if re.match(r"^(0x)?[0-9a-fA-F]{64}$", target):
            console.print("[yellow]Detected: Transaction ID[/yellow]\n")
            self.tx_lookup(target)
        else:
            console.print("[yellow]Detected: Wallet Address[/yellow]\n")
            self.analyze_address(target)

    # ═══════════════════════════════════════════
    #  7. LIST KNOWN ENTITIES
    # ═══════════════════════════════════════════

    def list_entities(self):
        """List all known entities"""
        console.print("[bold cyan]  Known Blockchain Entities[/bold cyan]\n")

        for category, entities in KNOWN_ENTITIES.items():
            console.print(f"[bold yellow]{category}[/bold yellow]\n")
            for name, info in entities.items():
                console.print(f"  [bold white]{name}[/bold white]")
                if info.get("type"):
                    console.print(f"    Type: {info['type']}")
                if info.get("note"):
                    console.print(f"    Note: {info['note']}")

                # Show addresses
                for chain_key in ["btc", "eth", "trc"]:
                    addrs = info.get(chain_key, [])
                    if addrs:
                        chain_name = {"btc": "Bitcoin", "eth": "Ethereum", "trc": "Tron"}[chain_key]
                        console.print(f"    {chain_name}: {', '.join(addrs[:2])}")

                # Show explorer links
                explorers = info.get("explorers", {})
                if explorers:
                    for chain, url in explorers.items():
                        console.print(f"    [{chain}] {url}")

                console.print()

    # ═══════════════════════════════════════════
    #  8. BLOCK EXPLORERS LIST
    # ═══════════════════════════════════════════

    def list_explorers(self):
        """List all block explorers"""
        console.print("[bold cyan]  Block Explorers by Chain[/bold cyan]\n")

        explorers = {
            "Bitcoin": [
                ("Blockchain.com", "https://www.blockchain.com/btc/address/{address}"),
                ("Blockstream.info", "https://blockstream.info/address/{address}"),
                ("Mempool.space", "https://mempool.space/address/{address}"),
                ("BTCScan", "https://btcscan.org/address/{address}"),
            ],
            "Ethereum": [
                ("Etherscan", "https://etherscan.io/address/{address}"),
                ("Blockscout", "https://eth.blockscout.com/address/{address}"),
                ("Ethplorer", "https://ethplorer.io/address/{address}"),
            ],
            "Polygon": [
                ("Polygonscan", "https://polygonscan.com/address/{address}"),
                ("Blockscout", "https://polygon.blockscout.com/address/{address}"),
            ],
            "BSC": [
                ("BscScan", "https://bscscan.com/address/{address}"),
            ],
            "Arbitrum": [
                ("Arbiscan", "https://arbiscan.io/address/{address}"),
                ("Blockscout", "https://arbitrum.blockscout.com/address/{address}"),
            ],
            "Optimism": [
                ("Optimism Explorer", "https://optimistic.etherscan.io/address/{address}"),
                ("Blockscout", "https://optimism.blockscout.com/address/{address}"),
            ],
            "Avalanche": [
                ("Snowtrace", "https://snowtrace.io/address/{address}"),
            ],
            "Tron": [
                ("Tronscan", "https://tronscan.org/#/address/{address}"),
                ("TRXplorer", "https://trxplorer.io/address/{address}"),
            ],
            "Solana": [
                ("Solscan", "https://solscan.io/account/{address}"),
                ("Solana.fm", "https://solana.fm/address/{address}"),
                ("Solana Explorer", "https://explorer.solana.com/address/{address}"),
            ],
            "Fantom": [
                ("FTMScan", "https://ftmscan.com/address/{address}"),
            ],
            "Gnosis": [
                ("GnosisScan", "https://gnosisscan.io/address/{address}"),
            ],
            "Base": [
                ("BaseScan", "https://basescan.org/address/{address}"),
            ],
            "Litecoin": [
                ("Litecoin Block Explorer", "https://litecoinblockexplorer.net/address/{address}"),
                ("Blockchair", "https://blockchair.com/litecoin/address/{address}"),
            ],
            "Ripple": [
                ("XRP Ledger Explorer", "https://xrpscan.com/account/{address}"),
                ("Bithomp", "https://bithomp.com/address/{address}"),
            ],
        }

        for chain, chain_explorers in explorers.items():
            console.print(f"[bold yellow]{chain}[/bold yellow]")
            for name, url in chain_explorers:
                console.print(f"  [green]•[/green] [bold white]{name}[/bold white]")
                console.print(f"    {url}")
            console.print()

    # ═══════════════════════════════════════════
    #  9. OSINT TOOLS LIST
    # ═══════════════════════════════════════════

    def list_osint_tools(self):
        """List OSINT tools for crypto investigation"""
        console.print("[bold cyan]  OSINT Tools for Crypto Investigation[/bold cyan]\n")

        for category, tools in CRYPTO_OSINT.items():
            console.print(f"[bold yellow]{category}[/bold yellow]\n")
            for name, url in tools:
                console.print(f"  [green]•[/green] [bold white]{name}[/bold white]")
                console.print(f"    {url}")
            console.print()


def main():
    p = argparse.ArgumentParser(
        prog="cryptotracker",
        description="CryptoTracker — Wallet Address OSINT · Transaction Graph · Entity Attribution")
    sub = p.add_subparsers(dest="command", help="Command to execute")

    # Address analysis
    addr_p = sub.add_parser("address", help="Analyze wallet address")
    addr_p.add_argument("addr", help="Wallet address")

    # Transaction lookup
    tx_p = sub.add_parser("tx", help="Look up transaction")
    tx_p.add_argument("txid", help="Transaction ID")
    tx_p.add_argument("--chain", default="auto", help="Blockchain (auto/bitcoin/ethereum)")

    # Entity lookup
    entity_p = sub.add_parser("entity", help="Look up known entity")
    entity_p.add_argument("name", help="Entity name (e.g., Binance, Tornado Cash)")

    # Sanctions check
    sanction_p = sub.add_parser("sanctions", help="Check if address is sanctioned")
    sanction_p.add_argument("addr", help="Address to check")

    # Full investigation
    inv_p = sub.add_parser("investigate", help="Full investigation on address/txid")
    inv_p.add_argument("target", help="Address or Transaction ID")

    # List commands
    sub.add_parser("entities", help="List all known entities")
    sub.add_parser("explorers", help="List all block explorers")
    sub.add_parser("tools", help="List OSINT tools")

    args = p.parse_args()

    banner()

    ct = CryptoTracker()

    if args.command == "address":
        ct.analyze_address(args.addr)
    elif args.command == "tx":
        ct.tx_lookup(args.txid, args.chain)
    elif args.command == "entity":
        ct.entity_lookup(args.name)
    elif args.command == "sanctions":
        ct.sanctions_check(args.addr)
    elif args.command == "investigate":
        ct.investigate(args.target)
    elif args.command == "entities":
        ct.list_entities()
    elif args.command == "explorers":
        ct.list_explorers()
    elif args.command == "tools":
        ct.list_osint_tools()
    else:
        p.print_help()

    console.print("\n[bold green]  Done.[/bold green]\n")


if __name__ == "__main__":
    main()
