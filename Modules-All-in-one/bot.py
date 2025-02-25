from aiohttp import ClientResponseError, ClientSession, ClientTimeout
from aiohttp_socks import ProxyConnector
from colorama import Fore, Style, init
from datetime import datetime, timedelta
from fake_useragent import FakeUserAgent
import asyncio
import json
import os
import pytz
import uuid
import random
import base64
import hashlib
import logging
import time
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from typing import Dict, List, Optional, Tuple, Union, Any
import aiohttp

# Initialize colorama
init(autoreset=True)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("dawn_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("DawnBot")

# Time zone setting
wib = pytz.timezone("Asia/Jakarta")


class TokenEncryption:
    """Class to handle token encryption and decryption"""

    def __init__(self, password_seed: str = "DawnBotSecurity"):
        """Initialize encryption with a password seed"""
        self.password = password_seed.encode()
        self.salt = b'salt_for_dawn_bot'  # In production, this should be stored securely
        self.key = self._generate_key()
        self.cipher_suite = Fernet(self.key)

    def _generate_key(self) -> bytes:
        """Generate encryption key from password"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.salt,
            iterations=100000,
        )
        return base64.urlsafe_b64encode(kdf.derive(self.password))

    def encrypt(self, data: str) -> str:
        """Encrypt a string"""
        return self.cipher_suite.encrypt(data.encode()).decode()

    def decrypt(self, data: str) -> str:
        """Decrypt a string"""
        try:
            return self.cipher_suite.decrypt(data.encode()).decode()
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            return ""


class ProxyManager:
    def __init__(self):
        # Proxy management
        self.proxies: List[str] = []
        self.proxy_stats: Dict[str, Dict[str, Any]] = {}
        self.proxy_display_mapping: Dict[str, str] = {}
        self.proxy_count: int = 0
        self.blacklisted_proxies: List[str] = []

        # Settings
        self.max_failures = 2  # Diubah dari 3
        self.blacklist_duration = 1800  # 30 menit
        self.proxy_rotation_count = 5  # Tambahan untuk rotasi

    def clear_proxy_stats(self):
        """Reset proxy statistics"""
        self.proxy_stats = {}

    def add_proxy(self, proxy: str):
        """Add a proxy to the pool if not already present"""
        if proxy not in self.proxies and proxy not in self.blacklisted_proxies:
            self.proxies.append(proxy)
            self.proxy_stats[proxy] = {
                "success": 0,
                "failure": 0,
                "last_used": 0,
                "blacklisted_until": 0
            }

    def get_proxy_display_name(self, proxy: str) -> str:
        """Get a display name for a proxy"""
        if proxy not in self.proxy_display_mapping:
            self.proxy_count += 1
            self.proxy_display_mapping[proxy] = f"Proxy-{self.proxy_count}"
        return self.proxy_display_mapping[proxy]

    def record_success(self, proxy: str):
        """Record a successful proxy usage"""
        if proxy in self.proxy_stats:
            self.proxy_stats[proxy]["success"] += 1
            self.proxy_stats[proxy]["last_used"] = time.time()

    def record_failure(self, proxy: str):
        """Record a failed proxy usage and potentially blacklist"""
        if proxy in self.proxy_stats:
            self.proxy_stats[proxy]["failure"] += 1
            self.proxy_stats[proxy]["last_used"] = time.time()

            # Check if proxy should be blacklisted
            if self.proxy_stats[proxy]["failure"] >= self.max_failures:
                self.blacklist_proxy(proxy)

    def blacklist_proxy(self, proxy: str):
        """Add a proxy to the blacklist"""
        if proxy in self.proxies:
            self.proxies.remove(proxy)

        if proxy not in self.blacklisted_proxies:
            self.blacklisted_proxies.append(proxy)
            blacklist_until = time.time() + self.blacklist_duration
            self.proxy_stats[proxy]["blacklisted_until"] = blacklist_until
            logger.info(f"Blacklisted {self.get_proxy_display_name(proxy)} for {self.blacklist_duration} seconds")

    def cleanup_blacklist(self):
        """Remove proxies from blacklist if their penalty time has passed"""
        current_time = time.time()
        proxies_to_restore = []

        for proxy in self.blacklisted_proxies:
            if proxy in self.proxy_stats and self.proxy_stats[proxy]["blacklisted_until"] <= current_time:
                proxies_to_restore.append(proxy)

        for proxy in proxies_to_restore:
            self.blacklisted_proxies.remove(proxy)
            self.proxies.append(proxy)
            # Reset failure count
            self.proxy_stats[proxy]["failure"] = 0
            logger.info(f"Restored {self.get_proxy_display_name(proxy)} from blacklist")

    def get_best_proxies(self, count: int) -> List[str]:
        """Get the best performing proxies"""
        if not self.proxies:
            return []

        # Clean up blacklist first
        self.cleanup_blacklist()

        # If we don't have enough proxies, return what we have
        if len(self.proxies) <= count:
            return self.proxies.copy()

        # Calculate a score for each proxy
        proxy_scores = []
        for proxy in self.proxies:
            if proxy in self.proxy_stats:
                stats = self.proxy_stats[proxy]
                success_rate = stats["success"] / (stats["success"] + stats["failure"] + 0.001)
                # Recent proxies are preferred
                recency = 1.0 / (time.time() - stats["last_used"] + 1)
                score = success_rate * 0.7 + recency * 0.3
                proxy_scores.append((proxy, score))

        # Sort by score descending
        proxy_scores.sort(key=lambda x: x[1], reverse=True)

        # Return top N proxies
        return [p[0] for p in proxy_scores[:count]]

    def check_proxy_schemes(self, proxy: str) -> str:
        """Ensure proxy has the correct scheme prefix"""
        schemes = ["http://", "https://", "socks4://", "socks5://"]
        if any(proxy.startswith(scheme) for scheme in schemes):
            return proxy

        return f"http://{proxy}"

    async def test_proxy(self, proxy: str) -> bool:
        """Test if a proxy is working"""
        formatted_proxy = self.check_proxy_schemes(proxy)
        connector = ProxyConnector.from_url(formatted_proxy)

        try:
            async with ClientSession(connector=connector, timeout=ClientTimeout(total=10)) as session:
                async with session.get("https://httpbin.org/ip") as response:
                    if response.status == 200:
                        self.record_success(proxy)
                        return True
                    else:
                        self.record_failure(proxy)
                        return False
        except Exception as e:
            self.record_failure(proxy)
            return False

    async def load_and_test_proxies(self, proxy_file: str = "proxy.txt") -> int:
        """Load proxies from file and test them"""
        if not os.path.exists(proxy_file):
            logger.error(f"Proxy file '{proxy_file}' not found!")
            return 0

        with open(proxy_file, "r") as f:
            loaded_proxies = f.read().splitlines()

        # Add proxies to our list
        for proxy in loaded_proxies:
            if proxy.strip():
                self.add_proxy(proxy.strip())

        logger.info(f"Loaded {len(loaded_proxies)} proxies from {proxy_file}")

        # Test proxies concurrently
        test_tasks = [self.test_proxy(proxy) for proxy in self.proxies[:]]
        results = await asyncio.gather(*test_tasks, return_exceptions=True)

        working_proxies = sum(1 for r in results if r is True)
        logger.info(f"Tested {len(test_tasks)} proxies. {working_proxies} are working.")

        return working_proxies

    async def load_from_github(self) -> int:
        """Load proxies from GitHub repository"""
        url = "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/all.txt"

        try:
            async with ClientSession(timeout=ClientTimeout(total=20)) as session:
                async with session.get(url=url) as response:
                    response.raise_for_status()
                    content = await response.text()

                    # Save to file
                    with open("auto_proxy.txt", "w") as f:
                        f.write(content)

                    # Process proxies
                    loaded_proxies = content.splitlines()
                    for proxy in loaded_proxies:
                        if proxy.strip():
                            self.add_proxy(proxy.strip())

                    logger.info(f"Downloaded {len(loaded_proxies)} proxies from GitHub")

                    # Test a sample of proxies
                    sample_size = min(50, len(self.proxies))
                    sample = random.sample(self.proxies, sample_size)

                    test_tasks = [self.test_proxy(proxy) for proxy in sample]
                    results = await asyncio.gather(*test_tasks, return_exceptions=True)

                    working_proxies = sum(1 for r in results if r is True)
                    logger.info(f"Tested {sample_size} sample proxies. {working_proxies} are working.")

                    return len(loaded_proxies)
        except Exception as e:
            logger.error(f"Failed to load proxies from GitHub: {e}")
            return 0


class RateLimiter:
    """Class to handle rate limiting for API calls"""

    def __init__(self, calls_per_minute: int = 20):
        self.calls_per_minute = calls_per_minute
        self.call_timestamps: List[float] = []
        self.last_reset = time.time()
       
    async def wait_if_needed(self):
        """Wait if we're making too many calls"""
        # Clean up old timestamps
        current_time = time.time()
        if current_time - self.last_reset >= 60:
            self.call_timestamps = [ts for ts in self.call_timestamps if current_time - ts < 60]
            self.last_reset = current_time

        # Check if we need to wait
        if len(self.call_timestamps) >= self.calls_per_minute:
            oldest_allowed = current_time - 60
            wait_until = self.call_timestamps[0] + 60

            if wait_until > current_time:
                wait_time = wait_until - current_time
                logger.info(f"Rate limit reached. Waiting for {wait_time:.2f} seconds...")
                await asyncio.sleep(wait_time)
                # Clean up after waiting
                self.call_timestamps = [ts for ts in self.call_timestamps if ts > oldest_allowed]

        # Record this call
        self.call_timestamps.append(time.time())
        self.call_timestamps.sort()


class AccountManager:
    """Class to manage accounts and their tokens"""
    
    def __init__(self, token_encryption: TokenEncryption):
        self.accounts: List[Dict[str, Any]] = []
        self.token_encryption = token_encryption
        self.account_stats: Dict[str, Dict[str, Any]] = {}
    
    def load_accounts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Load accounts from the accounts.json file"""
        try:
            if not os.path.exists("accounts.json"):
                logger.error("File 'accounts.json' not found.")
                return []
                
            with open("accounts.json", "r") as file:
                data = json.load(file)
                if isinstance(data, list):
                    # Initialize stats for each account
                    for account in data[:limit]:
                        email = account.get("Email", "")
                        if email and email not in self.account_stats:
                            self.account_stats[email] = {
                                "success": 0,
                                "failure": 0,
                                "last_used": 0,
                            }
                    return data[:limit]
                return []
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing accounts.json: {e}")
            return []
    
    def encrypt_tokens(self):
        """Encrypt all tokens in the accounts file"""
        try:
            if not os.path.exists("accounts.json"):
                logger.error("File 'accounts.json' not found.")
                return False
                
            with open("accounts.json", "r") as file:
                data = json.load(file)
                
            if not isinstance(data, list):
                logger.error("Invalid accounts data format.")
                return False
                
            # Make backup of original file
            with open("accounts.json.bak", "w") as backup:
                json.dump(data, backup, indent=2)
                
            # Encrypt tokens
            for account in data:
                if "Token" in account and account["Token"]:
                    account["Token"] = self.token_encryption.encrypt(account["Token"])
                    # Add a flag to indicate encryption
                    account["TokenEncrypted"] = True
            
            # Save encrypted data
            with open("accounts.json", "w") as file:
                json.dump(data, file, indent=2)
                
            logger.info("All tokens encrypted successfully.")
            return True
                
        except Exception as e:
            logger.error(f"Error encrypting tokens: {e}")
            return False
    
    def decrypt_token(self, account: Dict[str, Any]) -> str:
        """Get decrypted token from account"""
        if account.get("TokenEncrypted", False) and account.get("Token", ""):
            return self.token_encryption.decrypt(account["Token"])
        return account.get("Token", "")
    
    def record_success(self, email: str):
        """Record successful account usage"""
        if email in self.account_stats:
            self.account_stats[email]["success"] += 1
            self.account_stats[email]["last_used"] = time.time()
    
    def record_failure(self, email: str):
        """Record failed account usage"""
        if email in self.account_stats:
            self.account_stats[email]["failure"] += 1
            self.account_stats[email]["last_used"] = time.time()
    
    def hide_email(self, email: str) -> str:
        """Hide part of the email for display"""
        if "@" not in email:
            return "invalid_email"
            
        local, domain = email.split("@", 1)
        hide_local = local[:3] + "*" * 3 + local[-3:] if len(local) > 6 else local[:2] + "*" * 2 + local[-2:]
        return f"{hide_local}@{domain}"
    
    def hide_token(self, token: str) -> str:
        """Hide part of the token for display"""
        if len(token) < 10:
            return "*" * 10
            
        return token[:3] + "*" * (len(token) - 6) + token[-3:]
    
    def save_accounts(self):
        """Save accounts back to file (e.g., after updating tokens)"""
        try:
            if not self.accounts:
                logger.error("No accounts to save.")
                return False
                
            with open("accounts.json", "w") as file:
                json.dump(self.accounts, file, indent=2)
                
            logger.info("Accounts saved successfully.")
            return True
                
        except Exception as e:
            logger.error(f"Error saving accounts: {e}")
            return False


class APIClient:
    """Class to handle API communications"""

    def __init__(self, rate_limiter: RateLimiter, proxy_manager: ProxyManager):
        self.rate_limiter = rate_limiter
        self.proxy_manager = proxy_manager
        self.base_url = "https://www.aeropres.in"
        self.user_agent = FakeUserAgent().random
        self.base_extension_id = "fpdkjdnhkakefebpekbdhillbhonfjjp"
        self.jitter_enabled = True

    def generate_app_id(self) -> str:
        """Generate a unique app ID"""
        return uuid.uuid4().hex

    def generate_extension_ids(self, count: int) -> List[str]:
        extension_ids = []
        base_patterns = [
            "fpdkjdnh", "kakefebp", "ekbdhill", "bhonfjjp",
            "fpdjkdnh", "kkaefebp", "ekbdhiil", "bhonffjp"  # Tambah variasi
        ]
        used_patterns = set()

        for _ in range(count):
            while True:
                pattern = random.choice(base_patterns)
                if pattern not in used_patterns:
                    used_patterns.add(pattern)
                    new_id = pattern + uuid.uuid4().hex[:24]
                    extension_ids.append(new_id)
                    break
        return extension_ids

    def get_base_headers(self, extension_id: str = None) -> Dict[str, str]:
        """Get base headers for requests"""
        headers = {
            "Accept": "*/*",
            "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
            "Cache-Control": "no-cache",
            "Host": "www.aeropres.in",
            "User-Agent": self.user_agent,
        }

        if extension_id:
            headers["Origin"] = f"chrome-extension://{extension_id}"
        else:
            headers["Origin"] = f"chrome-extension://{self.base_extension_id}"

        return headers

    async def add_jitter(self):
        """Add random delay to avoid pattern detection"""
        if self.jitter_enabled:
            jitter = random.uniform(0.1, 1.5)
            await asyncio.sleep(jitter)

    async def make_request(
        self, 
        method: str, 
        endpoint: str, 
        proxy: str = None, 
        headers: Dict[str, str] = None, 
        data: str = None,
        retries: int = 3
    ) -> Tuple[int, Optional[Dict[str, Any]]]:
        """Make an API request with retries and error handling"""
        url = f"{self.base_url}{endpoint}"

        if headers is None:
            headers = self.get_base_headers()

        # Add jitter
        await self.add_jitter()

        # Wait for rate limiter
        await self.rate_limiter.wait_if_needed()

        # Set up connector with proxy if provided
        connector = ProxyConnector.from_url(proxy) if proxy else None

        for attempt in range(retries):
            try:
                async with ClientSession(
                    connector=connector, 
                    timeout=ClientTimeout(total=15)
                ) as session:
                    request_args = {
                        "url": url,
                        "headers": headers
                    }

                    if data and method.upper() in ["POST", "PUT", "PATCH"]:
                        request_args["data"] = data

                    # Make the request based on method
                    if method.upper() == "GET":
                        async with session.get(**request_args) as response:
                            status = response.status

                            # Handle common status codes
                            if status == 200:
                                if proxy:
                                    self.proxy_manager.record_success(proxy)
                                return status, await response.json()
                            elif status == 429:  # Rate limited
                                logger.warning(f"Rate limited. Waiting before retry...")
                                await asyncio.sleep(5 * (attempt + 1))
                            elif status in [400, 401, 403]:  # Auth issues
                                error_text = await response.text()
                                logger.error(f"Auth error ({status}): {error_text}")
                                return status, None
                            elif status >= 500:  # Server error
                                logger.warning(f"Server error ({status}). Retrying...")
                                await asyncio.sleep(2 * (attempt + 1))
                            else:
                                logger.warning(f"Unexpected status ({status})")
                                return status, None

                    elif method.upper() == "POST":
                        async with session.post(**request_args) as response:
                            status = response.status

                            if status == 200:
                                if proxy:
                                    self.proxy_manager.record_success(proxy)
                                return status, await response.json()
                            elif status == 429:
                                logger.warning(f"Rate limited. Waiting before retry...")
                                await asyncio.sleep(5 * (attempt + 1))
                            elif status in [400, 401, 403]:
                                error_text = await response.text()
                                logger.error(f"Auth error ({status}): {error_text}")
                                return status, None
                            elif status >= 500:
                                logger.warning(f"Server error ({status}). Retrying...")
                                await asyncio.sleep(2 * (attempt + 1))
                            else:
                                logger.warning(f"Unexpected status ({status})")
                                return status, None

            except asyncio.TimeoutError:
                logger.warning(f"Request timeout on attempt {attempt+1}/{retries}")
                if proxy:
                    self.proxy_manager.record_failure(proxy)

                # Double the timeout on next retry
                if attempt < retries - 1:
                    await asyncio.sleep(2 * (attempt + 1))

            except ClientResponseError as e:
                logger.error(f"Client response error: {e}")
                if proxy:
                    self.proxy_manager.record_failure(proxy)

                if attempt < retries - 1:
                    await asyncio.sleep(2)

            except aiohttp.ClientConnectorError:
                logger.error(f"Connection error (possibly proxy issue)")
                if proxy:
                    self.proxy_manager.record_failure(proxy)

                if attempt < retries - 1:
                    await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Request error: {e}")
                if proxy:
                    self.proxy_manager.record_failure(proxy)

                if attempt < retries - 1:
                    await asyncio.sleep(2)

        # All retries failed
        return -1, None

    async def check_ip(self, proxy: str = None) -> Optional[Dict[str, Any]]:
        """Check IP address information"""
        try:
            connector = ProxyConnector.from_url(proxy) if proxy else None

            async with ClientSession(
                connector=connector, 
                timeout=ClientTimeout(total=20)
            ) as session:
                async with session.get("https://ipinfo.io/json") as response:
                    if response.status == 200:
                        if proxy:
                            self.proxy_manager.record_success(proxy)
                        return await response.json()
                    else:
                        if proxy:
                            self.proxy_manager.record_failure(proxy)
                        return None
        except Exception as e:
            logger.error(f"Error checking IP: {e}")
            if proxy:
                self.proxy_manager.record_failure(proxy)
            return None

    async def get_user_data(
        self, 
        app_id: str, 
        token: str, 
        proxy: str = None
    ) -> Optional[Dict[str, Any]]:
        """Get user data from API"""
        endpoint = f"/api/atom/v1/userreferral/getpoint?appid={app_id}"
        headers = self.get_base_headers()
        headers["Authorization"] = f"Bearer {token}"
        headers["Content-Type"] = "application/json"

        status, response = await self.make_request(
            method="GET",
            endpoint=endpoint,
            headers=headers,
            proxy=proxy
        )

        if status == 200 and response and "data" in response:
            return response["data"]["rewardPoint"]
        return None

    async def send_keepalive(
        self,
        app_id: str,
        token: str,
        email: str,
        extension_id: str,
        proxy: str = None
    ) -> Optional[Dict[str, Any]]:
        """Send keepalive request to API"""
        endpoint = f"/chromeapi/dawn/v1/userreward/keepalive?appid={app_id}"

        data = json.dumps({
            "username": email,
            "extensionid": extension_id,
            "numberoftabs": random.randint(1, 3),  # Randomize tab count
            "_v": "1.1.1",
        })

        headers = self.get_base_headers(extension_id)
        headers["Authorization"] = f"Bearer {token}"
        headers["Content-Length"] = str(len(data))
        headers["Content-Type"] = "application/json"

        status, response = await self.make_request(
            method="POST",
            endpoint=endpoint,
            headers=headers,
            data=data,
            proxy=proxy
        )

        return response if status == 200 else None


class Dawn:
    async def pause_operations(self, duration: int):
        """Pause bot operations"""
        self.log(
            f"{Fore.YELLOW}Pausing operations for {duration} seconds...{Style.RESET_ALL}"
        )
        await asyncio.sleep(duration)

    async def rotate_all_proxies(self):
        """Force rotate all proxies"""
        self.log(f"{Fore.YELLOW}Rotating all proxies...{Style.RESET_ALL}")
        if self.proxy_choice == 1:
            await self.proxy_manager.load_from_github()
        else:
            await self.proxy_manager.load_and_test_proxies()

    async def update_bot_state(self):
        """Update status bot secara berkala"""
        current_time = time.time()
        hourly_requests = len(
            [t for t in self.rate_limiter.call_timestamps if t > current_time - 3600]
        )

        if hourly_requests > self.safety_settings["max_hourly_requests"]:
            await self.pause_operations(1800)  # Pause 30 menit

    def __init__(self):
        self.safety_settings = {
            "max_daily_requests": 800,    
            "max_hourly_requests": 80,  
            "min_success_rate": 0.85,    
            "max_concurrent_sessions": 2, 
            "auto_pause_threshold": 0.7    
        }

        # Monitor kesehatan
        self.health_monitor = {
            "success_rate": [],
            "error_patterns": {},
            "blocked_ips": set(),
            "suspicious_activities": [],
        }

        # Rotasi credential
        self.credential_rotation = {
            "last_token_refresh": None,
            "token_valid_duration": 86400,  # 24 jam
            "refresh_on_error": True,
        }
        # Initialize components
        self.token_encryption = TokenEncryption()
        self.proxy_manager = ProxyManager()
        self.rate_limiter = RateLimiter(calls_per_minute=30)
        self.account_manager = AccountManager(self.token_encryption)
        self.api_client = APIClient(self.rate_limiter, self.proxy_manager)

        # Bot configuration
        self.max_accounts = 2
        self.extensions_per_account = 1
        self.use_proxy = True
        self.proxy_choice = 1  # 1=auto, 2=manual, 3=none

        # Bot state
        self.running = False
        self.last_proxy_update = None
        self.proxy_update_interval = 1800  # 30 minutes
        
    async def check_health(self):
        """Monitor kesehatan bot"""
        current_success_rate = len([x for x in self.health_monitor["success_rate"][-100:] if x]) / 100
        if current_success_rate < self.safety_settings["min_success_rate"]:
            await self.pause_operations(300)  # Pause 5 menit

        if len(self.health_monitor["blocked_ips"]) > 5:
            await self.rotate_all_proxies()

    async def handle_error(self, error: Exception, context: str = ""):
        """Handle errors with exponential backoff"""
        self.health_monitor["error_patterns"][str(type(error))] = \
            self.health_monitor["error_patterns"].get(str(type(error)), 0) + 1

        if self.health_monitor["error_patterns"][str(type(error))] > 5:
            await self.pause_operations(600)  # Pause 10 menit

    def clear_terminal(self):
        """Clear the terminal screen"""
        os.system("cls" if os.name == "nt" else "clear")

    def log(self, message: str):
        """Log a message to console with timestamp"""
        print(
            f"{Fore.CYAN + Style.BRIGHT}[ {datetime.now().astimezone(wib).strftime('%x %X %Z')} ]{Style.RESET_ALL}"
            f"{Fore.WHITE + Style.BRIGHT} | {Style.RESET_ALL}{message}",
            flush=True,
        )

    def welcome(self):
        """Display welcome message"""
        print(
            f"""
        {Fore.GREEN + Style.BRIGHT}Dawn-Bot-Validator Version- 3.0.0 - MULTI-EXTENSION BOT |  {Fore.YELLOW + Style.BRIGHT}Enhanced with Security & Error Handling
            """
        )

    def format_seconds(self, seconds: int) -> str:
        """Format seconds to HH:MM:SS"""
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"

    async def encrypt_accounts(self):
        """Menu option to encrypt account tokens"""
        self.clear_terminal()
        self.welcome()

        print(f"{Fore.YELLOW + Style.BRIGHT}This will encrypt all tokens in your accounts.json file.{Style.RESET_ALL}")
        print(f"{Fore.YELLOW + Style.BRIGHT}A backup will be created as accounts.json.bak{Style.RESET_ALL}")
        print()

        confirm = input("Do you want to proceed? (y/n): ").strip().lower()

        if confirm == 'y':
            success = self.account_manager.encrypt_tokens()

            if success:
                print(f"{Fore.GREEN + Style.BRIGHT}Tokens encrypted successfully!{Style.RESET_ALL}")
                print(f"{Fore.GREEN + Style.BRIGHT}A backup of the original file was saved as accounts.json.bak{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED + Style.BRIGHT}Failed to encrypt tokens.{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW + Style.BRIGHT}Encryption cancelled.{Style.RESET_ALL}")

        input("\nPress Enter to return to main menu...")

    async def test_proxy_option(self):
        """Menu option to test proxies"""
        self.clear_terminal()
        self.welcome()

        print(f"{Fore.YELLOW + Style.BRIGHT}Proxy Testing{Style.RESET_ALL}")
        print("1. Test manual proxies from proxy.txt")
        print("2. Test auto proxies from GitHub")
        choice = input("Choose [1/2]: ").strip()

        if choice == "1":
            print(f"{Fore.CYAN + Style.BRIGHT}Testing proxies from proxy.txt...{Style.RESET_ALL}")
            count = await self.proxy_manager.load_and_test_proxies("proxy.txt")
            print(f"{Fore.GREEN + Style.BRIGHT}Tested {count} proxies.{Style.RESET_ALL}")
        elif choice == "2":
            print(f"{Fore.CYAN + Style.BRIGHT}Downloading and testing proxies from GitHub...{Style.RESET_ALL}")
            count = await self.proxy_manager.load_from_github()
            print(f"{Fore.GREEN + Style.BRIGHT}Downloaded {count} proxies.{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED + Style.BRIGHT}Invalid choice.{Style.RESET_ALL}")

        input("\nPress Enter to return to main menu...")

    async def question(self) -> int:
        """Display main menu and get user choice"""
        self.clear_terminal()
        self.welcome()

        print(f"{Fore.WHITE}Choose an option:")
        print(f"{Fore.YELLOW}1. {Fore.WHITE}Start the bot")
        print(f"{Fore.YELLOW}2. {Fore.WHITE}Test proxies")
        print(f"{Fore.YELLOW}3. {Fore.WHITE}Check account balance")
        print(f"{Fore.YELLOW}4. {Fore.WHITE}Encrypt account tokens")
        print(f"{Fore.YELLOW}5. {Fore.WHITE}Configure bot settings")
        print(f"{Fore.YELLOW}6. {Fore.WHITE}Exit")
        print()

        try:
            choice = input(f"{Fore.GREEN}Enter your choice [1-6]: {Fore.RESET}").strip()
            return int(choice) if choice.isdigit() and 1 <= int(choice) <= 6 else 0
        except ValueError:
            return 0

    async def configure_settings(self):
        """Configure bot settings"""
        self.clear_terminal()
        self.welcome()

        print(f"{Fore.YELLOW + Style.BRIGHT}Bot Configuration{Style.RESET_ALL}")
        print()

        # Show current settings
        print(f"{Fore.CYAN}Current settings:{Style.RESET_ALL}")
        print(f"Max accounts: {self.max_accounts}")
        print(f"Extensions per account: {self.extensions_per_account}")
        print(f"Proxy mode: {['Auto', 'Manual', 'None'][self.proxy_choice-1]}")
        print()

        # Update max accounts
        try:
            new_max = input(f"Max accounts (1-100) [{self.max_accounts}]: ").strip()
            if new_max and new_max.isdigit():
                self.max_accounts = max(1, min(100, int(new_max)))
        except ValueError:
            pass

        # Update extensions per account
        try:
            new_ext = input(f"Extensions per account (1-5) [{self.extensions_per_account}]: ").strip()
            if new_ext and new_ext.isdigit():
                self.extensions_per_account = max(1, min(5, int(new_ext)))
        except ValueError:
            pass

        # Update proxy settings
        print("\nProxy settings:")
        print("1. Auto (download from GitHub)")
        print("2. Manual (from proxy.txt)")
        print("3. None (use direct connection)")

        try:
            new_proxy = input(f"Choose proxy mode (1-3) [{self.proxy_choice}]: ").strip()
            if new_proxy and new_proxy.isdigit() and 1 <= int(new_proxy) <= 3:
                self.proxy_choice = int(new_proxy)
                self.use_proxy = self.proxy_choice != 3
        except ValueError:
            pass

        print(f"\n{Fore.GREEN + Style.BRIGHT}Settings updated successfully!{Style.RESET_ALL}")
        input("\nPress Enter to return to main menu...")

    async def check_balance(self):
        """Check and display account balances"""
        self.clear_terminal()
        self.welcome()

        print(f"{Fore.YELLOW + Style.BRIGHT}Checking Account Balances{Style.RESET_ALL}")
        print()

        # Load accounts
        accounts = self.account_manager.load_accounts()
        if not accounts:
            print(f"{Fore.RED + Style.BRIGHT}No accounts found in accounts.json{Style.RESET_ALL}")
            input("\nPress Enter to return to main menu...")
            return

        print(f"{Fore.CYAN + Style.BRIGHT}Found {len(accounts)} accounts{Style.RESET_ALL}")
        print()

        # Load proxies if needed
        proxies = []
        if self.use_proxy:
            if self.proxy_choice == 1:  # Auto proxy
                await self.proxy_manager.load_from_github()
            else:  # Manual proxy
                await self.proxy_manager.load_and_test_proxies()

            proxies = self.proxy_manager.get_best_proxies(len(accounts))
            if proxies:
                print(f"{Fore.GREEN + Style.BRIGHT}Using {len(proxies)} proxies{Style.RESET_ALL}")
            else:
                print(f"{Fore.YELLOW + Style.BRIGHT}No working proxies found, using direct connection{Style.RESET_ALL}")

        # Check each account balance
        for i, account in enumerate(accounts):
            email = account.get("Email", "")
            token = self.account_manager.decrypt_token(account)

            if not email or not token:
                print(f"{Fore.RED}Account {i+1}: Invalid account data{Style.RESET_ALL}")
                continue

            # Use a proxy if available
            proxy = proxies[i % len(proxies)] if proxies else None
            proxy_display = self.proxy_manager.get_proxy_display_name(proxy) if proxy else "None"

            # Generate app ID for this request
            app_id = self.api_client.generate_app_id()

            print(f"Checking balance for {self.account_manager.hide_email(email)} (Proxy: {proxy_display})...", end="", flush=True)

            try:
                # Get user data and balance
                balance = await self.api_client.get_user_data(app_id, token, proxy)

                if balance is not None:
                    print(f"{Fore.GREEN} {balance} points{Style.RESET_ALL}")
                    self.account_manager.record_success(email)
                else:
                    print(f"{Fore.RED} Failed to get balance{Style.RESET_ALL}")
                    self.account_manager.record_failure(email)
            except Exception as e:
                print(f"{Fore.RED} Error: {str(e)}{Style.RESET_ALL}")
                self.account_manager.record_failure(email)

            # Add some delay between requests
            await asyncio.sleep(2)

        print()
        input("\nPress Enter to return to main menu...")

    async def update_proxies_if_needed(self):
        """Update proxies if the update interval has passed"""
        current_time = time.time()

        if (self.last_proxy_update is None or 
            current_time - self.last_proxy_update > self.proxy_update_interval):

            if self.proxy_choice == 1:  # Auto proxy
                self.log("Auto-updating proxies from GitHub...")
                await self.proxy_manager.load_from_github()
            else:  # Manual proxy
                self.log("Refreshing proxies from proxy.txt...")
                await self.proxy_manager.load_and_test_proxies()

            self.last_proxy_update = current_time

    async def run_bot(self):
        """Main bot runner"""
        self.clear_terminal()
        self.welcome()

        print(f"{Fore.YELLOW + Style.BRIGHT}Starting Bot{Style.RESET_ALL}")

        # Initialize proxies
        if self.use_proxy:
            if self.proxy_choice == 1:  # Auto proxy
                self.log("Loading proxies from GitHub...")
                await self.proxy_manager.load_from_github()
            else:  # Manual proxy
                self.log("Loading proxies from proxy.txt...")
                await self.proxy_manager.load_and_test_proxies()

        # Load accounts
        accounts = self.account_manager.load_accounts(self.max_accounts)

        if not accounts:
            self.log(f"{Fore.RED + Style.BRIGHT}No accounts found in accounts.json{Style.RESET_ALL}")
            input("\nPress Enter to return to main menu...")
            return

        self.log(f"Loaded {len(accounts)} accounts")
        self.running = True

        start_time = time.time()
        cycle = 0

        try:
            while self.running:
                cycle += 1
                self.clear_terminal()
                self.welcome()

                # Calculate and display run time
                run_time = int(time.time() - start_time)
                print(f"{Fore.CYAN + Style.BRIGHT}Running for: {self.format_seconds(run_time)}{Style.RESET_ALL}")
                print(f"{Fore.CYAN + Style.BRIGHT}Cycle: {cycle}{Style.RESET_ALL}")
                print()

                # Update proxies if needed
                await self.update_proxies_if_needed()

                # Get proxies for this cycle
                proxies = []
                if self.use_proxy:
                    proxies = self.proxy_manager.get_best_proxies(len(accounts))

                    if proxies:
                        self.log(f"Using {len(proxies)} proxies for this cycle")
                    else:
                        self.log(f"{Fore.YELLOW}No working proxies, using direct connection{Style.RESET_ALL}")

                # Process each account
                for i, account in enumerate(accounts):
                    email = account.get("Email", "")
                    token = self.account_manager.decrypt_token(account)

                    if not email or not token:
                        self.log(f"{Fore.RED}Account {i+1}: Invalid account data{Style.RESET_ALL}")
                        continue

                    # Use a proxy if available
                    proxy = proxies[i % len(proxies)] if proxies else None
                    proxy_display = self.proxy_manager.get_proxy_display_name(proxy) if proxy else "None"

                    # Generate app ID for this account
                    app_id = self.api_client.generate_app_id()

                    # Generate extension IDs
                    extension_ids = self.api_client.generate_extension_ids(self.extensions_per_account)

                    self.log(f"Processing {self.account_manager.hide_email(email)} with {len(extension_ids)} extensions (Proxy: {proxy_display})")

                    success_count = 0

                    # Send keepalive for each extension ID
                    for ext_id in extension_ids:
                        try:
                            result = await self.api_client.send_keepalive(
                                app_id=app_id,
                                token=token,
                                email=email,
                                extension_id=ext_id,
                                proxy=proxy
                            )

                            if result:
                                success_count += 1
                                self.log(f"{Fore.GREEN}  ✓ Extension {ext_id[:8]}... keepalive successful{Style.RESET_ALL}")
                            else:
                                self.log(f"{Fore.RED}  ✗ Extension {ext_id[:8]}... keepalive failed{Style.RESET_ALL}")

                            # Add some delay between extension requests
                            await asyncio.sleep(random.uniform(2.0, 4.0))

                        except Exception as e:
                            self.log(f"{Fore.RED}  ✗ Error with {ext_id[:8]}: {str(e)}{Style.RESET_ALL}")

                    # Record success/failure for this account
                    if success_count > 0:
                        self.account_manager.record_success(email)
                    else:
                        self.account_manager.record_failure(email)

                    # Add some delay between accounts
                    await asyncio.sleep(random.uniform(2.0, 5.0))

                # Wait before next cycle (10-15 minutes)
                wait_time = random.randint(300, 450)
                self.log(f"{Fore.YELLOW}Cycle completed. Waiting {wait_time} seconds before next cycle...{Style.RESET_ALL}")

                # Wait with countdown
                for remaining in range(wait_time, 0, -1):
                    if not self.running:
                        break

                    if remaining % 60 == 0:  # Show countdown every minute
                        print(f"\rNext cycle in: {self.format_seconds(remaining)}    ", end="", flush=True)

                    await asyncio.sleep(1)

                print()  # New line after countdown

        except KeyboardInterrupt:
            self.log(f"{Fore.YELLOW}Bot stopping due to user interrupt...{Style.RESET_ALL}")
            self.running = False
        except Exception as e:
            self.log(f"{Fore.RED}Error in bot main loop: {str(e)}{Style.RESET_ALL}")
            self.running = False

        self.log(f"{Fore.YELLOW}Bot stopped.{Style.RESET_ALL}")
        input("\nPress Enter to return to main menu...")

    async def stop_bot(self):
        """Stop the bot gracefully"""
        self.running = False
        self.log(f"{Fore.YELLOW}Stopping bot gracefully... Please wait.{Style.RESET_ALL}")

    async def main(self):
        """Main entry point"""
        while True:
            choice = await self.question()

            if choice == 1:  # Start bot
                await self.run_bot()
            elif choice == 2:  # Test proxies
                await self.test_proxy_option()
            elif choice == 3:  # Check balance
                await self.check_balance()
            elif choice == 4:  # Encrypt tokens
                await self.encrypt_accounts()
            elif choice == 5:  # Configure settings
                await self.configure_settings()
            elif choice == 6:  # Exit
                print(f"{Fore.YELLOW + Style.BRIGHT}Exiting...{Style.RESET_ALL}")
                break
            else:
                print(f"{Fore.RED + Style.BRIGHT}Invalid choice. Please try again.{Style.RESET_ALL}")
                await asyncio.sleep(1)


# Main entry point
if __name__ == "__main__":
    # Create and run Dawn bot
    dawn = Dawn()
    
    try:
        # Run the main async function
        asyncio.run(dawn.main())
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW + Style.BRIGHT}Program interrupted by user. Exiting...{Style.RESET_ALL}")
    except Exception as e:
        print(f"\n{Fore.RED + Style.BRIGHT}Unexpected error: {str(e)}{Style.RESET_ALL}")
