import json
import os
from decimal import ROUND_HALF_UP, Decimal

from dateutil import parser

from api_client import graphql_request  # Using our GraphQL wrapper

SHOPIFY_STORE = os.getenv("SHOPIFY_STORE")
API_TOKEN = os.getenv("API_TOKEN")


def get_shopify_order(order_id):
    # Convert the order_id to Shopify’s global ID format.
    order_gid = f"gid://shopify/Order/{order_id}"
    query = f"""
    query getOrder {{
      order(id: "{order_gid}") {{
        name
        createdAt
        totalShippingPriceSet {{
          shopMoney {{
            amount
          }}
        }}
        customer {{
          firstName
          lastName
        }}
        shippingAddress {{
          address1
          address2
          city
        }}
        lineItems(first: 50) {{
          edges {{
            node {{
              title
              quantity
              variant {{
                price
                barcode
                inventoryItem {{
                  harmonizedSystemCode
                }}
              }}
            }}
          }}
        }}
      }}
    }}
    """
    response_data = graphql_request(query, max_retries=5)
    order = response_data.get("data", {}).get("order")
    if not order:
        raise Exception("Order not found.")

    # Process line items: flatten edges and include HSN code directly.
    line_items = []
    for edge in order["lineItems"]["edges"]:
        node = edge["node"]
        variant = node.get("variant") or {}
        line_item = {
            "title": node.get("title", ""),
            "quantity": node.get("quantity", 1),
            "price": variant.get("price", "0.00"),
            "barcode": variant.get("barcode", ""),
            "hsn_code": variant.get("inventoryItem", {}).get(
                "harmonizedSystemCode", "00000000"
            ),
        }
        line_items.append(line_item)

    # Reconstruct the order structure to be compatible with generate_gst_invoice_data.
    shopify_order = {
        "name": order.get("name"),
        "created_at": order.get("createdAt"),
        "total_shipping_price_set": order.get("totalShippingPriceSet"),
        "customer": {
            "first_name": order.get("customer", {}).get("firstName", ""),
            "last_name": order.get("customer", {}).get("lastName", ""),
        },
        "shipping_address": order.get("shippingAddress", {}),
        "line_items": line_items,
    }
    return shopify_order


def generate_gst_invoice_data(shopify_order, seller_details):
    shipping_amount = Decimal(
        shopify_order.get("total_shipping_price_set", {})
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
        hsn_code = item.get("hsn_code", "00000000")
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
