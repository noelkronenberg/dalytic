from . import *

from flask import render_template, request, redirect, url_for, session, send_file, flash, jsonify
import sqlite3
import tempfile
from io import BytesIO

# -----------------------------------------------------------
# Database Handling
# -----------------------------------------------------------

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

# -----------------------------------------------------------
# Data Handling
# -----------------------------------------------------------

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