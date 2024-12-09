from pathlib import Path

import typer
from typing_extensions import Annotated

app = typer.Typer(help="CLI tools for Indian GST compliance with Shopify stores")


@app.command()
def query_hsn(
    output_file: Annotated[
        Path, typer.Option(help="Output file for HSN code report")
    ] = Path("unique_hsn_codes.csv"),
):
    """Generate report of unique HSN codes in use"""
    from gst_shopify.hsn_query import save_unique_hsn_codes_to_csv

    save_unique_hsn_codes_to_csv(output_file)


@app.command()
def update_hsn(
    input_file: Annotated[
        Path, typer.Argument(help="CSV file containing SKU to HSN mappings")
    ] = Path("hsn-codes.csv"),
    qry_batch_size: Annotated[
        int, typer.Option(help="Number of query items to process per batch")
    ] = 250,
):
    """Update HSN codes for products based on CSV mapping file"""
    from gst_shopify.hsn_update import process_inventory_items

    process_inventory_items(input_file, qry_batch_size)


@app.command()
def generate_e_invoice(
    order_ids: Annotated[Path, typer.Argument(help="Text file containing order IDs")],
    output_dir: Annotated[
        Path, typer.Option(help="Directory for generated invoices")
    ] = Path("invoices"),
):
    """Generate GST invoices for specified orders"""
    from gst_shopify.e_invoice_exp_lut import generate_invoices

    generate_invoices(order_ids, output_dir)


if __name__ == "__main__":
    app()
