import os

LISTEN_INTERFACE = os.environ.get('LISTEN_INTERFACE', '0.0.0.0')
LISTEN_PORT = int(os.environ.get('LISTEN_PORT', '5000'))
CONVERSION_TIMEOUT = int(os.environ.get('CONVERSION_TIMEOUT', '30'))
MEMORY_USAGE_RATIO_LIMIT = float(os.environ.get('MEMORY_USAGE_RATIO_LIMIT', '8.0'))
