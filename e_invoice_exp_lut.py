import json
import logging
import os
import time
from decimal import ROUND_HALF_UP, Decimal

import requests
from dateutil import parser

from api_client import graphql_request

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

SHOPIFY_STORE = os.getenv("SHOPIFY_STORE")
API_TOKEN = os.getenv("API_TOKEN")
SELLER_DETAILS_FILE = "config/seller_details.json"
DEFAULT_GSTIN = "33AAATA0037B11O"
DEFAULT_POS = "96"
DEFAULT_STCD = "33"


def get_shopify_order(order_id):
    query = """
    query ($orderId: ID!) {
        node(id: $orderId) {
            ... on Order {
                id
                name
                createdAt
                totalShippingPriceSet {
                    shopMoney {
                        amount
                        currencyCode
                    }
                }
                customer {
                    firstName
                    lastName
                }
                shippingAddress {
                    address1
                    address2
                    city
                    province
                    country
                    zip
                }
                lineItems(first: 250) {
                    edges {
                        node {
                            id
                            title
                            quantity
                            price
                            variant {
                                id
                                inventoryItem {
                                    id
                                    harmonizedSystemCode
                                }
                            }
                            barcode
                        }
                    }
                }
            }
        }
    }
    """
    variables = {"orderId": f"gid://shopify/Order/{order_id}"}
    try:
        response = graphql_request(query, variables=variables)
        node = response.get("data", {}).get("node", {})
        if not node:
            logging.error(f"Order with ID {order_id} not found.")
            return {}
        return node
    except Exception as e:
        logging.error(f"Error fetching order {order_id}: {e}")
        return {}


def generate_gst_invoice_data(shopify_order, seller_details):
    shipping_amount = Decimal(
        shopify_order.get("totalShippingPriceSet", {})
        .get("shopMoney", {})
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
            "No": str(shopify_order.get("name", "")),
            "Dt": parser.parse(shopify_order.get("createdAt", "")).strftime("%d/%m/%Y"),
        },
        "SellerDtls": seller_details,
        "BuyerDtls": {
            "Gstin": "URP",
            "LglNm": f"{shopify_order.get('customer', {}).get('firstName', '')} {shopify_order.get('customer', {}).get('lastName', '')}",
            "Pos": DEFAULT_POS,
            "Addr1": shopify_order.get("shippingAddress", {}).get("address1", ""),
            "Addr2": shopify_order.get("shippingAddress", {}).get("address2", ""),
            "Loc": shopify_order.get("shippingAddress", {}).get("city", ""),
            "Pin": "999999",
            "Stcd": DEFAULT_STCD,
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

    for edge in shopify_order.get("lineItems", {}).get("edges", []):
        node = edge.get("node", {})
        variant = node.get("variant", {})
        inventory_item = variant.get("inventoryItem", {})
        hsn_code = inventory_item.get("harmonizedSystemCode", "00000000")
        barcode = node.get("barcode", "")
        quantity = Decimal(node.get("quantity", 1))
        unit_price = Decimal(node.get("price", "0.00"))
        total_amount = (unit_price * quantity).quantize(
            Decimal("0.00"), rounding=ROUND_HALF_UP
        )
        invoice_data["ItemList"].append(
            {
                "SlNo": str(len(invoice_data["ItemList"]) + 1),
                "PrdDesc": node.get("title", ""),
                "IsServc": "N",
                "HsnCd": hsn_code,
                "Barcde": barcode,
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


def load_seller_details(file_path="config/seller_details.json"):
    with open(file_path, "r") as file:
        return json.load(file)


def save_invoice_to_json(invoice_data, order_id):
    file_name = f"gst_export_invoice_lut_{order_id}.json"
    with open(file_name, "w") as json_file:
        json.dump(invoice_data, json_file, indent=4, default=str)
    print(f"GST export e-invoice (LUT) saved as {file_name}")


def create_e_invoice_lut(order_id):
    seller_details = load_seller_details()
    shopify_order = get_shopify_order(order_id)
    invoice_data = generate_gst_invoice_data(shopify_order, seller_details)
    save_invoice_to_json(invoice_data, order_id)


def main(input_file="order_ids.txt"):
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


if __name__ == "__main__":
    main()
