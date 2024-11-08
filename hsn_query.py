import pandas as pd

from shopify_api import graphql_request

QUERY_BATCH_SIZE = 250


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
                    product {{
                        status  # Include product status to filter archived products
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


def get_unique_hsn_codes():
    """Fetch all products and return a list of unique HSN codes."""
    unique_hsn_codes = set()
    has_next_page = True
    end_cursor = None
    page_count = 0

    while has_next_page:
        query = generate_inventory_query(first=QUERY_BATCH_SIZE, after=end_cursor)
        response = graphql_request(query)

        product_variants = response["data"]["productVariants"]["edges"]
        page_info = response["data"]["productVariants"]["pageInfo"]

        for variant in product_variants:
            hsn_code = variant["node"]["inventoryItem"]["harmonizedSystemCode"]
            if hsn_code:
                unique_hsn_codes.add(hsn_code)

        page_count += 1
        print(
            f"Processed page {page_count}, unique HSN codes found: {len(unique_hsn_codes)}"
        )

        has_next_page = page_info["hasNextPage"]
        end_cursor = page_info["endCursor"]

    return sorted(unique_hsn_codes)


def list_invalid_hsn_codes():
    """List all product variants with empty, blank, or invalid HSN codes."""
    invalid_hsn_variants = []
    has_next_page = True
    end_cursor = None
    page_count = 0

    while has_next_page:
        query = generate_inventory_query(first=QUERY_BATCH_SIZE, after=end_cursor)
        response = graphql_request(query)

        product_variants = response["data"]["productVariants"]["edges"]
        page_info = response["data"]["productVariants"]["pageInfo"]

        for variant in product_variants:
            product_status = variant["node"]["product"]["status"]
            if product_status == "ARCHIVED":
                continue  # Skip archived products

            sku = variant["node"]["sku"]
            hsn_code = variant["node"]["inventoryItem"]["harmonizedSystemCode"]

            if not hsn_code or len(hsn_code) not in {6, 8}:
                invalid_hsn_variants.append(
                    {
                        "sku": sku,
                        "hsn_code": hsn_code or "Blank",
                    }
                )

        page_count += 1
        print(
            f"Processed page {page_count}, invalid HSN codes found so far: {len(invalid_hsn_variants)}"
        )

        has_next_page = page_info["hasNextPage"]
        end_cursor = page_info["endCursor"]

    return invalid_hsn_variants


def save_unique_hsn_codes_to_csv(output_file="unique_hsn_codes.csv"):
    """Fetch unique HSN codes and save them to a CSV file."""
    unique_hsn_codes = get_unique_hsn_codes()
    unique_hsn_df = pd.DataFrame(unique_hsn_codes, columns=["HSN_Code"])
    unique_hsn_df.to_csv(output_file, index=False)
    print(f"Unique HSN codes saved to {output_file}")


def save_variants_to_csv(output_file="bad_variants.csv"):
    invalid_hsn_codes = list_invalid_hsn_codes()
    invalid_hsn_df = pd.DataFrame(invalid_hsn_codes, columns=["sku", "hsn_code"])
    invalid_hsn_df.to_csv(output_file, index=False)
    print(f"Invalid HSN codes saved to {output_file}")


if __name__ == "__main__":
    #    save_unique_hsn_codes_to_csv()
    save_variants_to_csv()
