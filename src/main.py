from rest_server import create_restful_app 
import tempfile
from settings import LISTEN_INTERFACE, LISTEN_PORT


if __name__ == '__main__':
    with tempfile.TemporaryDirectory() as tmpuserdir:
        app = create_restful_app(tmpuserdir)
        app.run(host=LISTEN_INTERFACE, port=LISTEN_PORT, debug=True, threaded=False, use_reloader=False)