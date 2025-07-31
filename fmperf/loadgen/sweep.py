import os
import json
from .run import run
from fmperf.utils import parse_results
from fmperf.utils.constants import REQUESTS_DIR, RESULTS_ALL_FILENAME

users = [int(u) for u in os.environ["SWEEP_USERS"].split(",")]

results = []

for u in users:
    os.environ["NUM_USERS"] = str(u)

    result_filename = "result_sweep_u%d.json" % (u)

    run(result_filename)

    filename = os.path.join(REQUESTS_DIR, result_filename)

    with open(filename, "rb") as f:
        tmp = json.load(f)

    results.extend(tmp["results"])

    parse_results(results, print_df=True)

outfile = os.path.join(REQUESTS_DIR, RESULTS_ALL_FILENAME)
print(f">> writing all results to file: {outfile}")
with open(outfile, "w") as f:
    json.dump(results, f)
