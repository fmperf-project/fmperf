import os
import json
from .run import run
from fmperf.utils import parse_results
from fmperf.utils.constants import REQUESTS_DIR, RESULTS_ALL_FILENAME

users = [int(u) for u in os.environ["SWEEP_USERS"].split(",")]

results = []

for u in users:
    os.environ["NUM_USERS"] = str(u)
    os.environ["RESULTS_FILENAME"] = "result_sweep_u%d.json" % (u)

    run()

    filename = "%srequests/result_sweep_u%d.json" % (REQUESTS_DIR, u)

    with open(filename, "rb") as f:
        tmp = json.load(f)

    results.extend(tmp["results"])

    parse_results(results, print_df=True)

outfile = f"{REQUESTS_DIR}{RESULTS_ALL_FILENAME}"
print(f">> writing all results to file: {outfile}")
with open(outfile, "w") as f:
    json.dump(results, f)
