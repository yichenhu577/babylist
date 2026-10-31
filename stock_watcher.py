#!/usr/bin/env python3
"""
Stock watcher for the Nuna PIPA Aire rx (Pine) on Babylist.
Emails you ONCE when it flips from out of stock -> in stock, then re-arms
if it goes out of stock again. Standard library only.

Environment variables (set as GitHub Actions secrets):
    GMAIL_ADDRESS       the Gmail account that sends the alert
    GMAIL_APP_PASSWORD  a Gmail "app password" (NOT your normal password)
    ALERT_TO            optional; where to send the alert (defaults to GMAIL_ADDRESS)

Usage:
    python stock_watcher.py              # check once
    python stock_watcher.py --test-alert # send a test email and exit
"""
import argparse
import json
import os
import smtplib
import sys
import urllib.error
import urllib.request
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

URL = "https://www.babylist.com/gp/nuna-pipa-aire-rx-1791566202/46283/1871699"
PRODUCT_MARKER = "pipa aire rx"          # must appear on the page, else we assume a bad fetch
OUT_OF_STOCK_TEXT = "currently out of stock"
STATE_FILE = Path(__file__).with_name(".stock_state.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def log(msg):
    print(f"[{datetime.utcnow():%Y-%m-%d %H:%M:%S} UTC] {msg}", flush=True)


def check_stock():
    """Returns 'in_stock', 'out_of_stock', or 'unknown' (fetch problem / page changed)."""
    req = urllib.request.Request(URL, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            html = r.read().decode("utf-8", errors="replace").lower()
    except urllib.error.HTTPError as e:
        log(f"HTTP error {e.code} (possibly blocked)")
        return "unknown"
    except Exception as e:
        log(f"Fetch error: {e}")
        return "unknown"

    if PRODUCT_MARKER not in html:
        log("Product name not found on page; layout changed or request was blocked")
        return "unknown"
    return "out_of_stock" if OUT_OF_STOCK_TEXT in html else "in_stock"


def send_email(subject, body):
    user = os.environ.get("GMAIL_ADDRESS")
    pw = os.environ.get("GMAIL_APP_PASSWORD")
    to = os.environ.get("ALERT_TO") or user
    if not (user and pw):
        log("GMAIL_ADDRESS / GMAIL_APP_PASSWORD not set")
        return False
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = user, to, subject
    msg.set_content(body)
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
            s.login(user, pw.replace(" ", ""))
            s.send_message(msg)
        log("Email sent")
        return True
    except Exception as e:
        log(f"Email failed: {e}")
        return False


def load_state():
    try:
        return json.loads(STATE_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {"alerted": False}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--test-alert", action="store_true")
    args = p.parse_args()

    if args.test_alert:
        sys.exit(0 if send_email("Stock watcher test", "Your stock watcher can send email.") else 1)

    status = check_stock()
    state = load_state()
    log(f"Status: {status}")

    if status == "in_stock" and not state["alerted"]:
        ok = send_email("Car seat IN STOCK: Nuna PIPA Aire rx (Pine)",
                        f"It looks like it's back in stock on Babylist:\n{URL}")
        if ok:
            state["alerted"] = True      # only mark alerted if the email actually went out
    elif status == "out_of_stock" and state["alerted"]:
        state["alerted"] = False         # re-arm for the next restock
    # 'unknown' never changes state or triggers an alert

    STATE_FILE.write_text(json.dumps(state))


if __name__ == "__main__":
    main()
