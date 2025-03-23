from flask import Flask
import logging
import os

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

from .index import * 
from .db import *
from .input import *
from .analysis import *