import json
import os
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import requests
from dateutil import parser

from gst_shopify.config import load_seller_details

SHOPIFY_STORE = os.getenv("SHOPIFY_STORE")
API_TOKEN = os.getenv("API_TOKEN")


def get_shopify_order(order_id):
    url = f"https://{SHOPIFY_STORE}/admin/api/2024-10/orders/{order_id}.json"
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": API_TOKEN,
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()["order"]


def get_inventory_item_id(variant_id):
    url = f"https://{SHOPIFY_STORE}/admin/api/2024-10/variants/{variant_id}.json"
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": API_TOKEN,
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()["variant"].get("inventory_item_id")


def get_hsn_code(inventory_item_id):
    url = f"https://{SHOPIFY_STORE}/admin/api/2024-10/inventory_items/{inventory_item_id}.json"
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": API_TOKEN,
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()["inventory_item"].get("harmonized_system_code", "00000000")


def generate_gst_invoice_data(shopify_order, seller_details):
    shipping_amount = Decimal(
        shopify_order.get("total_shipping_price_set", {})
        .get("shop_money", {})
        .get("amount", "0.00")
    )
    invoice_data = {
        "Version": "1.1",
        "TranDtls": {
            "TaxSch": "GST",
            "SupTyp": "EXPWOP",
            "IgstOnIntra": "N",
            "RegRev": "N",
            "EcmGstin": None,
        },
        "DocDtls": {
            "Typ": "INV",
            "No": str(shopify_order["name"]),
            "Dt": parser.parse(shopify_order["created_at"]).strftime("%d/%m/%Y"),
        },
        "SellerDtls": seller_details,
        "BuyerDtls": {
            "Gstin": "URP",
            "LglNm": shopify_order.get("customer", {}).get("first_name", "")
            + " "
            + shopify_order.get("customer", {}).get("last_name", ""),
            "Pos": "96",
            "Addr1": shopify_order.get("shipping_address", {}).get("address1", ""),
            "Addr2": shopify_order.get("shipping_address", {}).get("address2", ""),
            "Loc": shopify_order.get("shipping_address", {}).get("city", ""),
            "Pin": "999999",
            "Stcd": "96",
            "Ph": None,
            "Em": None,
        },
        "ItemList": [],
        "ValDtls": {
            "AssVal": Decimal("0.00"),
            "CgstVal": Decimal("0.00"),
            "SgstVal": Decimal("0.00"),
            "IgstVal": Decimal("0.00"),
            "CesVal": Decimal("0.00"),
            "StCesVal": Decimal("0.00"),
            "Discount": Decimal("0.00"),
            "OthChrg": shipping_amount,
            "RndOffAmt": Decimal("0.00"),
            "TotInvVal": Decimal("0.00"),
        },
    }

    for idx, item in enumerate(shopify_order["line_items"]):
        variant_id = item.get("variant_id")
        inventory_item_id = get_inventory_item_id(variant_id) if variant_id else None
        hsn_code = get_hsn_code(inventory_item_id) if inventory_item_id else "00000000"

        quantity = Decimal(item.get("quantity", 1))
        unit_price = Decimal(item.get("price", "0.00"))
        total_amount = (unit_price * quantity).quantize(
            Decimal("0.00"), rounding=ROUND_HALF_UP
        )
        invoice_data["ItemList"].append(
            {
                "SlNo": str(idx + 1),
                "PrdDesc": item.get("title", ""),
                "IsServc": "N",
                "HsnCd": hsn_code,
                "Barcde": item.get("barcode", ""),
                "Qty": quantity,
                "FreeQty": Decimal("0.00"),
                "Unit": "PCS",
                "UnitPrice": unit_price,
                "TotAmt": total_amount,
                "Discount": Decimal("0.00"),
                "PreTaxVal": total_amount,
                "AssAmt": total_amount,
                "GstRt": Decimal("0.00"),
                "IgstAmt": Decimal("0.00"),
                "CgstAmt": Decimal("0.00"),
                "SgstAmt": Decimal("0.00"),
                "CesRt": Decimal("0.00"),
                "CesAmt": Decimal("0.00"),
                "CesNonAdvlAmt": Decimal("0.00"),
                "StateCesRt": Decimal("0.00"),
                "StateCesAmt": Decimal("0.00"),
                "StateCesNonAdvlAmt": Decimal("0.00"),
                "OthChrg": Decimal("0.00"),
                "TotItemVal": total_amount.quantize(
                    Decimal("0.00"), rounding=ROUND_HALF_UP
                ),
                "AttribDtls": [],
            }
        )
        invoice_data["ValDtls"]["AssVal"] += total_amount
        invoice_data["ValDtls"]["TotInvVal"] += total_amount

    invoice_data["ValDtls"]["TotInvVal"] += shipping_amount
    invoice_data["ValDtls"]["TotInvVal"] = invoice_data["ValDtls"][
        "TotInvVal"
    ].quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)

    return invoice_data


def save_invoice_to_json(out_dir: Path, invoice_data, order_id):
    file_name = out_dir / f"gst_export_invoice_lut_{order_id}.json"
    with open(file_name, "w") as json_file:
        json.dump(invoice_data, json_file, indent=4, default=str)
    print(f"GST export e-invoice (LUT) saved as {file_name}")


def create_e_invoice_lut(out_dir: Path, order_id):
    seller_details = load_seller_details()
    shopify_order = get_shopify_order(order_id)
    invoice_data = generate_gst_invoice_data(shopify_order, seller_details)
    save_invoice_to_json(out_dir, invoice_data, order_id)


def generate_invoices(input_file: Path, out_dir: Path):
    try:
        with open(input_file, "r") as file:
            order_ids = [line.strip() for line in file if line.strip()]

        for order_id in order_ids:
            print(f"Processing order ID: {order_id}")
            create_e_invoice_lut(order_id)
        print("All invoices generated successfully.")

    except FileNotFoundError:
        print(f"Input file '{input_file}' not found.")
    except Exception as e:
        print(f"An error occurred: {e}")


def main(input_file: Path, out_dir: Path):
    generate_invoices(input_file, out_dir)


if __name__ == "__main__":
    main()
