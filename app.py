import os
from datetime import datetime

from flask import Flask, request, flash, redirect, render_template, send_from_directory
from werkzeug.utils import secure_filename

import tools
import settings

app = Flask(__name__)
app.config.from_object("settings")


@app.route("/instructions")
def instructions():
    return render_template("instructions.html")

@app.route('/service-worker.js', methods=['GET'])
def service_worker():
    return send_from_directory('static', 'service-worker.js', mimetype='application/javascript')

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        username = request.form.get("username") or settings.CLICKSEND_USERNAME
        api_key = request.form.get("api_key") or settings.CLICKSEND_API_KEY
        csv_url = request.form.get("csv_url") or settings.CSV_URL

        if username == "" or api_key == "":
            flash("ClickSend username and API key required")
            return redirect(request.url)

        if not tools.valid_credentials(username, api_key):
            flash("Invalid ClickSend credentials. Please double check your username and API key and try again")
            return redirect(request.url)

        if csv_url:
            if not tools.is_valid_url(csv_url):
                flash("Invalid CSV URL")
                return redirect(request.url)
            number_list = tools.get_number_list_from_url(csv_url)
        else:
            if "file" not in request.files:
                flash("No file selected")
                return redirect(request.url)

            file = request.files["file"]
            if file.filename == "":
                flash("No file selected")
                return redirect(request.url)

            if file and tools.allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

                number_list = tools.get_number_list(filename)
                wrong_numbers = tools.check_numbers(number_list, username, api_key)

                if wrong_numbers:
                    with open(settings.LOG_FILE, "a") as log_file:
                        log_string = f"{datetime.now()} - {len(wrong_numbers)} wrong numbers identified."
                        log_file.write(f"\n{log_string}")
                    return render_template("wrong_numbers.html", number_list=wrong_numbers)

                number_list = tools.send_messages(number_list, username, api_key)
                return render_template("report.html", number_list=number_list)
            else:
                flash("File type not allowed. Please select a CSV file")
                return redirect(request.url)
    else:
        api_key_placeholder = "••••••••••••••••••••••••••" if settings.CLICKSEND_API_KEY else ""
        return render_template(
            "index.html",
            username_placeholder=settings.CLICKSEND_USERNAME,
            api_key_placeholder=api_key_placeholder,
            csv_url_placeholder=settings.CSV_URL
        )
