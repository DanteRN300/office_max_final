import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules.historical_ml import build_historical_sales_ml_summary


def test_historical_sales_ml_trains_logistic_and_random_forest():
    rows = []
    for sku in ["A", "B", "C", "D", "E"]:
        for date in pd.date_range("2024-01-01", "2025-12-31", freq="14D"):
            price = 10 + (date.month % 4) + (ord(sku) - 65)
            qty = (
                20
                + (date.month in [11, 12]) * 10
                + (sku in ["A", "B"]) * 8
                - int(price / 4)
            )
            rows.append(
                {
                    "tran_date": date,
                    "qty": qty,
                    "net_sale": qty * price,
                    "prod_nbr": sku,
                    "dept_nm": f"Dept{ord(sku) % 2}",
                    "subdept_nm": "Cat",
                    "state": "Jalisco",
                }
            )

    summary = build_historical_sales_ml_summary(pd.DataFrame(rows))

    assert summary["status"] == "ok"
    assert set(summary["metrics"]["modelo"]) == {"Regresión logística", "Random Forest"}
    assert not summary["feature_importance"].empty
