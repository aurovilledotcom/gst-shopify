from pathlib import Path

import typer
from typing_extensions import Annotated

from gst_shopify.e_invoice_exp_lut import generate_invoices

app = typer.Typer(help="Generate GST e-invoices for Shopify orders")


@app.command()
def main(
    order_ids: Annotated[Path, typer.Argument()] = Path("order_ids.txt"),
    output_dir: Annotated[
        Path, typer.Option("--output", "-o", help="Directory for generated invoices")
    ] = Path("invoices"),
):
    """Generate GST invoices for specified orders"""
    generate_invoices(order_ids, output_dir)


if __name__ == "__main__":
    app()
