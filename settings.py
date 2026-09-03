import os
# Flask config
TESTING = False
SECRET_KEY = os.environ.get('SECRET_KEY')
CLICKSEND_USERNAME = os.environ.get('CLICKSEND_USERNAME', '')
CLICKSEND_API_KEY = os.environ.get('CLICKSEND_API_KEY', '')
CSV_URL = os.environ.get('CSV_URL', '')
PERMANENT_SESSION_LIFETIME = 180
JSONIFY_PRETTYPRINT_REGULAR = True
UPLOAD_FOLDER = "/tmp"
ALLOWED_EXTENSIONS = {"csv"}
LOG_FILE = "sms-log.txt"
