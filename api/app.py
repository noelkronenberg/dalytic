from flask import Flask, render_template, request, redirect, url_for, jsonify

import sqlite3
import pandas as pd
from sklearn.preprocessing import MinMaxScaler

import plotly
import plotly.graph_objs as go
import plotly.colors as pc

import json
import datetime
import logging

app = Flask(__name__)

# configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s [%(funcName)s] %(message)s')

# dynamically tracked metrics
METRIC_CONFIG = {
    "Resting Heart Rate": {"type": "number"},
    "Sleep Hours": {"type": "number"},
    "Calories": {"type": "number"},
    "Mood": {"type": "slider", "min": 1, "max": 5},
}

def get_db_connection():
    """
    Create a connection to the SQLite database.
    """

    logging.debug('Connecting to the database.')
    conn = sqlite3.connect('health_data.sqlite')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS health_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            metric_name TEXT NOT NULL,
            metric_value REAL NOT NULL,
            UNIQUE(date, metric_name) ON CONFLICT REPLACE
        )
    ''')

    logging.debug('Database connection established.')
    return conn

@app.route('/form', methods=['GET', 'POST'])
def form():
    """
    Display form for user to input data.
    """

    logging.debug('Form route accessed.')
    current_date = datetime.date.today().strftime('%Y-%m-%d')

    if request.method == 'POST':
        logging.debug('Form submitted.')
        selected_date = request.form.get('date', '')
        if not selected_date:
            selected_date = current_date

        conn = get_db_connection()
        for metric_name, _ in METRIC_CONFIG.items():
            value = request.form.get(metric_name, '0')
            logging.debug(f'Inserting data: {selected_date}, {metric_name}, {value}')
            conn.execute(
                'INSERT INTO health_data (date, metric_name, metric_value) VALUES (?, ?, ?)',
                (selected_date, metric_name, value)
            )
        conn.commit()
        conn.close()
        logging.debug('Data inserted and database connection closed.')

        return redirect(url_for('analysis'))

    # get previous values
    conn = get_db_connection()
    last_entries = {}
    for metric_name in METRIC_CONFIG.keys():
        last_entry = conn.execute(
            'SELECT date, metric_value FROM health_data WHERE metric_name = ? ORDER BY date DESC LIMIT 1',
            (metric_name,)
        ).fetchone()

        if last_entry:
            last_entries[metric_name] = last_entry[1]
        else:
            last_entries[metric_name] = '0'
    conn.close()
    logging.debug('Last entries fetched and database connection closed.')

    return render_template(
        'form.html', 
        metric_config=METRIC_CONFIG, 
        current_date=current_date, 
        last_entries=last_entries
    )

def calculate_correlations(data) -> str:
    """
    Calculate correlations between metrics, ensuring aligned dates.
    """

    df = pd.DataFrame(data, columns=['date', 'metric_name', 'metric_value'])
    df['metric_value'] = df['metric_value'].astype(float)

    # one column for each metric
    df_pivot = df.pivot(index='date', columns='metric_name', values='metric_value').dropna()

    unique_metrics = df_pivot.columns.tolist()
    correlation_results = []
    metric_pairs = []
    correlation_values = []

    for i, metric1 in enumerate(unique_metrics):
        for j, metric2 in enumerate(unique_metrics):
            if i < j: # avoid duplicate pairs and self-correlation
                logging.debug(f'Calculating correlation between {metric1} and {metric2}.')

                # check value count
                if len(df_pivot[metric1]) > 1 and len(df_pivot[metric2]) > 1:
                    correlation = df_pivot[metric1].corr(df_pivot[metric2])
                    correlation = round(correlation, 2)
                    correlation_results.append((metric1, metric2, correlation))
                    metric_pairs.append(f"{metric1} vs {metric2}")
                    correlation_values.append(correlation)
                    logging.debug(f'Correlation between {metric1} and {metric2}: {correlation}')
                else:
                    logging.debug(f'Not enough data to calculate correlation between {metric1} and {metric2}.')

    # sort by longest correlation
    sorted_indices = sorted(range(len(correlation_values)), key=lambda k: correlation_values[k], reverse=True)
    metric_pairs = [metric_pairs[i] for i in sorted_indices]
    correlation_values = [correlation_values[i] for i in sorted_indices]

    # dynamic margin for longest label
    max_label_length = max(len(pair) for pair in metric_pairs) if metric_pairs else 0
    left_margin = max(100, max_label_length * 8) 

    correlation_chart_json = json.dumps({
        "data": [
            go.Bar(
                x=correlation_values,
                y=metric_pairs,
                orientation='h'
            )
        ],
        "layout": go.Layout(
            title="Correlations",
            margin=dict(t=65, l=left_margin),
            autosize=True
        )
    }, cls=plotly.utils.PlotlyJSONEncoder)

    return correlation_chart_json

def normalize_dataframe(df):
    """
    Normalize a DataFrame's metric columns using MinMaxScaler to scale values between 0 and 1,
    taking into account predefined min and max values for slider-type metrics.
    """

    scaler = MinMaxScaler()
    for metric_name in df.columns.difference(['date']):
        if metric_name in METRIC_CONFIG and METRIC_CONFIG[metric_name]['type'] == 'slider':
            min_val = METRIC_CONFIG[metric_name]['min']
            max_val = METRIC_CONFIG[metric_name]['max']
            df[metric_name] = (df[metric_name] - min_val) / (max_val - min_val)
        else:
            df[[metric_name]] = scaler.fit_transform(df[[metric_name]])
    return df

@app.route('/analysis')
def analysis():
    """
    Display analysis of the data.
    """

    logging.debug('Analysis route accessed.')

    conn = get_db_connection()
    data = conn.execute('SELECT date, metric_name, metric_value FROM health_data').fetchall()
    conn.close()
    logging.debug('Data fetched from database and connection closed.')

    if not data:
        logging.debug('No data available for analysis.')
        return render_template('analysis.html', graphJSON=None, combined_graphJSON=None, num_graphs=0, correlation_chart_json=None)

    correlation_chart_json = calculate_correlations(data)

    # column for each metric
    df = pd.DataFrame(data, columns=['date', 'metric_name', 'metric_value'])
    df['date'] = pd.to_datetime(df['date'])
    df['metric_value'] = df['metric_value'].astype(float)
    df_pivot = df.pivot(index='date', columns='metric_name', values='metric_value')

    # impute missing dates
    df_pivot = df_pivot.reindex(pd.date_range(start=df['date'].min(), end=df['date'].max()), method='ffill')
    df_pivot = df_pivot.reset_index().rename(columns={'index': 'date'})

    # normalize data
    normalized_df = normalize_dataframe(df_pivot.copy())

    # generate color for each metric
    colors = pc.qualitative.Set1 + pc.qualitative.Set2 + pc.qualitative.Set3
    metric_colors = {metric: colors[i % len(colors)] for i, metric in enumerate(df_pivot.columns) if metric != 'date'}

    # create a figure for each metric
    figures = []
    combined_traces = []
    for metric_name in df_pivot.columns:
        if metric_name == 'date':
            continue

        color = metric_colors[metric_name]
        fill_color = color.replace("rgb", "rgba").replace(")", ", 0.1)")

        # individual metrics
        trace = go.Scatter(
            x=df_pivot['date'],
            y=df_pivot[metric_name],
            mode='lines',
            name=metric_name,
            fill='tozeroy',
            fillcolor=fill_color,
            line=dict(color=color)
        )
        
        # combined metrics
        combined_traces.append(
            go.Scatter(
                x=normalized_df['date'],
                y=normalized_df[metric_name],
                mode='lines',
                name=metric_name,
                fill='tozeroy',
                fillcolor=fill_color,
                line=dict(color=color)
            )
        )

        # individual metrics layout
        layout = go.Layout(
            title=metric_name,
            xaxis=dict(tickformat='%d %b', tickangle=-0, nticks=3),
            autosize=True,
            margin=dict(t=65),
        )

        figures.append({'data': [trace], 'layout': layout})
        logging.debug(f'Created figure for metric: {metric_name}')

    # combined metrics layout
    combined_layout = go.Layout(
        title="Normalized Combined Metrics",
        xaxis=dict(tickformat='%d %b', tickangle=-0, nticks=10),
        autosize=True,
        margin=dict(t=65),
        legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5),
    )
    combined_figure = {'data': combined_traces, 'layout': combined_layout}
    logging.debug('Created normalized combined metrics figure.')

    graphJSON = json.dumps(figures, cls=plotly.utils.PlotlyJSONEncoder)
    combined_graphJSON = json.dumps(combined_figure, cls=plotly.utils.PlotlyJSONEncoder)
    logging.debug('Converted figures to JSON.')

    return render_template(
        'analysis.html',
        graphJSON=graphJSON,
        combined_graphJSON=combined_graphJSON,
        num_graphs=len(figures),
        correlation_chart_json=correlation_chart_json
    )

@app.route('/entries')
def entries():
    """
    Display all entries in the database.
    """

    logging.debug('Entries route accessed.')
    conn = get_db_connection()
    data = conn.execute('SELECT id, date, metric_name, metric_value FROM health_data ORDER BY date DESC').fetchall()
    conn.close()
    logging.debug('Entries fetched from database and connection closed.')

    return render_template('entries.html', data=data)

@app.route('/delete/<int:entry_id>', methods=['POST'])
def delete_entry(entry_id):
    """
    Delete an entry from the database.
    """

    logging.debug(f'Deleting entry with ID: {entry_id}')
    conn = get_db_connection()
    conn.execute('DELETE FROM health_data WHERE id = ?', (entry_id,))
    conn.commit()
    conn.close()
    logging.debug('Entry deleted and database connection closed.')

    return redirect(url_for('entries'))

@app.route('/update_entry/<int:entry_id>', methods=['POST'])
def update_entry(entry_id):
    """
    Update an entry value in the database.
    """

    data = request.json
    field = data.get("field")
    new_value = data.get("value")

    if field not in ["metric_value"]: # only allow updating the metric value
        return jsonify({"status": "error", "message": "Invalid field"}), 400

    try:
        conn = get_db_connection()
        conn.execute(f"UPDATE health_data SET {field} = ? WHERE id = ?", (new_value, entry_id))
        conn.commit()
        conn.close()
        logging.debug(f"Entry {entry_id} updated: {field} = {new_value}")
        return jsonify({"status": "success"})
    
    except Exception as e:
        logging.error(f"Error updating entry: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/')
def index():
    """
    Redirect to home.
    """

    logging.debug('Index route accessed.')
    return redirect(url_for('analysis'))

if __name__ == '__main__':
    app.run(debug=True)