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