import csv
import os
import re
import chardet
import logging
import requests
from datetime import datetime
from urllib3.util import parse_url
from io import StringIO

import settings

# Setup logging
logging.basicConfig(filename=settings.LOG_FILE, level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

CLICKSEND_BASE_URL = "https://rest.clicksend.com/v3"


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in settings.ALLOWED_EXTENSIONS
    )


def _get_auth_headers(username, api_key):
    import base64
    credentials = base64.b64encode(f"{username}:{api_key}".encode()).decode()
    return {
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/json"
    }


def valid_credentials(username, api_key):
    """Validate ClickSend credentials by calling the account endpoint."""
    url = f"{CLICKSEND_BASE_URL}/account"
    headers = _get_auth_headers(username, api_key)
    try:
        response = requests.get(url, headers=headers, timeout=10)
        return response.status_code == 200
    except requests.RequestException as e:
        logging.error(f"Error occurred in valid_credentials: {e}")
        return False


def is_valid_url(url):
    # Check if the URL has a valid format
    try:
        result = parse_url(url)
        if not all([result.scheme, result.netloc]):
            return False
    except ValueError:
        return False

    # Check if the URL is accessible
    try:
        response = requests.head(url, timeout=10)
        if response.status_code >= 400:
            return False
    except requests.RequestException:
        return False

    # Check if the response contains ASCII text
    try:
        response = requests.get(url, timeout=10)
        content_type = response.headers.get('Content-Type', '')
        if 'text' not in content_type:
            return False
    except requests.RequestException:
        return False

    return True


def _is_e164(number):
    """Basic E.164 format check: + followed by 7-15 digits."""
    return bool(re.match(r'^\+\d{7,15}$', number.strip()))


def check_numbers(numbers, username, api_key):
    """Check numbers for basic E.164 format validity.
    ClickSend does not have a phone lookup API like Twilio,
    so we do basic regex validation here."""
    numbers_not_found = list()
    for number in numbers:
        to_number = number[1].strip() if len(number) > 1 else ""
        if not _is_e164(to_number):
            numbers_not_found.append(number)
    return numbers_not_found


def get_number_list_from_url(url):
    # Use requests to fetch the CSV data from the URL
    response = requests.get(url)
    response.raise_for_status()  # Raise an exception if the request was unsuccessful

    # Convert the CSV data into a list of lists
    csv_data = StringIO(response.text)
    try:
        csv_reader = csv.reader(csv_data)
        number_list = [row[:3] for row in csv_reader]  # Only include the first three columns
    except csv.Error as e:
        logging.error(f"Invalid CSV data: {e}")
        raise ValueError("Invalid CSV data") from e

    return number_list


def get_number_list(filename):
    number_list = list()
    file_path = os.path.join(
        settings.UPLOAD_FOLDER,
        filename
    )

    # Routine to detect CSV file encoding
    rawdata = open(file_path, "rb").read()
    guessed_encoding = chardet.detect(rawdata)

    with open(
            file_path,
            newline="",
            mode="r",
            encoding=guessed_encoding["encoding"]) as csv_file:
        csv_reader = csv.reader(csv_file)
        number_list = [row[:3] for row in csv_reader]  # Only include the first three columns
    os.remove(file_path)
    return number_list


def send_messages(number_list, username, api_key):
    """Send SMS messages via ClickSend API.

    number_list items: [from_number, to_number, message_body]
    Returns list with appended status and message_id: [from, to, body, status, message_id]
    """
    url = f"{CLICKSEND_BASE_URL}/sms/send"
    headers = _get_auth_headers(username, api_key)

    # Build ClickSend messages payload
    messages = []
    for row in number_list:
        sender = row[0].strip() if len(row) > 0 else ""
        recipient = row[1].strip() if len(row) > 1 else ""
        body = row[2].strip() if len(row) > 2 else ""

        messages.append({
            "to": recipient,
            "body": body,
            "from": sender,
        })

    payload = {"messages": messages}

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response_data = response.json()

        logging.info(f"ClickSend response: {response_data}")

        if response.status_code == 200 and response_data.get("response_code") == "SUCCESS":
            sent_messages = response_data.get("data", {}).get("messages", [])

            # Map response messages back to our number_list
            for i, row in enumerate(number_list):
                if i < len(sent_messages):
                    msg = sent_messages[i]
                    status = msg.get("status", "UNKNOWN")
                    msg_id = msg.get("message_id", "N/A")
                    row.append(status)
                    row.append(msg_id)
                else:
                    row.append("NO_RESPONSE")
                    row.append("N/A")
        else:
            # API call failed - mark all as failed
            error_msg = response_data.get("response_msg", "API_ERROR")
            for row in number_list:
                row.append(error_msg)
                row.append("N/A")

    except requests.RequestException as e:
        logging.error(f"Error occurred in send_messages: {e}")
        for row in number_list:
            row.append("REQUEST_ERROR")
            row.append("N/A")

    with open(settings.LOG_FILE, "a") as log_file:
        log_string = f"{datetime.now()} - {len(number_list)} messages processed via ClickSend."
        log_file.write(f"\n{log_string}")

    return number_list
