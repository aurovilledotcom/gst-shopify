# GST-Shopify

The `gst-shopify` repository contains tools for managing GST compliance for Shopify stores, including updating Harmonized System of Nomenclature (HSN) codes for inventory items. 

## Features

- **HSN Code Update**: Batch processing for updating HSN codes in Shopify inventory.

## Getting Started

### Prerequisites

- Python 3.12+
- [Poetry](https://python-poetry.org/) for dependency management

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
   - `API_TOKEN`: Access token for Shopify's Admin API with appropriate permissions

   These variables can be stored in a `.env` file in the root directory for convenience.

### HSN Code Update

The `hsn-update.py` script reads HSN codes from a CSV file and updates Shopify inventory items in batches. This script is useful for ensuring that all products in your store have accurate HSN codes for tax compliance.

#### CSV Format

The CSV file (default: `hsn-codes.csv`) should include two columns:

- `SKU`: The SKU (Stock Keeping Unit) of the product variant.
- `HSN_Code`: The HSN code to assign to that SKU.

Example CSV:
```csv
SKU,HSN_Code
SKU123,1001
SKU456,2002
SKU789,3003
```

#### Running the Script

To execute the HSN update script, run:

```bash
poetry run python hsn-update.py
```

This script performs the following steps:

1. **Load Data**: Reads the CSV file and maps SKUs to their corresponding HSN codes.
2. **Fetch Inventory**: Retrieves product variants from Shopify in batches.
3. **Update HSN Codes**: Sends batch requests to update HSN codes for items missing or with incorrect HSN codes.

#### Script Parameters

- `QUERY_BATCH_SIZE`: Number of product variants to fetch per GraphQL query. Adjust based on performance needs.
- `UPDATE_BATCH_SIZE`: Number of HSN codes to update per GraphQL mutation. A smaller size may help avoid rate limits.

#### Error Handling and Retries

The script includes retry logic to handle temporary connection issues and Shopify API rate limits. Errors are printed to the console for review.

## License

This project is licensed under the Apache License 2.0. See the [LICENSE](LICENSE) file for details.
