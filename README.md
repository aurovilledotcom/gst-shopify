# GST-Shopify

The `gst-shopify` package provides tools for GST compliance in Shopify stores. The main tool generates GST-compliant invoices, with additional development utilities for HSN code management.

> **Note**: This project was developed in collaboration with o1-mini and GPT-4o, using [LLM Context](https://github.com/cyberchitta/llm-context.py). All code in the repository is human-curated (by me 😇, [@restlessronin](https://github.com/restlessronin)).

## Features

### Main Tool
- **GST Invoice Generation**: Creates GST-compliant invoices for Shopify orders using seller and order details, with support for e-invoice requirements.

### Development Utilities
- **HSN Code Update**: Batch processes for updating HSN codes in Shopify inventory items
- **HSN Code Querying**: Generates reports of unique and invalid HSN codes in inventory

## Getting Started

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) for dependency management
- A valid Shopify Admin API access token with the required permissions.

### Required Shopify API Permissions

To use this project, the following Shopify API permissions are necessary:

- **Orders**: `read_orders`
- **Products**: `read_products`
- **Inventory**: `read_inventory`

Additional permissions required for development utilities:
- **Products**: `write_products` (for updating HSN codes)
- **Inventory**: `write_inventory` (for updating inventory HSN codes)

### Installation

1. Install directly from GitHub:
   ```bash
   uv pip install git+https://github.com/aurovilledotcom/gst-shopify.git@release
   ```

2. Set up environment variables:
   - `SHOPIFY_STORE`: Your Shopify store's domain (e.g., `yourstore.myshopify.com`)
   - `API_TOKEN`: Access token for Shopify's Admin API with the required permissions.

   These variables can be stored in a `.env` file in the root directory for convenience.

### Usage

```bash
gen-invoice ORDER_IDS [-o OUTPUT_DIR]
```

Generates GST invoices for specified orders. Parameters:
- `ORDER_IDS`: Text file containing one order ID per line
- `-o, --output`: Directory for generated invoices (default: "invoices")

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

### Development Utilities

When installed in development mode, additional functionality can be accessed by running the Python modules directly:

```bash
# Query HSN codes
uv run python -m gst_shopify.hsn_query [--output-file PATH]

# Update HSN codes
uv run python -m gst_shopify.hsn_update [INPUT_FILE] [--qry-batch-size INTEGER]
```

## License

This project is licensed under the Apache License 2.0. See the [LICENSE](LICENSE) file for details.
