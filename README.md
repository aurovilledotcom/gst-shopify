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
- [uv](https://github.com/astral-sh/uv) for dependency management
- A valid Shopify Admin API access token with the required permissions.

### Required Shopify API Permissions

To use this project, the following Shopify API permissions are necessary:

- **Orders**: `read_orders`
- **Products**: `read_products`, `write_products` (for updating HSN codes)
- **Inventory**: `read_inventory`, `write_inventory` (for updating inventory HSN codes)

Ensure that your Shopify app or private app is granted these permissions in the Shopify Admin settings.

### Installation

1. Install directly from GitHub:
   ```bash
   uv pip install git+https://github.com/aurovilledotcom/gst-shopify.git@release
   ```

### CLI Commands

The package installs a command-line tool `gst-shopify` with the following commands:

#### Query HSN Codes
```bash
uv run gst-shopify query-hsn [--output-file PATH]
```
Generates a report of unique HSN codes in use. The report is saved to the specified output file (default: `unique_hsn_codes.csv`).

#### Update HSN Codes
```bash
uv run gst-shopify update-hsn [INPUT_FILE] [--qry-batch-size INTEGER]
```
Updates HSN codes for products based on SKU mappings from a CSV file. The input file should contain two columns:
- `SKU`: The SKU (Stock Keeping Unit) of the product variant
- `HSN_Code`: The HSN code to assign to that SKU

#### Generate E-Invoices
```bash
uv run gst-shopify generate-e-invoice ORDER_IDS [--output-dir PATH]
```
Generates GST invoices for specified orders. `ORDER_IDS` should be a text file containing one order ID per line.

### Configuration

#### Seller Details
Seller details for the invoices are read from `config/seller_details.json`. Ensure this file is populated with the relevant business information.

### Error Handling and Retries

All operations include retry logic to handle Shopify API rate limits and temporary connection issues.

## Development

For development, install the package with development dependencies:
```bash
uv pip install -e ".[dev]"
```

This will install additional tools like:
- black (code formatting)
- flake8 (linting)
- isort (import sorting)
- mypy (type checking)
- pytest (testing)

## License

This project is licensed under the Apache License 2.0. See the [LICENSE](LICENSE) file for details.
