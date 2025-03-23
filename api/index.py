from flask import Flask, render_template, request, redirect, url_for, jsonify, session, send_file, flash

from statistics import mean
import sqlite3

import datetime
import logging
import os
import json
import tempfile
from io import BytesIO

FLASK_SECRET_KEY = os.environ.get('FLASK_SECRET_KEY')

app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s [%(funcName)s] %(message)s')

METRIC_CONFIG = {
    "Resting Heart Rate": {
        "type": "number", 
        "color": "rgba(240,128,128,1.0)"
    },
    "Sleep Hours": {
        "type": "number", 
        "color": "rgba(135,206,250,1.0)"
    },
    "Calories": {
        "type": "number", "color": "rgba(144,238,144,1.0)"
    },
    "Mood": {
        "type": "slider",
        "min": 1,
        "max": 5,
        "color": "rgba(255,182,193,1.0)"
    },
}
ALLOWED_EXTENSIONS = {'sqlite', 'db'}

@app.before_request
def require_db():
    """
    Require a custom database to be uploaded before accessing any endpoint other than the upload endpoint.
    """

    if 'custom_db' not in session and request.endpoint not in ('upload_db', 'static'):
        flash('Please upload a custom database before proceeding.')
        logging.warning('No custom database uploaded')
        return redirect(url_for('upload_db'))

def allowed_file(filename):
    """
    Check if the file extension is allowed.
    """

    logging.debug(f'Checking if {filename} is an allowed file')
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload', methods=['GET', 'POST'])
def upload_db():
    """
    Upload a custom SQLite database file.
    """

    logging.debug('Accessing upload page')

    if request.method == 'POST':
        file = request.files.get('file')
        logging.debug(f'File uploaded: {file}')

        if not file or file.filename == '':
            flash('No selected file. Please choose a file to upload.')
            logging.warning('No file selected')
            return redirect(request.url)
        
        if allowed_file(file.filename):
            logging.debug(f'Allowed file: {file.filename}')
            session['custom_db'] = file.read()
            logging.debug('File data stored in session cookie.')
            return redirect(url_for('analysis'))
        else:
            logging.warning(f'Invalid file extension: {file.filename}')
            flash('Invalid file extension. Please upload a SQLite database file.')
    
    logging.debug('Rendering upload page')
    return render_template('upload.html')

@app.route('/reset_db', methods=['GET', 'POST'])
def reset_db():
    """
    Reset the custom database by removing in-session data.
    """

    logging.debug('Resetting custom database')
    session.pop('custom_db', None)
    logging.debug('Redirecting to upload page')
    return redirect(url_for('analysis'))

@app.route('/download_db')
def download_db():
    """
    Download the custom database from in-session data.
    """

    logging.debug('Downloading custom database')
    data = session.get('custom_db')
    if not data:
        logging.warning('No custom database uploaded')
        flash("Please upload a custom database before proceeding.")
        return redirect(url_for('upload_db'))
    
    # in-memory data using BytesIO
    in_memory_file = BytesIO(data)
    logging.debug('Sending in-memory database file')
    return send_file(
        in_memory_file,
        as_attachment=True,
        download_name='database.sqlite',
        mimetype='application/x-sqlite3'
    )

def get_db_connection():
    """
    Load the uploaded database (stored in session) into an in-memory SQLite database.
    """

    data = session.get('custom_db')
    if not data:
        logging.warning('No custom database uploaded')
        flash("Please upload a custom database before proceeding.")
        raise RuntimeError("No database uploaded")
    
    # session bytes to a temporary file
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(data)
        tmp_name = tmp.name

    # load temporary file into an in-memory database
    logging.debug('Loading session bytes into in-memory database')
    disk_conn = sqlite3.connect(tmp_name)
    mem_conn = sqlite3.connect(":memory:")
    
    # copy data from disk to memory
    disk_conn.backup(mem_conn)
    disk_conn.close()
    logging.debug('Loaded session bytes into in-memory database')
    
    os.remove(tmp_name) # remove temporary file
    logging.debug('Removed temporary file')

    logging.debug('Connected to in-memory database, loaded from session bytes.')
    return mem_conn

