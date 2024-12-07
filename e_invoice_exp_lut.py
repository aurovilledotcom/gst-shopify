import base64
import json
import os
from decimal import ROUND_HALF_UP, Decimal

from dateutil import parser

from api_client import graphql_request

SHOPIFY_STORE = os.getenv("SHOPIFY_STORE")
API_TOKEN = os.getenv("API_TOKEN")


def encode_shopify_id(id):
    return base64.b64encode(id.encode()).decode()


def get_shopify_order(order_id):
    shopify_order_id = encode_shopify_id(f"gid://shopify/Order/{order_id}")

    query = f"""
    query {{
        order(id: "{shopify_order_id}") {{
            id
            name
            createdAt
            customer {{
                firstName
                lastName
            }}
            shippingAddress {{
                address1
                address2
                city
            }}
            totalShippingPriceSet {{
                shopMoney {{
                    amount
                }}
            }}
            lineItems(first: 250) {{
                edges {{
                    node {{
                        id
                        variant {{
                            id
                            inventoryItem {{
                                id
                                hsCode: harmonizedSystemCode
                            }}
                        }}
                        title
                        quantity
                        originalUnitPrice
                    }}
                }}
            }}
        }}
    }}
    """

    response = graphql_request(query, max_retries=5)
    if "errors" in response:
        raise Exception(f"GraphQL errors: {response['errors']}")
    return response["data"]["order"]


def generate_gst_invoice_data(shopify_order, seller_details):
    shipping_amount = Decimal(
        shopify_order["totalShippingPriceSet"]["shopMoney"]["amount"]
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
            "Dt": parser.parse(shopify_order["createdAt"]).strftime("%d/%m/%Y"),
        },
        "SellerDtls": seller_details,
        "BuyerDtls": {
            "Gstin": "URP",
            "LglNm": f"{shopify_order['customer']['firstName']} {shopify_order['customer']['lastName']}",
            "Pos": "96",
            "Addr1": shopify_order["shippingAddress"]["address1"],
            "Addr2": shopify_order["shippingAddress"]["address2"],
            "Loc": shopify_order["shippingAddress"]["city"],
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

    for idx, item in enumerate(shopify_order["lineItems"]["edges"]):
        node = item["node"]
        hsn_code = (
            node["variant"]["inventoryItem"]["hsCode"]
            if node["variant"]["inventoryItem"]["hsCode"]
            else "00000000"
        )

        quantity = Decimal(node["quantity"])
        unit_price = Decimal(node["originalUnitPrice"])
        total_amount = (unit_price * quantity).quantize(
            Decimal("0.00"), rounding=ROUND_HALF_UP
        )

        invoice_data["ItemList"].append(
            {
                "SlNo": str(idx + 1),
                "PrdDesc": node["title"],
                "IsServc": "N",
                "HsnCd": hsn_code,
                "Barcde": node.get("barcode", ""),
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
