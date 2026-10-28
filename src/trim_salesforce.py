import sys

import pandas as pd

from load_to_salesforce import connect

TARGET = 1200          # oportunidades a conservar
KEEP_NO_ACCOUNT = 100  # sin cuenta en el dataset original (para pruebas de calidad)
KEEP_FAILED = 40       # de las 2 cuentas que fallaron (se vincularán después)


def main(apply: bool) -> None:
    sf = connect()
    rows = sf.query_all("SELECT Id, Name, StageName, AccountId FROM Opportunity")["records"]
    df = pd.DataFrame(rows).drop(columns="attributes")
    print("Oportunidades actuales:", len(df))

    sin_cuenta = df["AccountId"].isna() & df["Name"].str.endswith(" - Sin cuenta")
    failed = df["AccountId"].isna() & ~sin_cuenta
    linked = df["AccountId"].notna()

    keep = pd.concat([
        df[sin_cuenta].sample(min(KEEP_NO_ACCOUNT, sin_cuenta.sum()), random_state=42),
        df[failed].sample(min(KEEP_FAILED, failed.sum()), random_state=42),
    ])

    # El resto, repartido proporcionalmente por etapa
    resto = TARGET - len(keep)
    pool = df[linked]
    frac = resto / len(pool)
    keep = pd.concat([
        keep,
        pool.groupby("StageName", group_keys=False).sample(frac=frac, random_state=42),
    ])

    to_delete = df[~df["Id"].isin(keep["Id"])]
    print("Se conservarán:", len(keep))
    print(keep["StageName"].value_counts().to_string())
    print("Se borrarán:", len(to_delete))

    if not apply:
        print("\nSimulación. Para borrar de verdad: --apply")
        return

    if input("Escribe BORRAR para confirmar: ") != "BORRAR":
        sys.exit("Cancelado")

    results = sf.bulk.Opportunity.delete(
        [{"Id": i} for i in to_delete["Id"]], batch_size=10000
    )
    ok = sum(1 for r in results if r["success"])
    print(f"Borradas: {ok}, con error: {len(results) - ok}")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)