@app.route('/form', methods=['GET', 'POST'])
def form():
    """
    Display a form to input data.
    """

    logging.debug('Accessing form page')
    current_date = datetime.date.today().strftime('%Y-%m-%d')

    if request.method == 'POST':
        logging.debug('Form submitted')

        selected_date = request.form.get('date', current_date)
        
        try:
            logging.debug('Connecting to database')
            conn = get_db_connection()
        except RuntimeError:
            logging.warning('No custom database uploaded')
            return redirect(url_for('upload_db'))
        
        for metric_name in METRIC_CONFIG:
            logging.debug(f'Inserting data for {metric_name}')
            value = request.form.get(metric_name, '0')
            conn.execute('INSERT INTO health_data (date, metric_name, metric_value) VALUES (?, ?, ?)',
                         (selected_date, metric_name, value))
            logging.debug(f'Inserted data for {metric_name}')

        conn.commit()
        conn.close()
        logging.debug('Committed data to database and closed connection')

        logging.debug('Redirecting to analysis page')
        return redirect(url_for('analysis'))
    
    try:
        logging.debug('Connecting to database')
        conn = get_db_connection()
    except RuntimeError:
        logging.warning('No custom database uploaded')
        return redirect(url_for('upload_db'))
    
    last_entries = {}
    for metric_name in METRIC_CONFIG:
        logging.debug(f'Fetching last entry for {metric_name}')
        result = conn.execute(
            'SELECT metric_value FROM health_data WHERE metric_name = ? ORDER BY date DESC LIMIT 1',
            (metric_name,)
        ).fetchone()
        last_entries[metric_name] = result[0] if result else '0'
        logging.debug(f'Fetching last entry for {metric_name}')
    
    conn.close()
    logging.debug('Closed database connection')

    logging.debug('Rendering form page')
    return render_template('form.html', metric_config=METRIC_CONFIG, current_date=current_date, last_entries=last_entries)

def calculate_correlations(data):
    """
    Calculate the correlations between different metrics.
    """

    logging.debug(f'Calculation of correlations initiated')

    # group data by date and metric name
    metrics = {}
    for date, name, value in data:
        metrics.setdefault(date, {})[name] = float(value)

    # align metrics
    dates = sorted(metrics.keys())
    aligned = {}
    for date in dates:
        row = metrics[date]
        if all(k in row for k in METRIC_CONFIG):
            for k, v in row.items():
                aligned.setdefault(k, []).append(v)
    logging.debug(f'Aligned metrics: {aligned}')

    metric_pairs = []
    correlation_values = []

    # calculate correlations
    logging.debug(f'Calculating correlations')
    keys = list(aligned.keys())
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):

            # get data for each metric
            m1, m2 = keys[i], keys[j]
            x, y = aligned[m1], aligned[m2]

            if len(x) < 2 or len(y) < 2:
                logging.debug(f'Skipping {m1} vs {m2} due to insufficient data points')
                continue

            # calculate covariance
            mx, my = mean(x), mean(y)
            cov = sum((a - mx) * (b - my) for a, b in zip(x, y))

            # calculate standard deviations
            std_x = sum((a - mx) ** 2 for a in x) ** 0.5
            std_y = sum((b - my) ** 2 for b in y) ** 0.5
            
            # calculate correlation coefficient
            corr = cov / (std_x * std_y) if std_x and std_y else 0
            corr = round(corr, 2)
            
            # store the metric pair and their correlation value
            metric_pairs.append(f"{m1} vs {m2}")
            correlation_values.append(corr)
            
    logging.debug(f'Calculated correlations')

    # sort by correlation values
    sorted_indices = sorted(range(len(correlation_values)), key=lambda k: correlation_values[k], reverse=True)
    metric_pairs = [metric_pairs[i] for i in sorted_indices]
    correlation_values = [correlation_values[i] for i in sorted_indices]

    # create correlation bars
    bars = [{"type": "bar", "x": [v], "y": [l], "orientation": "h", "marker": {"color": "grey"}, "hoverinfo": "x+y"} for v, l in zip(correlation_values, metric_pairs)]
    max_label_length = max((len(l) for l in metric_pairs), default=10)
    margin = max(100, max_label_length * 8) # adjust margin based on label length
    logging.debug(f'Created bars')

    # create correlation chart
    chart = {
        "data": bars,
        "layout": {
            "title": "Correlations",
            "margin": {"t": 65, "l": margin},
            "autosize": True,
            "showlegend": False,
            "hoverlabel": {"namelength": -1},
            "yaxis": {"tickangle": 0}
        }
    }

    logging.debug(f'Created correlation chart')
    return json.dumps(chart)

def normalize(value, min_val, max_val):
    """
    Normalize a value between a minimum and maximum value.
    """

    logging.debug(f'Normalizing value')
    normalized_value = (value - min_val) / (max_val - min_val) if max_val != min_val else 0

    return round(normalized_value, 2)

