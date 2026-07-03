"""
Run once to pre-seed the two demo tenants described in the assignment brief.

    python -m app.seed
"""
import asyncio

from app.database import tenants_col
from app.models import MediaLibraryEntry, Tenant
from app.tenant_resolver import refresh_mapping

TENANT_A = Tenant(
    tenant_id="tenant-a",
    name="Luxury Furniture Store",
    prompt_directions=(
        "You are a warm, upscale sales assistant for a luxury furniture brand. "
        "Help customers browse the catalog, answer questions about materials and pricing, "
        "and offer to send the product catalog or showroom photos when relevant."
    ),
    media_library=[
        MediaLibraryEntry(
            keyword="catalog", url="https://example.com/luxury-furniture-catalog.pdf",
            mime_type="application/pdf", label="Product Catalog",
        ),
        MediaLibraryEntry(
            keyword="sofa", url="https://example.com/showroom-sofa.jpg",
            mime_type="image/jpeg", label="Showroom Sofa",
        ),
    ],
)

TENANT_B = Tenant(
    tenant_id="tenant-b",
    name="Automotive Care",
    prompt_directions=(
        "You are a helpful service-desk assistant for an automotive repair shop. "
        "Help customers schedule appointments, answer questions about services, and "
        "send invoice sheets or repair diagrams when they ask for documentation."
    ),
    media_library=[
        MediaLibraryEntry(
            keyword="invoice", url="https://example.com/invoice-sheet.pdf",
            mime_type="application/pdf", label="Invoice Sheet",
        ),
        MediaLibraryEntry(
            keyword="diagram", url="https://example.com/repair-diagram.jpg",
            mime_type="image/jpeg", label="Repair Diagram",
        ),
    ],
)


async def main():
    for tenant in (TENANT_A, TENANT_B):
        await tenants_col().update_one(
            {"tenant_id": tenant.tenant_id}, {"$set": tenant.model_dump()}, upsert=True
        )
        print(f"Seeded {tenant.tenant_id}")
    await refresh_mapping()


if __name__ == "__main__":
    asyncio.run(main())
