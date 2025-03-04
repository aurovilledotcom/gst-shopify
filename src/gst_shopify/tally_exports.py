import jinja2
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from gst_shopify.orders import get_complete_order_details, get_order_ids_from_names


def format_tally_date(date_str):
    """Convert ISO date string to Tally date format (YYYYMMDD)"""
    if isinstance(date_str, str):
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%Y%m%d")
    return date_str.strftime("%Y%m%d")


def prepare_sales_data(order):
    """Transform GraphQL order data into format needed for sales XML template"""
    # Extract customer name
    first_name = order.get("customer", {}).get("firstName", "")
    last_name = order.get("customer", {}).get("lastName", "")
    customer_name = f"{first_name} {last_name}".strip()
    if not customer_name:
        customer_name = "Guest Customer"

    # Extract shipping address
    shipping = order.get("shippingAddress", {})
    address_parts = []
    if shipping.get("address1"):
        address_parts.append(shipping["address1"])
    if shipping.get("address2"):
        address_parts.append(shipping["address2"])
    address = ", ".join(address_parts)

    # Extract pricing
    subtotal = float(
        order.get("subtotalPriceSet", {}).get("shopMoney", {}).get("amount", "0")
    )
    total = float(
        order.get("totalPriceSet", {}).get("shopMoney", {}).get("amount", "0")
    )

    # Calculate tax amounts - adjust based on your tax structure
    tax_lines = order.get("taxLines", [])
    igst_amount = 0
    cgst_amount = 0
    sgst_amount = 0

    for tax in tax_lines:
        tax_title = tax.get("title", "").upper()
        tax_amount = float(
            tax.get("priceSet", {}).get("shopMoney", {}).get("amount", "0")
        )

        if "IGST" in tax_title:
            igst_amount += tax_amount
        elif "CGST" in tax_title:
            cgst_amount += tax_amount
        elif "SGST" in tax_title:
            sgst_amount += tax_amount

    # If no specific GST breakup is available, allocate to IGST for simplicity
    # This should be adjusted based on your business needs
    total_tax = float(
        order.get("totalTaxSet", {}).get("shopMoney", {}).get("amount", "0")
    )
    if not any([igst_amount, cgst_amount, sgst_amount]) and total_tax > 0:
        # Assuming exports use IGST
        igst_amount = total_tax

    # Extract line items
    line_items = []
    for edge in order.get("lineItems", {}).get("edges", []):
        node = edge["node"]
        variant = node.get("variant", {})

        item = {
            "name": node["name"],
            "quantity": float(node["quantity"]),
            "price": float(variant.get("price", "0")),
            "hsn_code": variant.get("inventoryItem", {}).get(
                "harmonizedSystemCode", "00000000"
            ),
            "total": float(
                node.get("discountedTotalSet", {})
                .get("shopMoney", {})
                .get("amount", "0")
            ),
        }
        line_items.append(item)

    # Determine place of supply (adjust based on your requirements)
    # Here we use a simple mapping - this would need to be customized for your needs
    state_code_map = {
        "Karnataka": "29",
        "Maharashtra": "27",
        # Add more state mappings as needed
    }
    province = shipping.get("province", "")
    place_of_supply = state_code_map.get(province, "96")  # Default to foreign (96)

    return {
        "company_name": "Your Company Name",  # Replace with actual company name from config
        "order_date": order["createdAt"],
        "order_name": order["name"].replace("#", ""),
        "customer_name": customer_name,
        "customer_gstin": "",  # Add logic to extract GSTIN if available
        "place_of_supply": place_of_supply,
        "customer_address": address,
        "customer_state": shipping.get("province", ""),
        "subtotal": subtotal,
        "total": total,
        "igst_amount": igst_amount,
        "cgst_amount": cgst_amount,
        "sgst_amount": sgst_amount,
        "line_items": line_items,
    }


