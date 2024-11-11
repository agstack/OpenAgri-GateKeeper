import logging
import warnings
import os

from waitress import serve
from gatekeeper.wsgi import application

host = os.getenv('APP_HOST', '0.0.0.0')
port = int(os.getenv('APP_PORT', '8001'))

logging.basicConfig(filename='logs/waitress.log', level=logging.INFO)

warnings.filterwarnings("ignore")

# Print the binding information for confirmation
print(f"Serving Django application on http://{host}:{port}")

serve(application, host=host, port=port)
