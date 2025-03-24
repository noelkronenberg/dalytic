from . import *

from flask import render_template, redirect, url_for
import json

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
    logging.debug('Fetched data')

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