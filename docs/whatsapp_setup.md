# WhatsApp Cloud API Setup

## Prerequisites

1. Meta Business account with a WhatsApp Business App
2. A verified phone number added to the WABA
3. ngrok (or any HTTPS tunnel) running locally

## Environment Variables

All values go in the root `.env` file (never commit this):

```
WHATSAPP_ACCESS_TOKEN=<permanent token from Meta App>
WHATSAPP_PHONE_NUMBER_ID=<from WhatsApp > Phone Numbers>
WHATSAPP_WABA_ID=<WhatsApp Business Account ID>
WHATSAPP_VERIFY_TOKEN=<any secret string you choose>
WHATSAPP_APP_SECRET=<App Secret from Meta App Settings > Basic>
```

## Local Development with ngrok

1. Install ngrok and authenticate it once (`ngrok config add-authtoken <token>`).

2. Start the FastAPI server:
   ```
   scripts\start_dev.bat
   ```

3. In a second terminal, start ngrok:
   ```
   ngrok http 8000
   ```
   Note the HTTPS forwarding URL, e.g. `https://abc123.ngrok-free.app`

4. Set the webhook in Meta App Dashboard:
   - **Callback URL**: `https://<ngrok-url>/webhook/whatsapp`
   - **Verify Token**: same value as `WHATSAPP_VERIFY_TOKEN` in `.env`
   - Click **Verify and Save**
   - Subscribe to the **messages** field

## Webhook Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/webhook/whatsapp` | Meta verification (one-time) |
| POST | `/webhook/whatsapp` | Inbound messages + delivery receipts |

## Test Endpoints (development only)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/test/whatsapp/send-text` | Send a text message |
| POST | `/test/whatsapp/send-template` | Send a template message |
| POST | `/test/whatsapp/send-buttons` | Send interactive buttons |
| GET | `/test/whatsapp/messages/{phone}` | View recent messages in DB |
| POST | `/test/whatsapp/simulate-webhook` | Replay a raw webhook payload |

### Quick smoke test — send a text to yourself

```bash
curl -X POST http://localhost:8000/test/whatsapp/send-text \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello from PG AI!"}'
```
(Uses `TEST_WHATSAPP_NUMBER` from `.env` when no `phone` is specified.)

## Security Notes

- Every inbound POST is verified with HMAC-SHA256 (`X-Hub-Signature-256`).
- Processing is async (BackgroundTasks) — Meta always gets 200 within 5s.
- Duplicate messages are dropped via `whatsapp_message_id` idempotency check.
- Phone numbers are stored in E.164 (+91XXXXXXXXXX) but sent to Meta without the `+`.

## Message Types Handled

| Type | Description |
|------|-------------|
| `text` | Plain text |
| `button` | Quick-reply button tap |
| `interactive.button_reply` | Reply button from interactive message |
| `interactive.list_reply` | Row selected from list message |
| `image` | Image (media_id captured) |
| `audio` | Voice note |
| `video` | Video |
| `document` | File/PDF |
| `location` | Location pin |
| `contacts` | Contact card |
| `sticker` | Sticker |
| `reaction` | Emoji reaction |
| `unsupported` | Anything else (logged, not processed) |
