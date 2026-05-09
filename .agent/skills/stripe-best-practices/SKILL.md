---
name: stripe-best-practices
description: >
type: feature
---
  Stripe integration best practices for payments, subscriptions, webhooks,
  and checkout. Covers idempotency, error handling, webhook verification,
  and PCI compliance patterns. Use when integrating Stripe APIs.
type: feature
source: Stripe

# Stripe Integration Best Practices

Secure, reliable Stripe integration patterns.

## Core Principles

1. **Server-side only** — Never expose secret keys client-side
2. **Idempotency** — Use idempotency keys for all mutating requests
3. **Webhook-driven** — Don't rely on redirects for payment confirmation
4. **PCI compliance** — Use Stripe.js / Elements, never handle raw card data

## Environment Setup

```bash
# Environment variables (NEVER hardcode)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

## Checkout Session (Recommended)

```python
import stripe
import os

stripe.api_key = os.environ["STRIPE_SECRET_KEY"]

def create_checkout_session(price_id: str, customer_email: str) -> str:
    """Create a Stripe Checkout session."""
    session = stripe.checkout.Session.create(
        mode="payment",  # or "subscription"
        line_items=[{"price": price_id, "quantity": 1}],
        customer_email=customer_email,
        success_url="https://example.com/success?session_id={CHECKOUT_SESSION_ID}",
        cancel_url="https://example.com/cancel",
        idempotency_key=f"checkout_{customer_email}_{price_id}",
    )
    return session.url
```

## Payment Intents (Custom UI)

```python
def create_payment_intent(amount: int, currency: str = "usd") -> dict:
    """Create a PaymentIntent for custom payment flow."""
    intent = stripe.PaymentIntent.create(
        amount=amount,  # In cents
        currency=currency,
        automatic_payment_methods={"enabled": True},
    )
    return {"client_secret": intent.client_secret}
```

```typescript
// Client-side with Stripe.js
const stripe = Stripe(process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY!);

const { error } = await stripe.confirmPayment({
  elements,
  confirmParams: {
    return_url: 'https://example.com/payment-complete',
  },
});
```

## Webhook Handling

```python
import stripe
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature")
    webhook_secret = os.environ["STRIPE_WEBHOOK_SECRET"]

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError:
        return jsonify({"error": "Invalid payload"}), 400
    except stripe.error.SignatureVerificationError:
        return jsonify({"error": "Invalid signature"}), 400

    # Handle events
    match event["type"]:
        case "checkout.session.completed":
            session = event["data"]["object"]
            fulfill_order(session)
        case "payment_intent.succeeded":
            intent = event["data"]["object"]
            handle_successful_payment(intent)
        case "payment_intent.payment_failed":
            intent = event["data"]["object"]
            handle_failed_payment(intent)
        case "customer.subscription.deleted":
            subscription = event["data"]["object"]
            handle_cancellation(subscription)

    return jsonify({"status": "ok"}), 200
```

## Idempotency

```python
import uuid

# Always use idempotency keys for creates
stripe.PaymentIntent.create(
    amount=1000,
    currency="usd",
    idempotency_key=str(uuid.uuid4()),
)

# Retry-safe pattern
def charge_with_retry(amount: int, customer_id: str, max_retries: int = 3) -> dict:
    idempotency_key = f"charge_{customer_id}_{amount}_{int(time.time())}"

    for attempt in range(max_retries):
        try:
            return stripe.PaymentIntent.create(
                amount=amount,
                currency="usd",
                customer=customer_id,
                idempotency_key=idempotency_key,
            )
        except stripe.error.RateLimitError:
            time.sleep(2 ** attempt)
        except stripe.error.APIConnectionError:
            time.sleep(2 ** attempt)

    raise RuntimeError("Payment failed after retries")
```

## Error Handling

```python
try:
    charge = stripe.Charge.create(amount=1000, currency="usd", source=token)
except stripe.error.CardError as e:
    # Card declined — show user-friendly message
    body = e.json_body
    err = body.get("error", {})
    logger.warning(f"Card declined: {err.get('code')}")
except stripe.error.RateLimitError:
    # Too many requests — retry with backoff
    ...
except stripe.error.InvalidRequestError:
    # Invalid params — developer error
    ...
except stripe.error.AuthenticationError:
    # Bad API key — check configuration
    ...
except stripe.error.APIConnectionError:
    # Network issue — retry
    ...
except stripe.error.StripeError:
    # Generic — log and alert
    ...
```

## Subscriptions

```python
def create_subscription(customer_id: str, price_id: str) -> dict:
    subscription = stripe.Subscription.create(
        customer=customer_id,
        items=[{"price": price_id}],
        payment_behavior="default_incomplete",
        expand=["latest_invoice.payment_intent"],
    )
    return {
        "subscription_id": subscription.id,
        "client_secret": subscription.latest_invoice.payment_intent.client_secret,
    }
```

## Security Checklist

- [ ] Secret key only on server (`sk_*` never in client code)
- [ ] Webhook signatures verified (`stripe.Webhook.construct_event`)
- [ ] Idempotency keys on all mutating requests
- [ ] Amount/price validated server-side (never trust client)
- [ ] HTTPS enforced for all Stripe communication
- [ ] Metadata sanitized (no PII in metadata fields)
- [ ] Test mode keys for development (`sk_test_*`)
- [ ] Error messages don't expose internal details to users

## Testing

```bash
# Forward webhooks to local server
stripe listen --forward-to localhost:5000/webhook

# Trigger test events
stripe trigger payment_intent.succeeded
stripe trigger checkout.session.completed
```
