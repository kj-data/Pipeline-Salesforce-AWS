import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests
from dotenv import load_dotenv
from simple_salesforce import Salesforce

load_dotenv()

DATA = Path(__file__).resolve().parents[1] / "data" / "salesforce_ready"


def connect() -> Salesforce:
    domain = os.environ["SF_DOMAIN"]
    resp = requests.post(
        f"https://{domain}/services/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_id": os.environ["SF_CONSUMER_KEY"],
            "client_secret": os.environ["SF_CONSUMER_SECRET"],
        },
        timeout=30,
    )
    if not resp.ok:
        sys.exit(f"Error al autenticar: {resp.status_code} {resp.text}")
    body = resp.json()
    host = urlparse(body["instance_url"]).hostname
    return Salesforce(instance=host, session_id=body["access_token"])


def to_records(df: pd.DataFrame) -> list[dict]:
    """DataFrame -> lista de dicts, omitiendo valores vacíos."""
    records = []
    for row in df.to_dict("records"):
        clean = {}
        for k, v in row.items():
            if pd.isna(v):
                continue
            if hasattr(v, "item"):
                v = v.item()
            clean[k] = v
        records.append(clean)
    return records


def report(label: str, df: pd.DataFrame, results: list[dict]) -> list[dict]:
    ok = [r for r in results if r["success"]]
    failed = [(i, r) for i, r in enumerate(results) if not r["success"]]
    print(f"{label}: {len(ok)} creados, {len(failed)} con error")
    if failed:
        errors = df.iloc[[i for i, _ in failed]].copy()
        errors["error"] = [str(r["errors"]) for _, r in failed]
        path = DATA / f"errors_{label.lower()}.csv"
        errors.to_csv(path, index=False)
        print(f"  Detalle de errores en {path}")
        print(f"  Primer error: {failed[0][1]['errors']}")
    return results


def main() -> None:
    sf = connect()
    print("Autenticación correcta")

    # Protección contra duplicados al volver a ejecutar
    n_acc = sf.query("SELECT COUNT() FROM Account")["totalSize"]
    n_opp = sf.query("SELECT COUNT() FROM Opportunity")["totalSize"]
    if n_acc or n_opp:
        sys.exit(
            f"La org ya tiene {n_acc} cuentas y {n_opp} oportunidades. "
            "Bórralas en Salesforce antes de recargar para no duplicar."
        )

    # 1. Cuentas
    accounts = pd.read_csv(DATA / "accounts_sf.csv")
    results = sf.bulk.Account.insert(to_records(accounts), batch_size=10000)
    report("Account", accounts, results)

    # Nombre de cuenta -> Id asignado por Salesforce
    name_to_id = {
        name: r["id"]
        for name, r in zip(accounts["Name"], results)
        if r["success"]
    }

    # 2. Oportunidades (AccountName -> AccountId)
    opps = pd.read_csv(DATA / "opportunities_sf.csv")
    opps["AccountId"] = opps["AccountName"].map(name_to_id)
    sin_vinculo = opps["AccountName"].notna() & opps["AccountId"].isna()
    if sin_vinculo.any():
        print(f"Aviso: {sin_vinculo.sum()} oportunidades apuntan a cuentas que no se crearon")
    opps = opps.drop(columns=["AccountName"])

    results = sf.bulk.Opportunity.insert(to_records(opps), batch_size=10000)
    report("Opportunity", opps, results)


if __name__ == "__main__":
    main()