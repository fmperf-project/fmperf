import os
import json
from .run import run
from fmperf.utils import parse_results

users = [int(u) for u in os.environ["SWEEP_USERS"].split(",")]

results = []

for u in users:
    os.environ["NUM_USERS"] = str(u)
    os.environ["RESULTS_FILENAME"] = "result_sweep_u%d.json" % (u)

    run()

    filename = "/requests/result_sweep_u%d.json" % (u)

    with open(filename, "rb") as f:
        tmp = json.load(f)

    results.extend(tmp["results"])

    parse_results(results, print_df=True)

outfile = f"/requests/{os.environ['RESULTS_ALL_FILENAME']}"
print(f">> writing all results to file: {outfile}")
with open(outfile, "w") as f:
    json.dump(results, f)
