import json
import os
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import requests
from dateutil import parser

from gst_shopify.api_client import graphql_request
from gst_shopify.config import load_seller_details

SHOPIFY_STORE = os.getenv("SHOPIFY_STORE")
API_TOKEN = os.getenv("API_TOKEN")

QUERY_BATCH_SIZE = 250


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


def validate_order_total(shopify_order, calculated_line_items_total):
    """
    Validate calculated line items total against Shopify order subtotal,
    excluding shipping since it's calculated from the same field.
    Returns tuple of (is_valid, explanation)
    """
    subtotal_price = Decimal(shopify_order.get("subtotal_price", "0.00"))
    total_discounts = Decimal(shopify_order.get("total_discounts", "0.00"))

    # Expected total is subtotal minus discounts
    expected_total = subtotal_price - total_discounts

    # Compare with small tolerance for rounding
    tolerance = Decimal("0.01")
    if abs(calculated_line_items_total - expected_total) <= tolerance:
        return True, "Line items total matches Shopify subtotal"

    discrepancy_report = (
        f"\nLine Items Total Validation Failed:\n"
        f"Calculated line items total: {calculated_line_items_total}\n"
        f"Expected total (subtotal - discounts): {expected_total}\n"
        f"Shopify subtotal: {subtotal_price}\n"
        f"Shopify discounts: {total_discounts}\n"
        f"Difference: {abs(calculated_line_items_total - expected_total)}"
    )

    return False, discrepancy_report


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

    valid_item_count = 0
    for idx, item in enumerate(shopify_order["line_items"]):
        if item.get("fulfillment_status") != "fulfilled":
            print(f"Skipping item {item.get('name')} - not fulfilled")
            continue
        variant_id = item.get("variant_id")
        inventory_item_id = get_inventory_item_id(variant_id) if variant_id else None
        hsn_code = get_hsn_code(inventory_item_id) if inventory_item_id else "00000000"
        quantity = Decimal(str(item["quantity"]))
        unit_price = Decimal(str(item["price"]))
        discount_amount = Decimal(str(item.get("total_discount", "0.00")))
        total_before_discount = (unit_price * quantity).quantize(
            Decimal("0.00"), rounding=ROUND_HALF_UP
        )
        total_amount = (total_before_discount - discount_amount).quantize(
            Decimal("0.00"), rounding=ROUND_HALF_UP
        )

        invoice_data["ItemList"].append(
            {
                "SlNo": str(valid_item_count + 1),
                "PrdDesc": item["title"],
                "IsServc": "N",
                "HsnCd": hsn_code,
                "Barcde": item.get("barcode", ""),
                "Qty": quantity,
                "FreeQty": Decimal("0.00"),
                "Unit": "PCS",
                "UnitPrice": unit_price,
                "TotAmt": total_before_discount,  # Amount before discount
                "Discount": discount_amount,  # Item level discount
                "PreTaxVal": total_amount,  # Amount after discount
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
                "TotItemVal": total_amount,
            }
        )
        invoice_data["ValDtls"]["AssVal"] += total_amount
        invoice_data["ValDtls"]["TotInvVal"] += total_amount
        invoice_data["ValDtls"]["Discount"] += discount_amount
        valid_item_count += 1

    invoice_data["ValDtls"]["OthChrg"] = shipping_amount
    invoice_data["ValDtls"]["TotInvVal"] += shipping_amount
    invoice_data["ValDtls"]["TotInvVal"] = invoice_data["ValDtls"][
        "TotInvVal"
    ].quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
    if not invoice_data["ItemList"]:
        raise ValueError(
            f"Order {shopify_order['name']} has no valid items for invoice generation"
        )
    return invoice_data


def save_invoice_to_json(out_dir: Path, invoice_data, order_id):
    out_dir.mkdir(parents=True, exist_ok=True)
    file_name = out_dir / f"gst_export_invoice_lut_{order_id}.json"
    with open(file_name, "w") as json_file:
        json.dump(invoice_data, json_file, indent=4, default=str)
    print(f"GST export e-invoice (LUT) saved as {file_name}")


def create_e_invoice_lut(out_dir: Path, order_id):
    seller_details = load_seller_details()
    shopify_order = get_shopify_order(order_id)
    invoice_data = generate_gst_invoice_data(shopify_order, seller_details)
    save_invoice_to_json(out_dir, invoice_data, order_id)


def get_order_ids_from_names(
    order_names: list[str], batch_size: int = QUERY_BATCH_SIZE
) -> dict[str, str]:
    """Look up multiple Shopify order IDs using order names in batches.
    Returns a dictionary mapping order names to their IDs."""
    name_to_id = {}
    orders_not_found = set(order_names)
    for i in range(0, len(order_names), batch_size):
        batch = order_names[i : i + batch_size]
        query_str = " OR ".join(f"name:{name}" for name in batch)

        query = f"""
        {{
            orders(first: {batch_size}, query: "{query_str}") {{
                edges {{
                    node {{
                        id
                        name
                    }}
                }}
            }}
        }}
        """
        response = graphql_request(query)
        try:
            orders = response["data"]["orders"]["edges"]
            for order in orders:
                name = order["node"]["name"]
                order_id = order["node"]["id"].split("/")[-1]
                name_to_id[name] = order_id
                orders_not_found.discard(name)  # Remove from not found set
        except (KeyError, IndexError) as e:
            raise ValueError(f"Error processing orders response: {e}")
    if orders_not_found:
        raise ValueError(f"Orders not found: {', '.join(orders_not_found)}")
    return name_to_id


def generate_invoices(input_file: Path, out_dir: Path):
    """Generate invoices from a file containing order names"""
    try:
        # Read order names from file
        with open(input_file, "r") as file:
            order_names = [line.strip() for line in file if line.strip()]

        print(f"Looking up IDs for {len(order_names)} orders...")

        try:
            # First get all order IDs
            name_to_id = get_order_ids_from_names(order_names)

            # Then generate invoices using existing functions
            for name, order_id in name_to_id.items():
                print(f"Processing order {name}")
                try:
                    create_e_invoice_lut(out_dir, order_id)
                except Exception as e:
                    print(f"Error generating invoice for order {name}: {e}")
                    continue

            print("All invoices generated successfully.")

        except ValueError as e:
            print(f"Error looking up orders: {e}")
            return

    except FileNotFoundError:
        print(f"Input file '{input_file}' not found at {input_file.absolute()}")
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        import traceback

        traceback.print_exc()


def main(input_file: Path, out_dir: Path):
    generate_invoices(input_file, out_dir)


if __name__ == "__main__":
    main()
