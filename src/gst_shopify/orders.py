from gst_shopify.api_client import graphql_request

QUERY_BATCH_SIZE = 250


def get_order_ids_from_names(order_names, batch_size=QUERY_BATCH_SIZE):
    """
    Look up multiple Shopify order IDs using order names in batches.

    Args:
        order_names: List of order names (e.g., ["#1001", "#1002"])
        batch_size: Number of orders to query in each batch

    Returns:
        dict: Mapping of order names to their IDs
    """
    name_to_id = {}
    orders_not_found = set(order_names)

    for i in range(0, len(order_names), batch_size):
        batch = order_names[i : i + batch_size]
        query_str = " OR ".join(f"name:{name}" for name in batch)

        query = f"""
        {{
            orders(first: {batch_size}, query: "{query_str}") {{
                edges {{
                    node {{
                        id
                        name
                    }}
                }}
            }}
        }}
        """
        response = graphql_request(query)
        try:
            orders = response["data"]["orders"]["edges"]
            for order in orders:
                name = order["node"]["name"]
                order_id = order["node"]["id"].split("/")[-1]
                name_to_id[name] = order_id
                orders_not_found.discard(name)  # Remove from not found set
        except (KeyError, IndexError) as e:
            raise ValueError(f"Error processing orders response: {e}")

    if orders_not_found:
        raise ValueError(f"Orders not found: {', '.join(orders_not_found)}")

    return name_to_id


def get_complete_order_details(order_id):
    """
    Fetch comprehensive order details including all fields needed for both
    Tally exports and e-invoice generation

    Args:
        order_id: The Shopify order ID (numeric part only)

    Returns:
        dict: Complete order information
    """
    query = """
    {
      order(id: "gid://shopify/Order/ORDER_ID") {
        id
        name
        createdAt
        processedAt
        cancelledAt
        
        # Financial details
        totalPriceSet { shopMoney { amount currencyCode } }
        subtotalPriceSet { shopMoney { amount currencyCode } }
        totalTaxSet { shopMoney { amount currencyCode } }
        totalShippingPriceSet { shopMoney { amount currencyCode } }
        totalDiscountsSet { shopMoney { amount currencyCode } }
        
        # Customer details
        customer {
          firstName
          lastName
          email
          phone
          defaultAddress {
            address1
            address2
            city
            province
            provinceCode
            zip
            country
            countryCode
            phone
          }
        }
        
        # Address details
        shippingAddress {
          address1
          address2
          city
          province
          provinceCode
          zip
          country
          countryCode
          phone
          name
          company
        }
        
        billingAddress {
          address1
          address2
          city
          province
          provinceCode
          zip
          country
          countryCode
          phone
          name
          company
        }
        
        # Tax information
        taxExempt
        taxesIncluded
        taxLines {
          title
          rate
          priceSet { shopMoney { amount } }
        }
        
        # Line items with details
        lineItems(first: 50) {
          edges {
            node {
              id
              name
              quantity
              sku
              requiresShipping
              fulfillmentStatus
              fulfillableQuantity
              vendor
              title
              variantTitle
              
              variant {
                id
                price
                sku
                title
                inventoryItem {
                  harmonizedSystemCode
                  tracked
                }
              }
              
              discountedTotalSet { shopMoney { amount } }
              originalTotalSet { shopMoney { amount } }
              totalDiscountSet { shopMoney { amount } }
              
              taxLines {
                title
                rate
                priceSet { shopMoney { amount } }
              }
            }
          }
        }
        
        # Fulfillment information
        fulfillments(first: 10) {
          id
          status
          createdAt
          trackingInfo {
            number
            url
            company
          }
        }
        
        # Payment information
        transactions(first: 10) {
          id
          gateway
          kind
          status
          processedAt
          amountSet { shopMoney { amount currencyCode } }
          paymentId
        }
      }
    }
    """.replace("ORDER_ID", order_id)

    response = graphql_request(query)

    if not response.get("data") or not response["data"].get("order"):
        raise ValueError(f"Order {order_id} not found")

    return response["data"]["order"]