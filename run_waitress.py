import logging
import warnings
import os

from waitress import serve
from gatekeeper.wsgi import application

host = os.getenv('APP_HOST', '0.0.0.0')
port = int(os.getenv('APP_PORT', '9000'))

logging.basicConfig(filename='logs/waitress.log', level=logging.INFO)

warnings.filterwarnings("ignore")

serve(application, host=host, port=port)