@app.route('/analysis')
def analysis():
    """
    Display a graph of the data.
    """

    logging.debug('Accessing analysis page')

    try:
        logging.debug('Connecting to database')
        conn = get_db_connection()
    except RuntimeError:
        logging.warning('No custom database uploaded')
        return redirect(url_for('upload_db'))
    
    logging.debug('Fetching data')
    data = conn.execute('SELECT date, metric_name, metric_value FROM health_data').fetchall()
    conn.close()
    logging.debug('Fetched data and closed database connection')

    if not data:
        logging.warning('No data found')
        return render_template('analysis.html', graphJSON=None, combined_graphJSON=None, num_graphs=0, correlation_chart_json=None)

    correlation_chart_json = calculate_correlations(data)
    entries = {}

    # group data by date and metric name
    for date, name, value in data:
        entries.setdefault(name, []).append((date, float(value)))
    logging.debug(f'Grouped entries')

    figures = []

    # create graphs
    logging.debug(f'Creating graphs')
    for metric, values in entries.items():
        logging.debug(f'Creating graph for {metric}')

        # sort values by date
        dates, vals = zip(*sorted(values))

        # get colors for metrics
        line_color = METRIC_CONFIG[metric].get("color", "rgba(128,128,128,1.0)")
        fill_color = line_color.replace('1.0)', '0.1)')
        logging.debug(f'Got colors for metrics')

        trace = {
            "x": dates,
            "y": vals,
            "mode": "lines",
            "name": metric,
            "fill": "tozeroy",
            "line": {"color": line_color},
            "fillcolor": line_color
        }
        layout = {
            "title": metric,
            "xaxis": {
                "tickangle": -0,
                "tickformat": "%m-%d"
            },
            "autosize": True,
            "margin": {"t": 65}
        }
        
        figures.append({"data": [trace], "layout": layout})
        logging.debug(f'Created graph for {metric}')

    logging.debug(f'Created graphs')

    # create combined graph
    logging.debug(f'Creating combined graph')
    normalized_traces = []
    for metric, values in entries.items():

        # normalize values
        _, vals = zip(*sorted(values))
        logging.debug(f'Normalizing values for {metric}')
        if METRIC_CONFIG[metric]["type"] == "slider":
            min_v = METRIC_CONFIG[metric]["min"]
            max_v = METRIC_CONFIG[metric]["max"]
            logging.debug(f'Using min and max values for normalization')
        else:
            min_v, max_v = min(vals), max(vals)
            logging.debug(f'Using min and max values from data for normalization')

        # create normalized trace
        logging.debug(f'Creating normalized trace for {metric}')
        norm_vals = [normalize(v, min_v, max_v) for v in vals]

        # sort dates
        dates = [d for d, _ in sorted(values)]

        # get colors for metrics
        line_color = METRIC_CONFIG[metric].get("color", "rgba(128,128,128,1.0)")
        fill_color = line_color.replace('1.0)', '0.1)')
        logging.debug(f'Got colors for metrics')
        
        # create trace
        trace = {
            "x": dates,
            "y": norm_vals,
            "mode": "lines",
            "name": metric,
            "fill": "tozeroy",
            "line": {"color": line_color},
            "fillcolor": fill_color
        }
        normalized_traces.append(trace)
        logging.debug(f'Created normalized trace for {metric}')
    
    logging.debug(f'Created traces')

    # create combined layout
    combined_layout = {
        "title": "Metrics",
        "xaxis": {
            "tickangle": -0,
            "tickformat": "%m-%d"
        },
        "autosize": True,
        "margin": {"t": 65},
        "legend": {
            "orientation": "h", "yanchor": "bottom", "y": -0.3, "xanchor": "center", "x": 0.5
        }
    }

    logging.debug(f'Rendering analysis page')
    return render_template(
        'analysis.html',
        graphJSON=json.dumps(figures),
        combined_graphJSON=json.dumps({"data": normalized_traces, "layout": combined_layout}),
        num_graphs=len(figures),
        correlation_chart_json=correlation_chart_json
    )

@app.route('/entries')
def entries():
    """
    Display all entries.
    """

    try:
        logging.debug('Connecting to database')
        conn = get_db_connection()
    except RuntimeError:
        logging.warning('No custom database uploaded')
        return redirect(url_for('upload_db'))
    
    logging.debug('Fetching entries')
    data = conn.execute('SELECT id, date, metric_name, metric_value FROM health_data ORDER BY date DESC').fetchall()
    conn.close()
    logging.debug('Fetched entries and closed database connection')

    logging.debug('Rendering entries page')
    return render_template('entries.html', data=data)

@app.route('/delete/<int:entry_id>', methods=['POST'])
def delete_entry(entry_id):
    """
    Delete an entry.
    """

    logging.debug(f'Deleting entry: {entry_id}')

    try:
        logging.debug('Connecting to database')
        conn = get_db_connection()
    except RuntimeError:
        logging.warning('No custom database uploaded')
        return redirect(url_for('upload_db'))
    
    logging.debug(f'Deleting entry: {entry_id}')
    conn.execute('DELETE FROM health_data WHERE id = ?', (entry_id,))
    conn.commit()
    conn.close()
    logging.debug('Deleted entry and closed database connection')

    logging.debug('Redirecting to entries page')
    return redirect(url_for('entries'))

@app.route('/update_entry/<int:entry_id>', methods=['POST'])
def update_entry(entry_id):
    """
    Update an entry.
    """

    logging.debug(f'Updating entry: {entry_id}')

    # get field and new value
    data = request.json
    field = data.get("field")
    new_value = data.get("value")

    if field not in ["metric_value"]:
        return jsonify({"status": "error", "message": "Invalid field"}), 400
    try:
        conn = get_db_connection()
        conn.execute(f"UPDATE health_data SET {field} = ? WHERE id = ?", (new_value, entry_id))
        conn.commit()
        conn.close()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/')
def index():
    """
    Redirect to the analysis page.
    """

    logging.debug('Redirecting to analysis page')
    return redirect(url_for('analysis'))