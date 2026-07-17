from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import sqlite3
import random
import time
import os
import stripe

# Mock Stripe API Key or load from env
stripe.api_key = os.environ.get("STRIPE_API_KEY", "sk_test_4eC39HqLyjWDarjtT1zdp7dc")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "whsec_mock")

app = FastAPI(title="Tesseract Key Gen Server")

DB_FILE = "licenses.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS licenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    app_id TEXT,
                    app_serial TEXT,
                    name TEXT,
                    email TEXT,
                    temp_pin TEXT,
                    target_pop_lock TEXT,
                    tier TEXT,
                    status TEXT
                )''')
    conn.commit()
    conn.close()

init_db()

class RegisterRequest(BaseModel):
    app_id: str
    app_serial: str
    initial_pop_lock: str
    name: str
    email: str
    requested_tier: str = "FULL_PAID"

class GenerateUnlockRequest(BaseModel):
    temp_pin: str
    current_pop_lock: str

@app.post("/register")
def register_device(req: RegisterRequest):
    # In a real system, we'd verify payment via Stripe/PayPal webhooks here.
    
    # Generate a Temp PIN for the user to enter into the app
    temp_pin = f"{random.randint(1000, 9999)}"
    
    # We would theoretically sync the HMAC sequence. For now, any target pop lock is accepted.
    # We just instruct the user on the next steps.
    target_pop_lock = "ANY" 

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''INSERT INTO licenses (app_id, app_serial, name, email, temp_pin, target_pop_lock, tier, status)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (req.app_id, req.app_serial, req.name, req.email, temp_pin, target_pop_lock, req.requested_tier, "PENDING"))
    conn.commit()
    conn.close()

    # Simulated delay for 48-hour email dispatch
    message = "Registration received. "
    if req.requested_tier == "SUBSCRIPTION_DAILY":
        message += "Your $1.59 payment is processing. "
    elif req.requested_tier == "SUBSCRIPTION_WEEKLY":
        message += "Your auto-renewing weekly subscription is processing. "

    message += "You will receive your 1-time code via email within 48 hours."

    return {
        "status": "success",
        "message": message,
        "temp_pin": temp_pin
    }

@app.post("/generate_unlock")
def generate_unlock(req: GenerateUnlockRequest):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT app_id, tier FROM licenses WHERE temp_pin = ? AND status = 'PENDING'", (req.temp_pin,))
    row = c.fetchone()
    
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Invalid Temp PIN or already processed.")
    
    app_id, tier = row
    
    # Mark as PROCESSED
    c.execute("UPDATE licenses SET status = 'PROCESSED' WHERE temp_pin = ?", (req.temp_pin,))
    conn.commit()
    conn.close()
    
    # Generate the 1-time unlock code and payload
    one_time_code = f"{random.randint(100000, 999999)}"
    
    payload_content = ""
    if tier == "FULL_PAID":
        payload_content = "TESS_FULL_UNLOCK"
    elif tier == "BASE_PAID":
        payload_content = "TESS_BASE_UNLOCK"
    elif tier == "SUBSCRIPTION_DAILY":
        payload_content = "TESS_DAILY_UNLOCK"
    elif tier == "SUBSCRIPTION_WEEKLY":
        payload_content = "TESS_WEEKLY_UNLOCK"
    else:
        payload_content = "TESS_TRIAL_UNLOCK"

    # The payload would normally be AES encrypted using the one_time_code.
    # The client app decrypts it using the code and if it reads the TESS_*_UNLOCK string, it unlocks.
    
    return {
        "one_time_code": one_time_code,
        "payload": payload_content,
        "instructions": "Enter the 1-time code into the app. It will fetch this payload and unlock the requested tier."
    }

class CheckoutRequest(BaseModel):
    app_id: str
    tier: str

@app.post("/create-checkout-session")
def create_checkout_session(req: CheckoutRequest):
    price_id = "price_mock_daily" if req.tier == "SUBSCRIPTION_DAILY" else "price_mock_weekly"
    
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url='https://yourdomain.com/success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url='https://yourdomain.com/cancel',
            client_reference_id=req.app_id
        )
        return {"id": session.id, "url": session.url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        # Invalid payload
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        app_id = session.get("client_reference_id")
        
        # In a real app, we'd trigger the email dispatch with the one_time_code here.
        # Mark as PROCESSED in DB
        if app_id:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("UPDATE licenses SET status = 'PAYMENT_RECEIVED' WHERE app_id = ?", (app_id,))
            conn.commit()
            conn.close()

    return {"status": "success"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
