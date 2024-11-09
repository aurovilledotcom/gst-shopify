import os
import time

import requests

SHOPIFY_STORE = os.getenv("SHOPIFY_STORE")
API_TOKEN = os.getenv("API_TOKEN")


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
