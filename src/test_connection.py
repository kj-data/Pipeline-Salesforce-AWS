import os
import requests
from dotenv import load_dotenv

load_dotenv()

domain = os.environ["SF_DOMAIN"]
key = os.environ["SF_CONSUMER_KEY"]
secret = os.environ["SF_CONSUMER_SECRET"]

# 1. Pedir el token de acceso
resp = requests.post(
    f"https://{domain}/services/oauth2/token",
    data={
        "grant_type": "client_credentials",
        "client_id": key,
        "client_secret": secret,
    },
    timeout=30,
)
if not resp.ok:
    print("Error al autenticar:", resp.status_code, resp.text)
    raise SystemExit(1)

token = resp.json()["access_token"]
print("Autenticación correcta")

# 2. Consultar 5 cuentas
query = requests.get(
    f"https://{domain}/services/data/v60.0/query",
    params={"q": "SELECT Id, Name FROM Account LIMIT 5"},
    headers={"Authorization": f"Bearer {token}"},
    timeout=30,
)
if not query.ok:
    print("Error al consultar:", query.status_code, query.text)
    raise SystemExit(1)

print("Cuentas encontradas:", query.json()["records"])