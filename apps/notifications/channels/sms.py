"""
notifications/channels/sms.py
Handles SMS delivery.

Supported providers (configured via SMS_PROVIDER in settings):
  - africas_talking   — Africa's Talking (pan-Africa)
  - beam_africa       — Beam Africa (Tanzania)
  - nextsms           — NextSMS (Tanzania)
  - twilio            — Twilio (global)
  - console           — development fallback (default, prints to stdout)

Required .env keys per provider:
  africas_talking:  SMS_AT_USERNAME, SMS_AT_API_KEY, SMS_SENDER_ID (optional)
  beam_africa:      SMS_BEAM_API_KEY, SMS_BEAM_SOURCE_ADDR
  nextsms:          SMS_NEXTSMS_USERNAME, SMS_NEXTSMS_PASSWORD, SMS_SENDER_ID (optional)
  twilio:           SMS_TWILIO_ACCOUNT_SID, SMS_TWILIO_AUTH_TOKEN, SMS_TWILIO_FROM
  console:          (none)
"""

import requests
from django.conf import settings


def send_sms(to: str, message: str) -> tuple[bool, str | None]:
    """
    Send an SMS to a phone number.

    Returns:
        (True, None)          on success
        (False, error_str)    on failure
    """
    provider = getattr(settings, 'SMS_PROVIDER', 'console').lower()

    if provider == 'africas_talking':
        return _send_via_africas_talking(to, message)
    elif provider == 'beam_africa':
        return _send_via_beam_africa(to, message)
    elif provider == 'nextsms':
        return _send_via_nextsms(to, message)
    elif provider == 'twilio':
        return _send_via_twilio(to, message)
    else:
        return _send_via_console(to, message)


# ─── Providers ────────────────────────────────────────────────────────────────

def _send_via_africas_talking(to: str, message: str) -> tuple[bool, str | None]:
    try:
        import africastalking  # pip install africastalking
        africastalking.initialize(
            username=settings.SMS_AT_USERNAME,
            api_key=settings.SMS_AT_API_KEY,
        )
        sms = africastalking.SMS
        kwargs = {'message': message, 'recipients': [to]}
        sender_id = getattr(settings, 'SMS_SENDER_ID', None)
        if sender_id:
            kwargs['sender_id'] = sender_id
        response = sms.send(**kwargs)
        recipients = response.get('SMSMessageData', {}).get('Recipients', [])
        if recipients and recipients[0].get('statusCode') == 101:
            return True, None
        return False, str(response)
    except Exception as exc:
        return False, str(exc)


def _send_via_beam_africa(to: str, message: str) -> tuple[bool, str | None]:
    """
    Beam Africa SMS API (Tanzania).
    Docs: https://beamafrica.com/docs/sms
    """
    try:
        url = 'https://bsmsa.beam.africa/api/sms/send'
        payload = {
            'api_key':     settings.SMS_BEAM_API_KEY,
            'source_addr': settings.SMS_BEAM_SOURCE_ADDR,
            'schedule':    '',
            'message':     message,
            'dest_addr':   to,
        }
        response = requests.post(url, json=payload, timeout=15)
        data = response.json()
        # Beam returns {"status": "success", ...} on success
        if response.ok and str(data.get('status', '')).lower() == 'success':
            return True, None
        return False, str(data)
    except Exception as exc:
        return False, str(exc)


def _send_via_nextsms(to: str, message: str) -> tuple[bool, str | None]:
    """
    NextSMS API (Tanzania).
    Docs: https://nextsms.co.tz/api
    Uses HTTP Basic Auth (username + password).
    """
    try:
        import base64
        credentials = base64.b64encode(
            f"{settings.SMS_NEXTSMS_USERNAME}:{settings.SMS_NEXTSMS_PASSWORD}".encode()
        ).decode()

        url = 'https://messaging.nextsms.co.tz/api/sms/v1/text/single'
        headers = {
            'Authorization': f'Basic {credentials}',
            'Content-Type':  'application/json',
            'Accept':        'application/json',
        }
        payload = {
            'from':    getattr(settings, 'SMS_SENDER_ID', 'NEXTSMS'),
            'to':      to,
            'text':    message,
        }
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        data = response.json()
        # NextSMS returns {"messages": [{"status": "0", ...}]} where status "0" = success
        messages = data.get('messages', [])
        if messages and str(messages[0].get('status', '')) == '0':
            return True, None
        return False, str(data)
    except Exception as exc:
        return False, str(exc)


def _send_via_twilio(to: str, message: str) -> tuple[bool, str | None]:
    try:
        from twilio.rest import Client  # pip install twilio
        client = Client(settings.SMS_TWILIO_ACCOUNT_SID, settings.SMS_TWILIO_AUTH_TOKEN)
        client.messages.create(body=message, from_=settings.SMS_TWILIO_FROM, to=to)
        return True, None
    except Exception as exc:
        return False, str(exc)


def _send_via_console(to: str, message: str) -> tuple[bool, str | None]:
    """Development fallback — prints to stdout instead of sending."""
    print(f"[SMS console] To: {to} | Message: {message}")
    return True, None
