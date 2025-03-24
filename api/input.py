from . import *

from flask import render_template, request, redirect, url_for
from statistics import mean
import datetime
import json

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
        backup_db_to_session(conn)
        conn.close()
        logging.debug('Committed data to database')

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