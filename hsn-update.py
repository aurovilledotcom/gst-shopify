import os
import time

import pandas as pd
import requests
from requests.exceptions import ConnectionError

SHOPIFY_STORE = os.getenv("SHOPIFY_STORE")
API_TOKEN = os.getenv("API_TOKEN")

QUERY_BATCH_SIZE = 100  # Larger batch size for queries
UPDATE_BATCH_SIZE = 3  # Smaller batch size for updates

data = pd.read_csv("hsn-codes.csv")  # CSV with columns: SKU, HSN_Code
sku_hsn_map = dict(zip(data["sku"], data["hsncode"]))


def graphql_request(query, max_retries=5):
    url = f"https://{SHOPIFY_STORE}/admin/api/2024-10/graphql.json"
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": API_TOKEN,
        "User-Agent": "python-requests",
    }
    retries = 0
    while retries < max_retries:
        try:
            response = requests.post(
                url, json={"query": query}, headers=headers, timeout=10
            )

            #            api_call_limit = response.headers.get("X-Shopify-Shop-Api-Call-Limit")
            #            print(f"API call limit: {api_call_limit}")
            #            api_cost = response.headers.get("X-GraphQL-Cost-Incurred")
            #            print(f"API request cost: {api_cost}")

            response.raise_for_status()
            response_data = response.json()

            if "errors" in response_data:
                print(f"GraphQL errors: {response_data['errors']}")

            return response_data
        except requests.exceptions.HTTPError as http_err:
            if response.status_code == 429:  # Too many requests
                retry_after = response.headers.get(
                    "Retry-After", 5
                )  # Default to 5 seconds if not provided
                print(f"Rate limit hit. Retrying after {retry_after} seconds...")
                time.sleep(int(retry_after))
            else:
                print(f"HTTP error occurred: {http_err}")
                print(
                    f"Response content: {response.text}"
                )  # Capture and log error details from response
            break
        except requests.exceptions.RequestException as err:
            print(f"Connection error: {err}. Retrying...")
            retries += 1
            time.sleep(2**retries)  # Exponential backoff
    raise Exception("Max retries reached. Connection failed.")


def generate_inventory_query(first=50, after=None):
    after_str = f', after: "{after}"' if after else ""
    return f"""
    query {{
        productVariants(first: {first}{after_str}) {{
            edges {{
                node {{
                    sku
                    inventoryItem {{
                        id
                        harmonizedSystemCode
                    }}
                }}
            }}
            pageInfo {{
                hasNextPage
                endCursor
            }}
        }}
    }}
    """


def generate_hsn_mutation(inventory_item_id, hsn_code, index):
    return f"""
    updateInventoryItem_{index}: inventoryItemUpdate(
        id: "{inventory_item_id}",
        input: {{
            harmonizedSystemCode: "{hsn_code}"
        }}
    ) {{
        inventoryItem {{
            id
            harmonizedSystemCode
        }}
        userErrors {{
            message
        }}
    }}
    """


def batch_update_hsn_codes(inventory_item_ids, hsn_codes):
    total_updates = len(inventory_item_ids)
    for i in range(0, total_updates, UPDATE_BATCH_SIZE):
        mutations = []
        batch_inventory_item_ids = inventory_item_ids[i : i + UPDATE_BATCH_SIZE]
        batch_hsn_codes = hsn_codes[i : i + UPDATE_BATCH_SIZE]

        for idx, (inventory_item_id, hsn_code) in enumerate(
            zip(batch_inventory_item_ids, batch_hsn_codes)
        ):
            mutations.append(generate_hsn_mutation(inventory_item_id, hsn_code, idx))

        if mutations:
            mutation_query = "mutation {\n" + "\n".join(mutations) + "\n}"
            graphql_request(mutation_query)


def process_inventory_items():
    total_processed = 0
    has_next_page = True
    end_cursor = None

    while has_next_page:
        query = generate_inventory_query(first=QUERY_BATCH_SIZE, after=end_cursor)
        response = graphql_request(query)

        product_variants = response["data"]["productVariants"]["edges"]
        page_info = response["data"]["productVariants"]["pageInfo"]

        inventory_item_ids = []
        hsn_codes = []

        for variant in product_variants:
            sku = variant["node"]["sku"]
            current_hsn_code = variant["node"]["inventoryItem"]["harmonizedSystemCode"]
            if sku in sku_hsn_map and (not current_hsn_code or current_hsn_code == ""):
                inventory_item_id = variant["node"]["inventoryItem"]["id"]
                hsn_code = sku_hsn_map[sku]
                inventory_item_ids.append(inventory_item_id)
                hsn_codes.append(hsn_code)

        if inventory_item_ids:
            batch_update_hsn_codes(inventory_item_ids, hsn_codes)
            total_processed += len(inventory_item_ids)

        print(f"Total processed so far: {total_processed}")

        has_next_page = page_info["hasNextPage"]
        end_cursor = page_info["endCursor"]

        time.sleep(2)


def main():
    print("Processing inventory items and updating HSN codes...")
    process_inventory_items()
    print("Update complete!")


if __name__ == "__main__":
    main()
