"""
One-time Stripe setup: creates prices and webhook endpoint in test mode.

Usage:
    export STRIPE_SECRET_KEY=sk_test_...
    python scripts/setup_stripe.py

Outputs env vars ready to copy into Vercel.
"""

import os
import sys

import stripe

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
if not stripe.api_key:
    print("ERROR: Set STRIPE_SECRET_KEY environment variable")
    sys.exit(1)


def main():
    print("Creating prices...\n")

    prices = [
        ("Pro Monthly", "pro_monthly", 2900, "month", 1),
        ("Pro Yearly", "pro_yearly", 29000, "year", 1),
        ("Enterprise Monthly", "enterprise_monthly", 9900, "month", 1),
        ("Enterprise Yearly", "enterprise_yearly", 99000, "year", 1),
    ]

    price_ids = {}
    for name, lookup_key, amount, interval, interval_count in prices:
        p = stripe.Price.create(
            currency="usd",
            unit_amount=amount,
            recurring={"interval": interval, "interval_count": interval_count},
            product_data={"name": f"Sporafind {name}"},
            lookup_key=lookup_key,
        )
        price_ids[lookup_key] = p.id
        print(f"  {name:25s}  ${amount/100:<8.2f}  {p.id}")

    print("\nCreating webhook endpoint...\n")
    wh = stripe.WebhookEndpoint.create(
        url="https://api.sporafind.com/billing/webhook",
        enabled_events=[
            "checkout.session.completed",
            "customer.subscription.updated",
            "customer.subscription.deleted",
            "invoice.payment_failed",
        ],
        description="Sporafind billing webhook",
        api_version="2025-02-24.acacia",
    )
    print(f"  Webhook secret: {wh.secret}")

    print("\n\n=== Vercel env vars (copy these) ===\n")
    print(f"STRIPE_SECRET_KEY={stripe.api_key}")
    print(f"STRIPE_WEBHOOK_SECRET={wh.secret}")
    print(f"STRIPE_PRICE_PRO_MONTHLY={price_ids['pro_monthly']}")
    print(f"STRIPE_PRICE_PRO_YEARLY={price_ids['pro_yearly']}")
    print(f"STRIPE_PRICE_ENTERPRISE_MONTHLY={price_ids['enterprise_monthly']}")
    print(f"STRIPE_PRICE_ENTERPRISE_YEARLY={price_ids['enterprise_yearly']}")
    print()


if __name__ == "__main__":
    main()
