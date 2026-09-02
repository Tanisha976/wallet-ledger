import requests
import concurrent.futures

BASE_URL = "http://127.0.0.1:8000"

# Fresh wallet, funded with exactly enough for 5 successful withdrawals of 100
resp = requests.post(f"{BASE_URL}/wallets", json={"owner_name": "concurrency_test"})
wallet_id = resp.json()["id"]
requests.post(f"{BASE_URL}/wallets/{wallet_id}/deposit", json={"amount": 500})

def try_withdraw(_):
    r = requests.post(f"{BASE_URL}/wallets/{wallet_id}/withdraw", json={"amount": 100})
    return r.status_code

# Fire 50 withdraw requests at once
with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
    results = list(executor.map(try_withdraw, range(50)))

successes = results.count(200)
failures = results.count(400)

final_balance = requests.get(f"{BASE_URL}/wallets/{wallet_id}").json()["balance"]

print(f"Successful withdrawals: {successes}")
print(f"Failed (insufficient balance): {failures}")
print(f"Final balance: {final_balance}")