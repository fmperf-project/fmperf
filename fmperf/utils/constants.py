import os

REQUESTS_DIR = (lambda s: s + "/" if len(s) > 1 and not s.endswith("/") else s)(
    os.environ.get("REQUESTS_DIR", "")
)
REQUESTS_FILENAME = os.environ["REQUESTS_FILENAME"]
RESULTS_ALL_FILENAME = os.environ["RESULTS_ALL_FILENAME"]
