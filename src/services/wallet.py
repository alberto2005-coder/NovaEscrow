import os
import asyncio
import aiohttp
import time
from web3 import Web3
from eth_account import Account
from bitcoinlib.keys import Key 
from bitcoinlib.wallets import Wallet
import base58
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from cryptography.fernet import Fernet
import hashlib
import secrets

# Importación para Solana (SOL)
from solana.rpc.async_api import AsyncClient
from solana.system_program import transfer, TransferParams
from solders.transaction import Transaction
from solders.instruction import Instruction


# Contratos de Tokens ERC-20
USDT_CONTRACT = '0xdac17f958d2ee523a2206206994597c13d831ec7'
USDC_CONTRACT = '0xa0b86991c6218b3cf5ba990597d90c99026a27aa'

class CryptoWalletManager:
    def __init__(self):
        self.infura_url = os.getenv("INFURA_URL", "https://mainnet.infura.io/v3/YOUR_PROJECT_ID")
        self.solana_rpc = os.getenv("SOLANA_RPC", "https://api.mainnet-beta.solana.com")
        self.blockcypher_token = os.getenv("BLOCKCYPHER_TOKEN", "")
        self.master_key = os.getenv("WALLET_MASTER_KEY", Fernet.generate_key().decode())
        
    def generate_wallet_address(self, currency: str, channel_id: int) -> dict:
        seed = f"{self.master_key}_{currency}_{channel_id}_{secrets.token_hex(16)}"
        seed_hash = hashlib.sha256(seed.encode()).digest()
        
        if currency == "BTC":
            return self._generate_btc_address(seed_hash)
        elif currency in ["ETH", "USDT", "USDC"]:
            return self._generate_eth_address(seed_hash)
        elif currency == "SOL":
            return self._generate_sol_address(seed_hash)
        elif currency == "LTC":
            return self._generate_ltc_address(seed_hash)
        else:
            raise ValueError("Moneda no soportada")

    def _generate_btc_address(self, seed_hash: bytes) -> dict:
        k = Key(hash=seed_hash)
        return {
            "address": k.address(),
            "private_key": k.wif(),
            "public_key": k.pub().hex(),
        }

    def _generate_ltc_address(self, seed_hash: bytes) -> dict:
        k = Key(hash=seed_hash)
        return {
            "address": k.address(network='litecoin'),
            "private_key": k.wif(network='litecoin'),
            "public_key": k.pub().hex(),
        }
    
    def _generate_eth_address(self, seed_hash: bytes) -> dict:
        Account.enable_unaudited_hdwallet_features()
        acct = Account.from_key(seed_hash)
        return {
            "address": acct.address,
            "private_key": acct.key.hex(),
            "public_key": ""
        }

    def _generate_sol_address(self, seed_hash: bytes) -> dict:
        keypair = Keypair.from_seed(seed_hash[:32])
        return {
            "address": str(keypair.pubkey()),
            "private_key": base58.b58encode(bytes(keypair)).decode('ascii'),
            "public_key": str(keypair.pubkey())
        }
    
    def encrypt_private_key(self, private_key: str) -> str:
        f = Fernet(self.master_key.encode())
        return f.encrypt(private_key.encode()).decode()

    def decrypt_private_key(self, encrypted_key: str) -> str:
        f = Fernet(self.master_key.encode())
        return f.decrypt(encrypted_key.encode()).decode()

    async def send_funds(self, from_wallet: dict, to_address: str, amount: float, currency: str) -> str:
        if currency == "BTC":
            return await self._send_btc(from_wallet, to_address, amount)
        elif currency == "LTC":
            return await self._send_ltc(from_wallet, to_address, amount)
        elif currency == "SOL":
            return await self._send_sol(from_wallet, to_address, amount)
        elif currency in ["ETH", "USDT", "USDC"]:
            return await self._send_eth_erc20(from_wallet, to_address, amount, currency)
        else:
            raise ValueError(f"Envío para {currency} no soportado")

    async def _send_btc(self, from_wallet: dict, to_address: str, amount: float) -> str:
        
        def sync_send_btc():
            wallet_name = f'temp_btc_{os.getpid()}_{secrets.token_hex(4)}'
            w = None 
            tx_id = ""
            MAX_RETRIES = 3
            WAIT_SECONDS = 5
            
            try:
                w = Wallet.create(wallet_name, keys=from_wallet['private_key'], network='bitcoin')
                
                for attempt in range(MAX_RETRIES):
                    try:
                        w.scan()
                        if w.unspent():
                            break
                        elif attempt < MAX_RETRIES - 1:
                            time.sleep(WAIT_SECONDS)
                        else:
                            raise Exception("BTC: No se encontraron UTXOs después de múltiples intentos de escaneo.")
                    except Exception as scan_e:
                        if attempt < MAX_RETRIES - 1:
                            time.sleep(WAIT_SECONDS)
                        else:
                            raise Exception(f"Fallo al escanear UTXOs para BTC. Último error: {scan_e}")

                amount_satoshis = int(amount * 100000000)
                tx = w.send_to(to_address, amount_satoshis, fee='normal')
                if tx:
                    tx_id = tx.txid
            except Exception as e:
                print(f"Error en el thread síncrono para BTC: {e}")
                raise e
            finally:
                if w:
                    try:
                        w.session.close()
                        w.delete()
                    except Exception as cleanup_e:
                        print(f"Advertencia: Error durante la limpieza de la BTC wallet: {cleanup_e}") 
            return tx_id

        try:
            tx_hash = await asyncio.to_thread(sync_send_btc)
            return tx_hash
        except Exception as e:
            print(f"Error sending BTC: {e}")
            return ""

    async def _send_ltc(self, from_wallet: dict, to_address: str, amount: float) -> str:
        
        def sync_send_ltc():
            wallet_name = f'temp_ltc_{os.getpid()}_{secrets.token_hex(4)}'
            w = None 
            tx_id = ""
            MAX_RETRIES = 3
            WAIT_SECONDS = 5
            
            try:
                w = Wallet.create(wallet_name, keys=from_wallet['private_key'], network='litecoin')
                
                for attempt in range(MAX_RETRIES):
                    try:
                        w.scan()
                        if w.unspent():
                            print(f"LTC Scan exitoso en intento {attempt + 1}. UTXOs encontrados.")
                            break
                        elif attempt < MAX_RETRIES - 1:
                            print(f"LTC Scan fallido en intento {attempt + 1}. Esperando {WAIT_SECONDS}s...")
                            time.sleep(WAIT_SECONDS)
                        else:
                            raise Exception("LTC: No se encontraron UTXOs después de múltiples intentos de escaneo.")
                    except Exception as scan_e:
                        if attempt < MAX_RETRIES - 1:
                            print(f"LTC Scan error ({scan_e}) en intento {attempt + 1}. Esperando {WAIT_SECONDS}s...")
                            time.sleep(WAIT_SECONDS)
                        else:
                            print(f"LTC Scan fallido después de múltiples intentos. Último error: {scan_e}")
                            raise Exception(f"Fallo al escanear UTXOs para LTC. Último error: {scan_e}")
                
                amount_litoshis = int(amount * 100000000)
                tx = w.send_to(to_address, amount_litoshis, fee='normal')
                
                if tx:
                    tx_id = tx.txid
                
            except Exception as e:
                print(f"Error en el thread síncrono para LTC: {e}")
                raise e
            finally:
                if w:
                    try:
                        w.session.close()
                        w.delete()
                    except Exception as cleanup_e:
                        print(f"Advertencia: Error durante la limpieza de la LTC wallet: {cleanup_e}") 
            
            return tx_id

        try:
            tx_hash = await asyncio.to_thread(sync_send_ltc)
            return tx_hash
        except Exception as e:
            print(f"Error sending LTC: {e}")
            return ""

    async def _send_eth_erc20(self, from_wallet: dict, to_address: str, amount: float, currency: str) -> str:
        
        def sync_send_eth_erc20():
            w3 = Web3(Web3.HTTPProvider(self.infura_url))
            if not w3.is_connected():
                raise ConnectionError("No se pudo conectar a la red Ethereum/Infura")

            private_key = from_wallet['private_key']
            from_address = from_wallet['address']
            
            nonce = w3.eth.get_transaction_count(from_address)
            gas_price = w3.eth.gas_price

            if currency == "ETH":
                tx = {
                    'nonce': nonce,
                    'to': to_address,
                    'value': w3.to_wei(amount, 'ether'),
                    'gas': 21000,
                    'gasPrice': gas_price,
                }
            else:
                contract_address = USDT_CONTRACT if currency == "USDT" else USDC_CONTRACT
                contract = w3.eth.contract(address=w3.to_checksum_address(contract_address), abi=self._get_erc20_abi())
                
                decimals = contract.functions.decimals().call()
                amount_wei = int(amount * (10**decimals))

                tx = contract.functions.transfer(
                    w3.to_checksum_address(to_address),
                    amount_wei
                ).build_transaction({
                    'from': from_address,
                    'nonce': nonce,
                    'gas': 100000, 
                    'gasPrice': gas_price,
                })
            
            signed_tx = w3.eth.account.sign_transaction(tx, private_key)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            return tx_hash.hex()

        try:
            tx_hash = await asyncio.to_thread(sync_send_eth_erc20)
            return tx_hash
        except Exception as e:
            print(f"Error sending {currency}: {e}")
            return ""

    def _get_erc20_abi(self):
        return [
            {
                "constant": True,
                "inputs": [],
                "name": "decimals",
                "outputs": [{"name": "", "type": "uint8"}],
                "type": "function",
            },
            {
                "constant": False,
                "inputs": [
                    {"name": "_to", "type": "address"},
                    {"name": "_value", "type": "uint256"},
                ],
                "name": "transfer",
                "outputs": [{"name": "", "type": "bool"}],
                "type": "function",
            },
        ]
        
    async def _send_sol(self, from_wallet: dict, to_address: str, amount: float) -> str:
        try:
            async with AsyncClient(self.solana_rpc) as client:
                private_key_bytes = base58.b58decode(from_wallet['private_key'])
                keypair = Keypair.from_bytes(private_key_bytes)
                
                from_pubkey = keypair.pubkey()
                to_pubkey = Pubkey.from_string(to_address)
                
                amount_lamports = int(amount * 1000000000)
                
                transfer_ix = transfer(TransferParams(
                    from_pubkey=from_pubkey,
                    to_pubkey=to_pubkey,
                    lamports=amount_lamports
                ))
                
                recent_blockhash = (await client.get_latest_blockhash()).value.blockhash
                
                tx = Transaction.new_with_payer(
                    [transfer_ix],
                    keypair.pubkey()
                )
                tx.recent_blockhash = recent_blockhash
                tx.sign([keypair])
                
                result = await client.send_transaction(tx, keypair)
                return str(result.value)
        except Exception as e:
            print(f"Error sending SOL: {e}")
            return ""

    def validate_address(self, address: str, currency: str) -> bool:
        if not address or not isinstance(address, str):
            return False
        address = address.strip()
        
        try:
            if currency in ["ETH", "USDT", "USDC"]:
                return Web3.is_address(address)
            elif currency == "SOL":
                try:
                    Pubkey.from_string(address)
                    return True
                except ValueError:
                    return False
            elif currency == "BTC":
                if len(address) < 26 or len(address) > 62:
                    return False
                if not address.startswith(('1', '3', 'bc1')):
                    return False
                import re
                if address.startswith(('1', '3')):
                    return bool(re.match(r'^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$', address))
                elif address.startswith('bc1'):
                    return bool(re.match(r'^bc1[ac-hj-np-z02-9]{11,71}$', address))
                return True
            elif currency == "LTC":
                if len(address) < 26 or len(address) > 43:
                    return False
                if not address.startswith(('L', 'M', 'ltc1')):
                    return False
                import re
                if address.startswith(('L', 'M')):
                    return bool(re.match(r'^[LM][a-km-zA-HJ-NP-Z1-9]{26,33}$', address))
                elif address.startswith('ltc1'):
                    return bool(re.match(r'^ltc1[ac-hj-np-z02-9]{11,71}$', address))
                return True
            else:
                return False
        except Exception as e:
            print(f"Error validating address {address} for {currency}: {e}")
            return False

    async def check_balance(self, address: str, currency: str) -> float:
        if not address or not isinstance(address, str):
            return 0.0
        address = address.strip()
        
        if currency == "SOL":
            try:
                async with AsyncClient(self.solana_rpc) as client:
                    pubkey = Pubkey.from_string(address)
                    response = await client.get_balance(pubkey)
                    if response and hasattr(response, 'value'):
                        return response.value / 1000000000.0  # lamports to SOL
                    return 0.0
            except Exception as e:
                print(f"Error checking SOL balance for {address}: {e}")
                return 0.0
                
        elif currency in ["ETH", "USDT", "USDC"]:
            def sync_check_eth_erc20():
                w3 = Web3(Web3.HTTPProvider(self.infura_url))
                if not w3.is_connected():
                    raise ConnectionError("No se pudo conectar a la red Ethereum/Infura")
                
                checksum_address = w3.to_checksum_address(address)
                
                if currency == "ETH":
                    balance_wei = w3.eth.get_balance(checksum_address)
                    return float(w3.from_wei(balance_wei, 'ether'))
                else:
                    contract_address = USDT_CONTRACT if currency == "USDT" else USDC_CONTRACT
                    contract = w3.eth.contract(address=w3.to_checksum_address(contract_address), abi=self._get_erc20_abi())
                    
                    decimals = contract.functions.decimals().call()
                    balance_raw = contract.functions.balanceOf(checksum_address).call()
                    return float(balance_raw / (10 ** decimals))
            
            try:
                balance = await asyncio.to_thread(sync_check_eth_erc20)
                return balance
            except Exception as e:
                print(f"Error checking {currency} balance for {address}: {e}")
                return 0.0
                
        elif currency in ["BTC", "LTC"]:
            coin = "btc" if currency == "BTC" else "ltc"
            url = f"https://api.blockcypher.com/v1/{coin}/main/addrs/{address}/balance"
            if self.blockcypher_token:
                url += f"?token={self.blockcypher_token}"
                
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=10) as response:
                        if response.status == 200:
                            data = await response.json()
                            balance_satoshis = data.get("balance", 0)
                            return float(balance_satoshis / 100000000.0)
                        else:
                            print(f"Error calling BlockCypher: HTTP {response.status}")
                            return 0.0
            except Exception as e:
                print(f"Error checking {currency} balance for {address} via BlockCypher: {e}")
                return 0.0
        
        return 0.0
