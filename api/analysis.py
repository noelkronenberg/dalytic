from . import *

from flask import render_template, redirect, url_for
import json
from datetime import datetime

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
    bars = [
        {
            "type": "bar",
            "x": [v],
            "y": [l],
            "orientation": "h",
            "marker": {"color": "grey"},
            "hoverinfo": "none"
        }
        for v, l in zip(correlation_values, metric_pairs)
    ]
    max_label_length = max((len(l) for l in metric_pairs), default=10)
    margin = max(100, max_label_length * 8) # adjust margin based on label length
    logging.debug(f'Created bars')

    # create correlation chart
    chart = {
        "data": bars,
        "layout": {
            "title": "Correlations",
            "hovermode": False,
            "margin": {"t": 65, "l": margin, "r": 65, "b": 45},
            "autosize": True,
            "showlegend": False,
            "hoverlabel": {"namelength": -1},
            "yaxis": {"tickangle": 0}
        },
        "config": {
            "staticPlot": True # disable plotly interactivity
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
            "fillcolor": fill_color
        }
        layout = {
            "title": metric,
            "hovermode": False,
            "xaxis": {"visible": False},
            "autosize": True,
            "margin": {"l": 65, "r": 65, "t": 65, "b": 45}
        }
        
        figures.append({
            "data": [trace],
            "layout": layout,
            "config": {"staticPlot": True} # disable plotly interactivity
        })
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
        "hovermode": False,
        "xaxis": {"visible": False},
        "autosize": True,
        "margin": {"l": 65, "r": 65, "t": 65, "b": 65},
        "legend": {
            "orientation": "h", "yanchor": "bottom", "y": -0.15, "xanchor": "center", "x": 0.5
        }
    }

    # create combined figure
    combined_figure = {
        "data": normalized_traces,
        "layout": combined_layout,
        "config": {"staticPlot": True} # disable plotly interactivity
    }

    # get time span
    dates = [row[0] for row in data]
    lowest_date = min(dates)
    highest_date = max(dates)
    lowest_date_formatted = datetime.strptime(lowest_date, "%Y-%m-%d").strftime("%d/%m/%Y")
    highest_date_formatted = datetime.strptime(highest_date, "%Y-%m-%d").strftime("%d/%m/%Y")
    time_span = f"{lowest_date_formatted} to {highest_date_formatted}"

    def _has_enough_data(graph):
        """
        Check if a graph has enough data to render.
        """

        if not graph or 'data' not in graph:
            return False

        if isinstance(graph, str):
            try:
                graph = json.loads(graph)
            except json.JSONDecodeError:
                return False

        for trace in graph['data']:

            y = trace.get('y', [])
            numeric_values = [v for v in y if isinstance(v, (int, float))]
        
            if len(numeric_values) >= 2:
                return True
        
        return False

    has_data = (
        _has_enough_data(combined_figure) or
        _has_enough_data(correlation_chart_json) or
        any(_has_enough_data(g) for g in figures)
    )
    if has_data:
        logging.debug(f'Enough data to render page')
    else:
        logging.warning(f'Not enough data to render page')

    logging.debug(f'Rendering analysis page')
    return render_template(
        'analysis.html',
        graphJSON=json.dumps(figures),
        combined_graphJSON=json.dumps(combined_figure),
        num_graphs=len(figures),
        correlation_chart_json=correlation_chart_json,
        time_span=time_span,
        has_data=has_data
    )