def build_product_context(products: list) -> str:
    blocks = []

    for i, p in enumerate(products, 1):
        specs = p.get("specifications", {})
        specs_text = "\n".join(
            f"- {k}: {v}" for k, v in specs.items()
        ) if isinstance(specs, dict) else "Not available"

        block = f"""
Product {i}:
- Product ID: {p.get("pid")}
- Brand: {p.get("brand")}
- Category: {p.get("category")}
- Price: {p.get("price")}
- Specifications:
{specs_text}
"""
        blocks.append(block)

    return "\n".join(blocks)