# GST-Shopify

The `gst-shopify` repository provides tools for managing GST compliance in Shopify stores, focusing on updating Harmonized System of Nomenclature (HSN) codes for inventory items and generating GST-compliant invoices.

> **Note**: This project was developed in collaboration with o1-mini and GPT-4o, using [LLM Context](https://github.com/cyberchitta/llm-context.py). All code in the repository is human-curated (by me 😇, [@restlessronin](https://github.com/restlessronin)).

## Features

1. **HSN Code Update**: Batch processes for updating HSN codes in Shopify inventory items based on SKU mappings from a CSV file.
2. **HSN Code Querying**: Generates reports of unique and invalid HSN codes in inventory.
3. **GST Invoice Generation**: Creates GST-compliant invoices for Shopify orders using seller and order details, with support for e-invoice requirements.

## Getting Started

### Prerequisites

- Python 3.12+
- [Poetry](https://python-poetry.org/) for dependency management
- A valid Shopify Admin API access token with the required permissions.

### Required Shopify API Permissions

To use this project, the following Shopify API permissions are necessary:

- **Orders**: `read_orders`
- **Products**: `read_products`, `write_products` (for updating HSN codes)
- **Inventory**: `read_inventory`, `write_inventory` (for updating inventory HSN codes)

Ensure that your Shopify app or private app is granted these permissions in the Shopify Admin settings.

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/gst-shopify.git
   cd gst-shopify
   ```

2. Install dependencies:
   ```bash
   poetry install
   ```

3. Set up environment variables:
   - `SHOPIFY_STORE`: Your Shopify store’s domain (e.g., `yourstore.myshopify.com`)
   - `API_TOKEN`: Access token for Shopify's Admin API with the required permissions.

   These variables can be stored in a `.env` file in the root directory for convenience.

### Scripts Overview

#### HSN Code Update (`hsn_update.py`)

This script updates Shopify inventory items with HSN codes based on SKU mappings provided in a CSV file. It processes items in batches, fetching items from Shopify, checking current HSN codes, and updating them as needed.

**CSV Format**

The CSV file (default: `hsn-codes.csv`) should include two columns:

- `SKU`: The SKU (Stock Keeping Unit) of the product variant.
- `HSN_Code`: The HSN code to assign to that SKU.

Example:
```csv
SKU,HSN_Code
SKU123,1001
SKU456,2002
SKU789,3003
```

**Running the Script**

```bash
poetry run python hsn_update.py
```

This script performs the following steps:

1. **Load Data**: Reads SKU-HSN mappings from a CSV file.
2. **Fetch Inventory**: Retrieves product variants in batches.
3. **Update HSN Codes**: Sends batch requests to update HSN codes where they are missing or incorrect.

**Script Parameters**

- `QUERY_BATCH_SIZE`: Number of items per GraphQL query (default: 250).
- `UPDATE_BATCH_SIZE`: Number of HSN code updates per GraphQL mutation (default: 3).

#### HSN Code Query (`hsn_query.py`)

This script generates two types of reports:

1. **Unique HSN Codes**: Fetches all unique HSN codes used in Shopify inventory and saves them to `unique_hsn_codes.csv`.
2. **Invalid HSN Codes**: Lists SKUs with missing, blank, or invalid HSN codes and saves them to `bad_variants.csv`.

To execute, run:
```bash
poetry run python hsn_query.py
```

**File Output**

- `unique_hsn_codes.csv`: Contains a list of unique HSN codes.
- `bad_variants.csv`: Contains SKUs and their HSN code status if missing or invalid.

#### GST Invoice Generation (`e_invoice_exp_lut.py`)

This script generates GST-compliant e-invoices for specified Shopify orders, saving each invoice in JSON format.

**Usage**

1. Prepare a text file (`order_ids.txt`) with a list of order IDs.
2. Run:
   ```bash
   poetry run python e_invoice_exp_lut.py
   ```

Each order's JSON invoice file will be saved with the filename `gst_export_invoice_lut_<order_id>.json`.

**Seller Details Configuration**

Seller details for the invoices are read from `config/seller_details.json`. Ensure this file is populated with the relevant business information.

### Error Handling and Retries

All scripts include retry logic to handle Shopify API rate limits and temporary connection issues.

## License

This project is licensed under the Apache License 2.0. See the [LICENSE](LICENSE) file for details.
