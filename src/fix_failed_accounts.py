import pandas as pd

from load_to_salesforce import DATA, connect, to_records


def main() -> None:
    sf = connect()
    print("Autenticación correcta")

    # Cuentas que fallaron en la primera carga
    failed = pd.read_csv(DATA / "errors_account.csv").drop(columns=["error"])
    print("Cuentas a recrear:", failed["Name"].tolist())

    # Evita duplicar si el script se ejecuta dos veces
    existing = {
        r["Name"]: r["Id"]
        for r in sf.query_all("SELECT Id, Name FROM Account")["records"]
    }
    to_create = failed[~failed["Name"].isin(existing)].copy()

    if not to_create.empty:
        # Guarda el país original en Description y omite el campo inválido
        to_create["Description"] = "billing_country_original=" + to_create["BillingCountry"].astype(str)
        to_create = to_create.drop(columns=["BillingCountry"])
        results = sf.bulk.Account.insert(to_records(to_create), batch_size=10000)
        for name, r in zip(to_create["Name"], results):
            if r["success"]:
                existing[name] = r["id"]
            else:
                print(f"Error creando {name}: {r['errors']}")

    # Oportunidades sin cuenta cuyo nombre termina en " - <cuenta>"
    opps = sf.query_all("SELECT Id, Name FROM Opportunity WHERE AccountId = null")["records"]
    updates = []
    for opp in opps:
        for name in failed["Name"]:
            if name in existing and opp["Name"].endswith(f" - {name}"):
                updates.append({"Id": opp["Id"], "AccountId": existing[name]})
                break

    print(f"Oportunidades a vincular: {len(updates)}")
    if updates:
        results = sf.bulk.Opportunity.update(updates, batch_size=10000)
        ok = sum(1 for r in results if r["success"])
        print(f"Vinculadas: {ok}, con error: {len(results) - ok}")


if __name__ == "__main__":
    main()