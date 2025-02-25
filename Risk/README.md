# Dawn Bot Validator - v1.0.5

![Dawn Bot Banner](images/images.png)

A specialized bot for validating and maintaining multiple Dawn extension accounts through automated proxy rotation and keepalive pings.

## 🌟 Features

- **Alternating Account Processing**: Rotates through all accounts with each proxy cycle
- **Multiple Proxy Support**: Use auto-downloaded or your own custom proxies
- **Smart Proxy Rotation**: Each account uses different proxies to avoid detection
- **Account Monitoring**: Tracks points balance and login status
- **Flexible Configuration**: Set number of accounts and proxy cycles
- **Auto-Recovery**: Automatically attempts alternative proxies if one fails
- **Colorful Console Output**: Clear visual feedback on bot operation

## ⚙️ Requirements

- Python 3.7+
- Required Python packages (install via `pip install -r requirements.txt`):
  - aiohttp
  - aiohttp_socks
  - colorama
  - fake_useragent
  - pytz

## 📋 Setup Instructions

1. Clone or download this repository
2. Install required packages:
   ```bash
   pip install -r requirements.txt
   ```
3. Create an `accounts.json` file in the same directory with your accounts:
   ```json
   [
     {
       "Email": "your_email@example.com",
       "Token": "your_token_here"
     },
     {
       "Email": "another_email@example.com",
       "Token": "another_token_here"
     }
   ]
   ```
4. (Optional) Create a `proxy.txt` file with your proxies (one per line):
   ```
   http://username:password@host:port
   socks5://username:password@host:port
   ```

## 🚀 Usage

Run the bot with:

```bash
python risk-bot.py # or python3 risk-bot.py
```

### Configuration Options

When you start the bot, you'll be prompted to select:

1. **Proxy Mode**:
   - Auto Proxy (Free shared proxies)
   - Manual Proxy (Your own proxies from proxy.txt)
   - No Proxy (Use your own IP)

2. **Number of Accounts**: How many accounts to process (1-10)

3. **Proxy Cycles**: How many unique proxies to use per account

## 🔄 How It Works

The Dawn Bot uses an alternating processing method that rotates through all accounts with each proxy cycle:

```
Cycle 1: Account1 → Account2 → Account3
Cycle 2: Account1 → Account2 → Account3
Cycle 3: Account1 → Account2 → Account3
```

For each account in a cycle, the bot:
1. Checks the IP and location (with proxy)
2. Attempts to login using the account token
3. Checks and displays point balance
4. Sends a keepalive ping to maintain account activity

After all cycles complete, the bot waits 2 minutes before starting again.

## ⚠️ Disclaimer

This tool is for educational purposes only. Use at your own risk. The creators are not responsible for any account restrictions or bans that may result from using this bot.

## 🔗 Links

- Join our community: [Telegram](https://t.me/masterairdrophunts)
- Check for updates: [GitHub](https://github.com/Madleyym/Dawn-Bot-Validator/)

## 📜 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

Last Updated: 2025-02-25  
Created by: Mad-Jr