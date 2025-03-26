import json
import os
from decimal import ROUND_HALF_UP, Decimal

from dateutil import parser

from api_client import graphql_request

SHOPIFY_STORE = os.getenv("SHOPIFY_STORE")
API_TOKEN = os.getenv("API_TOKEN")


def get_shopify_order(order_id):
    query = f"""
    {{
      order(id: "gid://shopify/Order/{order_id}") {{
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
        lineItems(first: 100) {{ # Assuming max 100 line items per order
          edges {{
            node {{
              title
              quantity
              originalUnitPriceSet {{
                shopMoney {{
                  amount
                }}
              }}
              variant {{
                id
                inventoryItem {{
                  id
                  harmonizedSystemCode
                }}
              }}
            }}
          }}
        }}
      }}
    }}
    """
    response_data = graphql_request(query)
    if response_data and "data" in response_data and "order" in response_data["data"]:
        return response_data["data"]["order"]
    else:
        # Handle cases where order is not found or other GraphQL errors occurred
        print(f"Error fetching order {order_id}: {response_data.get('errors')}")
        raise ValueError(f"Could not fetch order details for ID: {order_id}")


def generate_gst_invoice_data(shopify_order, seller_details):
    shipping_amount = Decimal(
        shopify_order.get("totalShippingPriceSet", {})
        .get("shopMoney", {})
        .get("amount", "0.00")
    )
    customer = shopify_order.get("customer", {}) or {}
    shipping_address = shopify_order.get("shippingAddress", {}) or {}
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
            "LglNm": f"{customer.get('firstName', '')} {customer.get('lastName', '')}".strip(),
            "Pos": "96",
            "Addr1": shipping_address.get("address1", ""),
            "Addr2": shipping_address.get("address2", ""),
            "Loc": shipping_address.get("city", ""),
            "Pin": "999999",  # Assuming fixed PIN for export
            "Stcd": "96",  # Assuming fixed state code for export
            "Ph": None,  # Phone not typically available/needed here
            "Em": None,  # Email not typically available/needed here
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

    line_items = shopify_order.get("lineItems", {}).get("edges", [])
    for idx, edge in enumerate(line_items):
        item = edge.get("node", {})
        if not item:
            continue

        variant = item.get("variant") or {}
        inventory_item = variant.get("inventoryItem") or {}
        hsn_code = inventory_item.get("harmonizedSystemCode") or "00000000"
        if not hsn_code:  # Ensure empty string is also treated as default
            hsn_code = "00000000"

        quantity = Decimal(item.get("quantity", 1))
        unit_price = Decimal(
            item.get("originalUnitPriceSet", {})
            .get("shopMoney", {})
            .get("amount", "0.00")
        )
        total_amount = (unit_price * quantity).quantize(
            Decimal("0.00"), rounding=ROUND_HALF_UP
        )
        invoice_data["ItemList"].append(
            {
                "SlNo": str(idx + 1),
                "PrdDesc": item.get("title", ""),
                "IsServc": "N",
                "HsnCd": hsn_code,
                "Barcde": "",  # Barcode not directly available in this query structure
                "Qty": quantity,
                "FreeQty": Decimal("0.00"),
                "Unit": "PCS",  # Assuming PCS, adjust if needed
                "UnitPrice": unit_price,
                "TotAmt": total_amount,
                "Discount": Decimal("0.00"),
                "PreTaxVal": total_amount,  # Assuming price is pre-tax for export
                "AssAmt": total_amount,
                "GstRt": Decimal("0.00"),  # Assuming 0% GST for export under LUT
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
    # Using original numeric order ID for filename consistency
    numeric_order_id = invoice_data["DocDtls"]["No"].replace(
        "#", ""
    )  # Ensure clean number if prefix exists
    file_name = f"gst_export_invoice_lut_{numeric_order_id}.json"
    with open(file_name, "w") as json_file:
        json.dump(invoice_data, json_file, indent=4, default=str)
    print(f"GST export e-invoice (LUT) saved as {file_name}")


def create_e_invoice_lut(order_id):
    try:
        seller_details = load_seller_details()
        # Pass the numeric order ID to get_shopify_order
        shopify_order = get_shopify_order(order_id)
        invoice_data = generate_gst_invoice_data(shopify_order, seller_details)
        save_invoice_to_json(invoice_data, order_id)  # Pass original ID for context
    except ValueError as ve:
        print(f"Skipping order {order_id}: {ve}")
    except Exception as e:
        print(f"Failed to process order {order_id}: {e}")


def main(input_file="order_ids.txt"):
    try:
        with open(input_file, "r") as file:
            # Ensure only numeric IDs are processed
            order_ids = [line.strip() for line in file if line.strip().isdigit()]

        if not order_ids:
            print(f"No valid numeric order IDs found in '{input_file}'.")
            return

        for order_id in order_ids:
            print(f"Processing order ID: {order_id}")
            create_e_invoice_lut(order_id)
        print("Invoice generation process completed.")

    except FileNotFoundError:
        print(f"Input file '{input_file}' not found.")
    except Exception as e:
        print(f"An unexpected error occurred during processing: {e}")


if __name__ == "__main__":
    main()