def prepare_payment_data(order, transaction):
    """Transform GraphQL transaction data into format needed for payment XML template"""
    # Extract customer name from order
    first_name = order.get("customer", {}).get("firstName", "")
    last_name = order.get("customer", {}).get("lastName", "")
    customer_name = f"{first_name} {last_name}".strip()
    if not customer_name:
        customer_name = "Guest Customer"

    # Extract payment details
    payment_id = transaction["id"].split("/")[-1]  # Extract numeric ID
    gateway = transaction.get("gateway", "")
    payment_amount = float(
        transaction.get("amountSet", {}).get("shopMoney", {}).get("amount", "0")
    )

    # Map gateway to Tally account name - customize for your setup
    gateway_account_map = {
        "razorpay": "Razorpay Account",
        "shopify_payments": "Shopify Payments Account",
        # Add more gateway mappings as needed
    }

    payment_account = gateway_account_map.get(gateway.lower(), f"{gateway} Account")

    return {
        "company_name": "Your Company Name",  # Replace with actual company name from config
        "payment_date": transaction["processedAt"],
        "payment_id": payment_id,
        "gateway_ref": transaction.get("paymentId", ""),  # Using paymentId instead of authorization
        "customer_name": customer_name,
        "order_name": order["name"].replace("#", ""),
        "payment_amount": payment_amount,
        "payment_method": gateway,
        "payment_account": payment_account,
    }


def generate_tally_xml(order_id, output_dir=Path("tally_imports")):
    """
    Generate Tally XML import files for an order and its payments

    Args:
        order_id: Shopify order ID
        output_dir: Directory to save XML files

    Returns:
        dict: Paths to generated files
    """
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create Jinja environment
    template_dir = Path(__file__).parent / "templates"
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(template_dir),
        autoescape=jinja2.select_autoescape(["xml"]),
    )
    env.filters["format_date"] = format_tally_date

    # Load templates
    sales_template = env.get_template("sales_voucher.xml.j2")
    payment_template = env.get_template("payment_voucher.xml.j2")

    # Get order details with GraphQL
    order = get_complete_order_details(order_id)

    # Prepare data for sales voucher
    sales_data = prepare_sales_data(order)

    # Generate sales voucher XML
    sales_xml = sales_template.render(**sales_data)
    sales_file = output_dir / f"sales_{order['name'].replace('#', '')}.xml"
    with open(sales_file, "w", encoding="utf-8") as f:
        f.write(sales_xml)

    # Generate payment voucher XML for each successful payment transaction
    payment_files = []

    for transaction in order.get("transactions", []):
        # Only process successful payment transactions
        if transaction.get("kind") == "SALE" and transaction.get("status") == "SUCCESS":
            payment_data = prepare_payment_data(order, transaction)

            payment_xml = payment_template.render(**payment_data)
            payment_file = (
                output_dir
                / f"payment_{order['name'].replace('#', '')}_{payment_data['payment_id']}.xml"
            )
            with open(payment_file, "w", encoding="utf-8") as f:
                f.write(payment_xml)

            payment_files.append(payment_file)

    return {"sales_file": sales_file, "payment_files": payment_files}


def process_order_by_id(order_id, output_dir=Path("tally_imports")):
    """
    Process a single order by its ID and generate Tally import files

    Args:
        order_id: Shopify order ID (numeric)
        output_dir: Directory to save output files

    Returns:
        dict: Paths to generated files
    """
    try:
        print(f"Processing order ID {order_id} for Tally import...")
        result = generate_tally_xml(order_id, output_dir)

        print(f"Sales voucher XML generated: {result['sales_file']}")
        for payment_file in result["payment_files"]:
            print(f"Payment voucher XML generated: {payment_file}")

        return result
    except Exception as e:
        print(f"Error processing order ID {order_id}: {str(e)}")
        import traceback

        traceback.print_exc()
        return None


def process_order_by_name(order_name, output_dir=Path("tally_imports")):
    """
    Process a single order by its name (e.g., "#1001") and generate Tally import files

    Args:
        order_name: Shopify order name including # symbol (e.g., "#1001")
        output_dir: Directory to save output files

    Returns:
        dict: Paths to generated files
    """
    try:
        print(f"Looking up order ID for {order_name}...")
        # Get order ID from name
        name_to_id = get_order_ids_from_names([order_name])
        if order_name not in name_to_id:
            raise ValueError(f"Order {order_name} not found")

        order_id = name_to_id[order_name]
        print(f"Found order ID: {order_id}")
        return process_order_by_id(order_id, output_dir)
    except Exception as e:
        print(f"Error processing order name {order_name}: {str(e)}")
        import traceback

        traceback.print_exc()
        return None


if __name__ == "__main__":
    process_order_by_name("#AURO69593")
