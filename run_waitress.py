from waitress import serve
from gatekeeper.wsgi import application
import warnings

warnings.filterwarnings("ignore")

serve(application, host="0.0.0.0", port=8080)
