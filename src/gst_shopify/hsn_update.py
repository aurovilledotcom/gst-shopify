import time
from pathlib import Path

import pandas as pd

from gst_shopify.api_client import graphql_request

QUERY_BATCH_SIZE = 250  # Larger batch size for queries
UPDATE_BATCH_SIZE = 3  # Smaller batch size for updates


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


def process_inventory_items(input_file: Path, qry_batch_size: int):
    print("Processing inventory items and updating HSN codes...")

    data = pd.read_csv(input_file, dtype={"hsncode": "string"})
    sku_hsn_map = dict(zip(data["sku"], data["hsncode"]))

    total_processed = 0
    has_next_page = True
    end_cursor = None

    while has_next_page:
        query = generate_inventory_query(first=qry_batch_size, after=end_cursor)
        response = graphql_request(query)

        product_variants = response["data"]["productVariants"]["edges"]
        page_info = response["data"]["productVariants"]["pageInfo"]

        inventory_item_ids = []
        hsn_codes = []

        for variant in product_variants:
            sku = variant["node"]["sku"]
            current_hsn_code = variant["node"]["inventoryItem"]["harmonizedSystemCode"]
            if sku in sku_hsn_map and (
                not current_hsn_code or current_hsn_code != sku_hsn_map[sku]
            ):
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

    print("Update complete!")


def main():
    process_inventory_items()


if __name__ == "__main__":
    main()
