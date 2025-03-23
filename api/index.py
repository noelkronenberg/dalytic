from . import *

from flask import redirect, url_for

@app.route('/')
def index():
    """
    Redirect to the analysis page.
    """

    logging.debug('Redirecting to analysis page')
    return redirect(url_for('analysis'))