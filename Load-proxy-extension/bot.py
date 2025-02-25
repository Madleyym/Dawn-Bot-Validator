from aiohttp import ClientResponseError, ClientSession, ClientTimeout
from aiohttp_socks import ProxyConnector
from colorama import Fore, Style, init
from datetime import datetime
from fake_useragent import FakeUserAgent
import asyncio, json, os, pytz, uuid, random

init(autoreset=True)

wib = pytz.timezone("Asia/Jakarta")


class Dawn:
    def __init__(self) -> None:
        self.headers = {
            "Accept": "*/*",
            "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
            "Cache-Control": "no-cache",
            "Host": "www.aeropres.in",
            "Origin": "chrome-extension://fpdkjdnhkakefebpekbdhillbhonfjjp",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "cross-site",
            "User-Agent": FakeUserAgent().random,
        }
        # Basis extension ID
        self.base_extension_id = "fpdkjdnhkakefebpekbdhillbhonfjjp"
        self.proxies = []
        self.proxy_index = 0
        self.used_proxies = {}
        self.proxy_display_mapping = {}
        self.proxy_count = 0
        self.max_accounts = 2
        self.extensions_per_account = 1  # Default jumlah extension per akun
        self.extension_ids = []  # Untuk menyimpan extension ID yang dibuat

    def clear_terminal(self):
        os.system("cls" if os.name == "nt" else "clear")

    def log(self, message):
        print(
            f"{Fore.CYAN + Style.BRIGHT}[ {datetime.now().astimezone(wib).strftime('%x %X %Z')} ]{Style.RESET_ALL}"
            f"{Fore.WHITE + Style.BRIGHT} | {Style.RESET_ALL}{message}",
            flush=True,
        )

    def welcome(self):
        print(
            f"""
        {Fore.GREEN + Style.BRIGHT}Dawn-Bot-Validator Version- 2.0.0 - MULTI-EXTENSION BOT |  {Fore.YELLOW + Style.BRIGHT}Mad-Jr - Join https://t.me/masterairdrophunts)
            """
        )

    def format_seconds(self, seconds):
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"

    def get_proxy_display_name(self, proxy):
        if proxy not in self.proxy_display_mapping:
            self.proxy_count += 1
            self.proxy_display_mapping[proxy] = f"Proxy - {self.proxy_count}"
        return self.proxy_display_mapping[proxy]

    def generate_extension_ids(self, count):
        """Generate a unique list of extension IDs based on the base extension ID"""
        # Reset existing extension IDs
        self.extension_ids = []

        # Always include the original extension ID
        self.extension_ids.append(self.base_extension_id)

        # Generate additional random extension IDs with similar format to the original
        for _ in range(count - 1):
            new_id = uuid.uuid4().hex[:32]
            self.extension_ids.append(new_id)

        return self.extension_ids

    async def load_auto_proxies(self):
        url = (
            "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/all.txt"
        )
        try:
            async with ClientSession(timeout=ClientTimeout(total=20)) as session:
                async with session.get(url=url) as response:
                    response.raise_for_status()
                    content = await response.text()
                    with open("auto_proxy.txt", "w") as f:
                        f.write(content)

                    self.proxies = content.splitlines()
                    if not self.proxies:
                        self.log(
                            f"{Fore.RED + Style.BRIGHT}No proxies found in the downloaded list!{Style.RESET_ALL}"
                        )
                        return

                    self.proxy_display_mapping = {}
                    self.proxy_count = 0

                    random.shuffle(self.proxies)
                    self.log(
                        f"{Fore.GREEN + Style.BRIGHT}Proxies successfully downloaded.{Style.RESET_ALL}"
                    )
                    self.log(
                        f"{Fore.YELLOW + Style.BRIGHT}Loaded {len(self.proxies)} proxies.{Style.RESET_ALL}"
                    )
                    self.log(f"{Fore.CYAN + Style.BRIGHT}-{Style.RESET_ALL}" * 75)
                    await asyncio.sleep(3)
        except Exception as e:
            self.log(
                f"{Fore.RED + Style.BRIGHT}Failed to load proxies: {e}{Style.RESET_ALL}"
            )
            return []

    async def load_manual_proxy(self):
        try:
            if not os.path.exists("proxy.txt"):
                print(
                    f"{Fore.RED + Style.BRIGHT}Proxy file 'proxy.txt' not found!{Style.RESET_ALL}"
                )
                return

            with open("proxy.txt", "r") as f:
                proxies = f.read().splitlines()

            self.proxies = proxies

            self.proxy_display_mapping = {}
            self.proxy_count = 0

            random.shuffle(self.proxies)
            self.log(
                f"{Fore.YELLOW + Style.BRIGHT}Loaded {len(self.proxies)} proxies.{Style.RESET_ALL}"
            )
            self.log(f"{Fore.CYAN + Style.BRIGHT}-{Style.RESET_ALL}" * 75)
            await asyncio.sleep(3)
        except Exception as e:
            print(
                f"{Fore.RED + Style.BRIGHT}Failed to load manual proxies: {e}{Style.RESET_ALL}"
            )
            self.proxies = []

    def get_unique_proxies(self, count, email=None):
        """Get a list of unique proxies for an email/extension combination"""
        if not self.proxies:
            self.log(f"{Fore.RED + Style.BRIGHT}No proxies available!{Style.RESET_ALL}")
            return []

        if email and email not in self.used_proxies:
            self.used_proxies[email] = set()

        unique_proxies = []
        attempts = 0
        max_attempts = len(self.proxies) * 2  # Avoid infinite loop

        available_proxies = list(self.proxies)
        random.shuffle(available_proxies)
        
        for proxy in available_proxies:
            if not email or proxy not in self.used_proxies[email]:
                if email:
                    self.used_proxies[email].add(proxy)
                proxy = self.check_proxy_schemes(proxy)
                unique_proxies.append(proxy)
                if len(unique_proxies) >= count:
                    break
        
        if len(unique_proxies) < count:
            self.log(f"{Fore.YELLOW + Style.BRIGHT}Warning: Only found {len(unique_proxies)} unique proxies, some may be reused.{Style.RESET_ALL}")
            while len(unique_proxies) < count:
                proxy = random.choice(self.proxies)
                proxy = self.check_proxy_schemes(proxy)
                unique_proxies.append(proxy)
        
        return unique_proxies

    def check_proxy_schemes(self, proxies):
        schemes = ["http://", "https://", "socks4://", "socks5://"]
        if any(proxies.startswith(scheme) for scheme in schemes):
            return proxies

        return f"http://{proxies}"

    def load_accounts(self):
        try:
            if not os.path.exists("accounts.json"):
                self.log(
                    f"{Fore.RED}File 'accounts.json' tidak ditemukan.{Style.RESET_ALL}"
                )
                return []

            with open("accounts.json", "r") as file:
                data = json.load(file)
                if isinstance(data, list):
                    return data[: self.max_accounts]
                return []
        except json.JSONDecodeError:
            return []

    def generate_app_id(self):
        return uuid.uuid4().hex

    def hide_email(self, email):
        local, domain = email.split("@", 1)
        hide_local = local[:3] + "*" * 3 + local[-3:]
        return f"{hide_local}@{domain}"

    def hide_token(self, token):
        hide_token = token[:3] + "*" * 3 + token[-3:]
        return hide_token

    async def cek_ip(self, proxy=None):
        connector = ProxyConnector.from_url(proxy) if proxy else None
        try:
            async with ClientSession(
                connector=connector, timeout=ClientTimeout(total=20)
            ) as session:
                async with session.get("https://ipinfo.io/json") as response:
                    response.raise_for_status()
                    return await response.json()
        except (Exception, ClientResponseError) as e:
            return None

    async def user_data(self, app_id: str, token: str, proxy=None):
        url = (
            f"https://www.aeropres.in/api/atom/v1/userreferral/getpoint?appid={app_id}"
        )
        headers = {
            **self.headers,
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        connector = ProxyConnector.from_url(proxy) if proxy else None
        try:
            async with ClientSession(
                connector=connector, timeout=ClientTimeout(total=20)
            ) as session:
                async with session.get(url=url, headers=headers) as response:
                    if response.status == 400:
                        self.log(
                            f"{Fore.MAGENTA + Style.BRIGHT}[ Token{Style.RESET_ALL}"
                            f"{Fore.WHITE + Style.BRIGHT} {self.hide_token(token)} {Style.RESET_ALL}"
                            f"{Fore.RED + Style.BRIGHT}Is Expired{Style.RESET_ALL}"
                            f"{Fore.MAGENTA + Style.BRIGHT} ]{Style.RESET_ALL}"
                        )
                        return

                    response.raise_for_status()
                    result = await response.json()
                    return result["data"]["rewardPoint"]
        except (Exception, ClientResponseError) as e:
            return None

    async def send_keepalive(
        self,
        app_id: str,
        token: str,
        email: str,
        extension_id: str,
        proxy=None,
        retries=60,
    ):
        url = f"https://www.aeropres.in/chromeapi/dawn/v1/userreward/keepalive?appid={app_id}"
        data = json.dumps(
            {
                "username": email,
                "extensionid": extension_id,
                "numberoftabs": 0,
                "_v": "1.1.1",
            }
        )
        headers = {
            **self.headers,
            "Authorization": f"Bearer {token}",  
            "Content-Length": str(len(data)),
            "Content-Type": "application/json",
            "Origin": f"chrome-extension://{extension_id}",
        }
        for attempt in range(retries):
            connector = ProxyConnector.from_url(proxy) if proxy else None
            try:
                async with ClientSession(
                    connector=connector, timeout=ClientTimeout(total=10)
                ) as session:
                    async with session.post(
                        url=url, headers=headers, data=data
                    ) as response:
                        response.raise_for_status()
                        return await response.json()
            except (Exception, ClientResponseError) as e:
                if attempt < retries - 1:
                    continue
                return None

    async def question(self):
        while True:
            try:
                print("Input number => Enter")
                print("1. Run With Auto Proxy | Proxy share (Free)")
                print("2. Run With Manual Proxy | Buy From Proxysale")
                print("3. Run Without Proxy | MRP Tech")
                choose = int(input("Choose [1/2/3] -> ").strip())

                if choose in [1, 2, 3]:
                    proxy_type = (
                        "With Auto Proxy"
                        if choose == 1
                        else "With Manual Proxy" if choose == 2 else "Without Proxy"
                    )
                    print(
                        f"{Fore.GREEN + Style.BRIGHT}Run {proxy_type} Selected.{Style.RESET_ALL}"
                    )

                    try:
                        num_accounts = int(
                            input(
                                "How many accounts to process? (default: 2): "
                            ).strip()
                            or "2"
                        )
                        self.max_accounts = max(1, min(num_accounts, 10))
                        print(
                            f"{Fore.GREEN + Style.BRIGHT}Will process {self.max_accounts} accounts.{Style.RESET_ALL}"
                        )
                    except ValueError:
                        print(
                            f"{Fore.YELLOW + Style.BRIGHT}Invalid input, using default of 2 accounts.{Style.RESET_ALL}"
                        )

                    # Tambahkan input untuk jumlah extension per akun
                    try:
                        extensions_per_account = int(
                            input(
                                "How many extensions per account? (default: 1): "
                            ).strip()
                            or "1"
                        )
                        self.extensions_per_account = max(1, extensions_per_account)
                        print(
                            f"{Fore.GREEN + Style.BRIGHT}Will run {self.extensions_per_account} extensions per account.{Style.RESET_ALL}"
                        )
                    except ValueError:
                        print(
                            f"{Fore.YELLOW + Style.BRIGHT}Invalid input, using default of 1 extension per account.{Style.RESET_ALL}"
                        )

                    await asyncio.sleep(1)
                    return choose
                else:
                    print(
                        f"{Fore.RED + Style.BRIGHT}Please enter either 1, 2 or 3.{Style.RESET_ALL}"
                    )
            except ValueError:
                print(
                    f"{Fore.RED + Style.BRIGHT}Invalid input. Enter a number (1, 2 or 3).{Style.RESET_ALL}"
                )

    async def process_account_multi_extension(
        self,
        app_id: str,
        token: str,
        email: str,
        extension_id: str,
        use_proxy: bool,
        proxy=None,
        extension_num: int = 1,
    ):
        hide_email = self.hide_email(email)
        proxy_display = "Without Proxy"

        if proxy:
            proxy_display = self.get_proxy_display_name(proxy)

        self.log(
            f"{Fore.MAGENTA + Style.BRIGHT}[ Account{Style.RESET_ALL}"
            f"{Fore.WHITE + Style.BRIGHT} {hide_email} {Style.RESET_ALL}"
            f"{Fore.MAGENTA + Style.BRIGHT}] [ Extension #{extension_num} {Style.RESET_ALL}"
            f"{Fore.WHITE + Style.BRIGHT} {extension_id[:6]}...{extension_id[-6:]} {Style.RESET_ALL}"
            f"{Fore.MAGENTA + Style.BRIGHT}]{Style.RESET_ALL}"
        )

        # Cek IP jika menggunakan proxy
        if use_proxy and proxy:
            my_ip = await self.cek_ip(proxy)
            if my_ip:
                self.log(
                    f"{Fore.MAGENTA + Style.BRIGHT}[ IP{Style.RESET_ALL}"
                    f"{Fore.WHITE + Style.BRIGHT} {my_ip['ip']} {Style.RESET_ALL}"
                    f"{Fore.MAGENTA + Style.BRIGHT}] [ Country{Style.RESET_ALL}"
                    f"{Fore.WHITE + Style.BRIGHT} {my_ip['country']} {Style.RESET_ALL}"
                    f"{Fore.MAGENTA + Style.BRIGHT}-{Style.RESET_ALL}"
                    f"{Fore.WHITE + Style.BRIGHT} {my_ip.get('region', 'Unknown')} {Style.RESET_ALL}"
                    f"{Fore.MAGENTA + Style.BRIGHT}]{Style.RESET_ALL}"
                )
        elif not use_proxy:
            my_ip = await self.cek_ip()
            if my_ip:
                self.log(
                    f"{Fore.MAGENTA + Style.BRIGHT}[ IP{Style.RESET_ALL}"
                    f"{Fore.WHITE + Style.BRIGHT} {my_ip['ip']} {Style.RESET_ALL}"
                    f"{Fore.MAGENTA + Style.BRIGHT}] [ Country{Style.RESET_ALL}"
                    f"{Fore.WHITE + Style.BRIGHT} {my_ip['country']} {Style.RESET_ALL}"
                    f"{Fore.MAGENTA + Style.BRIGHT}-{Style.RESET_ALL}"
                    f"{Fore.WHITE + Style.BRIGHT} {my_ip.get('region', 'Unknown')} {Style.RESET_ALL}"
                    f"{Fore.MAGENTA + Style.BRIGHT}]{Style.RESET_ALL}"
                )

        await asyncio.sleep(1)

        user = await self.user_data(app_id, token, proxy if use_proxy else None)

        if not user:
            self.log(
                f"{Fore.MAGENTA + Style.BRIGHT}[ Account{Style.RESET_ALL}"
                f"{Fore.WHITE + Style.BRIGHT} {hide_email} {Style.RESET_ALL}"
                f"{Fore.RED + Style.BRIGHT}Login Failed{Style.RESET_ALL}"
                f"{Fore.WHITE + Style.BRIGHT} With {proxy_display} {Style.RESET_ALL}"
                f"{Fore.MAGENTA + Style.BRIGHT}]{Style.RESET_ALL}"
            )
            return False

        total_points = 0
        for key, value in user.items():
            if (
                isinstance(key, str)
                and "points" in key.lower()
                and isinstance(value, (int, float))
            ):
                total_points += value

        self.log(
            f"{Fore.MAGENTA + Style.BRIGHT}[ Account{Style.RESET_ALL}"
            f"{Fore.WHITE + Style.BRIGHT} {hide_email} {Style.RESET_ALL}"
            f"{Fore.GREEN + Style.BRIGHT}Login Success{Style.RESET_ALL}"
            f"{Fore.MAGENTA + Style.BRIGHT} ] [ Balance{Style.RESET_ALL}"
            f"{Fore.WHITE + Style.BRIGHT} {total_points:.0f} Points {Style.RESET_ALL}"
            f"{Fore.MAGENTA + Style.BRIGHT}]{Style.RESET_ALL}"
        )
        await asyncio.sleep(1)

        self.log(
            f"{Fore.BLUE + Style.BRIGHT}Try to Send Ping for {hide_email} with Extension #{extension_num},{Style.RESET_ALL}"
            f"{Fore.YELLOW + Style.BRIGHT} Wait... {Style.RESET_ALL}"
        )
        await asyncio.sleep(1)

        keepalive = await self.send_keepalive(
            app_id, token, email, extension_id, proxy if use_proxy else None
        )

        if not keepalive:
            self.log(
                f"{Fore.MAGENTA + Style.BRIGHT}[ Ping{Style.RESET_ALL}"
                f"{Fore.WHITE + Style.BRIGHT} Sent With {proxy_display} {Style.RESET_ALL}"
                f"{Fore.MAGENTA + Style.BRIGHT}] [ Status{Style.RESET_ALL}"
                f"{Fore.YELLOW + Style.BRIGHT} Keep Alive Not Recorded {Style.RESET_ALL}"
                f"{Fore.MAGENTA + Style.BRIGHT}]{Style.RESET_ALL}"
            )
            return False

        if keepalive:
            self.log(
                f"{Fore.MAGENTA + Style.BRIGHT}[ Ping{Style.RESET_ALL}"
                f"{Fore.WHITE + Style.BRIGHT} Sent With {proxy_display} {Style.RESET_ALL}"
                f"{Fore.MAGENTA + Style.BRIGHT}] [ Status{Style.RESET_ALL}"
                f"{Fore.GREEN + Style.BRIGHT} Keep Alive Recorded {Style.RESET_ALL}"
                f"{Fore.MAGENTA + Style.BRIGHT}]{Style.RESET_ALL}"
            )

        return True

    async def main(self):
        try:
            accounts = self.load_accounts()
            if not accounts:
                self.log(
                    f"{Fore.RED}No accounts loaded from 'accounts.json'.{Style.RESET_ALL}"
                )
                return

            use_proxy_choice = await self.question()

            use_proxy = use_proxy_choice in [1, 2]

            self.clear_terminal()
            self.welcome()

            accounts = accounts[: self.max_accounts]

            self.log(
                f"{Fore.GREEN + Style.BRIGHT}Account's Total: {Style.RESET_ALL}"
                f"{Fore.WHITE + Style.BRIGHT}{len(accounts)}{Style.RESET_ALL}"
            )

            self.log(
                f"{Fore.GREEN + Style.BRIGHT}Extensions Per Account: {Style.RESET_ALL}"
                f"{Fore.WHITE + Style.BRIGHT}{self.extensions_per_account}{Style.RESET_ALL}"
            )

            self.log(f"{Fore.CYAN + Style.BRIGHT}-{Style.RESET_ALL}" * 75)

            last_proxy_update = None
            proxy_update_interval = 1800

            if use_proxy and use_proxy_choice == 1:
                await self.load_auto_proxies()
                last_proxy_update = datetime.now()
            elif use_proxy and use_proxy_choice == 2:
                await self.load_manual_proxy()

            while True:
                if use_proxy and use_proxy_choice == 1:
                    if (
                        not last_proxy_update
                        or (datetime.now() - last_proxy_update).total_seconds()
                        > proxy_update_interval
                    ):
                        await self.load_auto_proxies()
                        last_proxy_update = datetime.now()

                self.used_proxies = {}

                extension_ids = self.generate_extension_ids(self.extensions_per_account)

                for account in accounts:
                    token = account.get("Token")
                    email = account.get("Email", "Unknown Email")

                    if not token:
                        self.log(
                            f"{Fore.MAGENTA + Style.BRIGHT}[ Account{Style.RESET_ALL}"
                            f"{Fore.WHITE + Style.BRIGHT} {email} {Style.RESET_ALL}"
                            f"{Fore.YELLOW + Style.BRIGHT}Token Not Found in 'accounts.json'{Style.RESET_ALL}"
                            f"{Fore.MAGENTA + Style.BRIGHT} ]{Style.RESET_ALL}"
                        )
                        continue

                    unique_proxies = []
                    if use_proxy:
                        unique_proxies = self.get_unique_proxies(
                            self.extensions_per_account, email
                        )
                        if len(unique_proxies) < self.extensions_per_account:
                            self.log(
                                f"{Fore.YELLOW + Style.BRIGHT}Warning: Could only find {len(unique_proxies)} unique proxies for {self.hide_email(email)}{Style.RESET_ALL}"
                            )

                    tasks = []
                    for idx, extension_id in enumerate(extension_ids):
                        app_id = self.generate_app_id()
                        proxy = (
                            None
                            if not use_proxy
                            else (
                                unique_proxies[idx]
                                if idx < len(unique_proxies)
                                else None
                            )
                        )

                        # Jalankan proses untuk setiap extension
                        success = await self.process_account_multi_extension(
                            app_id,
                            token,
                            email,
                            extension_id,
                            use_proxy,
                            proxy,
                            idx + 1,
                        )

                        # Jeda singkat antara setiap extension
                        if idx < len(extension_ids) - 1:
                            delay = random.randint(2, 5)
                            await asyncio.sleep(delay)

                    # Jeda sebelum berpindah ke akun berikutnya
                    if accounts.index(account) < len(accounts) - 1:
                        delay = random.randint(5, 10)
                        self.log(
                            f"{Fore.YELLOW + Style.BRIGHT}Waiting {delay} seconds before next account...{Style.RESET_ALL}"
                        )
                        await asyncio.sleep(delay)

                self.log(f"{Fore.CYAN + Style.BRIGHT}-{Style.RESET_ALL}" * 75)
                self.log(
                    f"{Fore.GREEN + Style.BRIGHT}Completed all accounts with multiple extensions.{Style.RESET_ALL}"
                )

                seconds = 120
                while seconds > 0:
                    formatted_time = self.format_seconds(seconds)
                    print(
                        f"{Fore.CYAN+Style.BRIGHT}[ Wait for{Style.RESET_ALL}"
                        f"{Fore.WHITE+Style.BRIGHT} {formatted_time} {Style.RESET_ALL}"
                        f"{Fore.CYAN+Style.BRIGHT}... ]{Style.RESET_ALL}"
                        f"{Fore.WHITE+Style.BRIGHT} | {Style.RESET_ALL}"
                        f"{Fore.BLUE+Style.BRIGHT}All Accounts Have Been Processed.{Style.RESET_ALL}",
                        end="\r",
                    )
                    await asyncio.sleep(1)
                    seconds -= 1

        except Exception as e:
            self.log(f"{Fore.RED+Style.BRIGHT}Error: {e}{Style.RESET_ALL}")


if __name__ == "__main__":
    try:
        bot = Dawn()
        asyncio.run(bot.main())
    except KeyboardInterrupt:
        print(
            f"{Fore.CYAN + Style.BRIGHT}[ {datetime.now().astimezone(wib).strftime('%x %X %Z')} ]{Style.RESET_ALL}"
            f"{Fore.WHITE + Style.BRIGHT} | {Style.RESET_ALL}"
            f"{Fore.RED + Style.BRIGHT}[ EXIT ] Dawn - BOT{Style.RESET_ALL}",
        )
