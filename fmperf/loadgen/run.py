import time
import requests
from typing import Iterable, List
import json
import pandas as pd
import os
from durations import Duration
import numpy as np
from text_generation_tests.approx import approx
import grpc
from google.protobuf import json_format
from text_generation_tests.pb import generation_pb2_grpc as gpb2, generation_pb2 as pb2
from fmperf.utils import parse_results
from datetime import datetime
from .collect_energy import collect_metrics, summarize_energy


def run():
    def get_streaming_response_tgis(response):
        stop = False
        generated_tokens = 0
        while not stop:
            try:
                x = next(response)
                timestamp = time.time_ns()
                data = json_format.MessageToDict(x)
                # skip first response (tokenizer output only)
                if "inputTokenCount" not in data:
                    n_tokens = data["generatedTokenCount"] - generated_tokens
                    generated_tokens = data["generatedTokenCount"]
                    yield data, n_tokens, timestamp, True, None
            except Exception as e:
                timestamp = time.time_ns()
                yield None, 0, timestamp, False, e

    def get_streaming_response_vllm(response):
        response_iter = response.iter_lines(
            chunk_size=8192,
            decode_unicode=False,
            delimiter=b"\n",
        )

        stop = False
        prev_completion_tokens = 0
        while not stop:
            try:
                chunk = next(response_iter)
                timestamp = time.time_ns()
                if chunk and not stop:
                    data = chunk.decode("utf-8").strip().split("data: ")[1]
                    out = json.loads(data)["choices"][0]
                    stop = out["finish_reason"] is not None
                    usage = json.loads(data)["usage"]
                    token_count = usage["completion_tokens"] - prev_completion_tokens
                    prev_completion_tokens = usage["completion_tokens"]
                    for i in range(token_count):
                        yield {
                            "index": out["index"],
                            "text": "" if (i < token_count - 1) else out["text"],
                            "logprobs": None,
                            "finish_reason": (
                                None if (i < token_count - 1) else out["finish_reason"]
                            ),
                            "stop_reason": (
                                None if (i < token_count - 1) else out["stop_reason"]
                            ),
                        }, 1, timestamp, True, None
            except Exception as e:
                timestamp = time.time_ns()
                yield None, 0, timestamp, False, e

        # we have stopped
        yield None, 0, time.time_ns(), False, StopIteration()

    infile = "/requests/%s" % (os.environ["REQUESTS_FILENAME"])
    outfile = "/requests/%s" % (os.environ["RESULTS_FILENAME"])
    target = os.environ["TARGET"]
    api_url = os.environ["URL"]
    num_users = int(os.environ["NUM_USERS"])
    duration = Duration(os.environ["DURATION"])
    backoff = Duration(os.environ["BACKOFF"])
    grace_period = Duration(os.environ["GRACE_PERIOD"])

    with open(infile, "rb") as f:
        sample_requests = json.load(f)

    def worker(wid, channel):
        rs = np.random.RandomState(seed=wid)

        if target == "tgis":
            stub = gpb2.GenerationServiceStub(channel)

        t_start = time.time_ns()

        output = []
        request_idx = 0
        while (
            time.time_ns() - t_start < duration.to_seconds() * 1000.0 * 1000.0 * 1000.0
        ):
            sample_idx = rs.randint(low=0, high=len(sample_requests))

            sample_request = sample_requests[sample_idx]["request"]

            if target == "vllm":
                headers = {"User-Agent": "fmaas-load-test"}
                t0 = time.time_ns()
                response = requests.post(
                    "http://%s/v1/completions" % (api_url),
                    headers=headers,
                    json=sample_request,
                    stream=True,
                )
            elif target == "tgis":
                message = json_format.ParseDict(
                    sample_request, pb2.SingleGenerationRequest()
                )
                t0 = time.time_ns()
                response = stub.GenerateStream(message)
            else:
                raise ValueError("Invalid target")

            stop = False
            response_idx = 0

            if target == "vllm":
                response_generator = get_streaming_response_vllm(response)
            elif target == "tgis":
                response_generator = get_streaming_response_tgis(response)
            else:
                raise ValueError("Invalid target")

            apply_backoff = False

            while not stop:
                r, n_tokens, t, ok, err = next(response_generator)

                if not ok:
                    stop = True
                    # check if we have reached end of stream
                    if type(err) is StopIteration:
                        continue
                    else:
                        apply_backoff = True

                record = {
                    "response": r,
                    "ok": ok,
                    "error": str(err),
                    "timestamp": t,
                    "exp_num_users": num_users,
                    "exp_duration": duration.to_seconds(),
                    "duration_ms": (t - t0) / 1000.0 / 1000.0,
                    "exclude": (t - t_start) / 1000.0 / 1000.0 / 1000.0
                    > (duration.to_seconds() + grace_period.to_seconds()),
                    "worker_idx": wid,
                    "request_idx": request_idx,
                    "sample_idx": sample_idx,
                    "response_idx": response_idx,
                    "n_tokens": n_tokens,
                }

                output.append(record)
                response_idx += 1
                t0 = t

            if apply_backoff:
                time.sleep(backoff.to_seconds())

            request_idx += 1

        with open("results_wid%d" % (wid), "w") as f:
            json.dump(output, f)

        return True

    from datetime import datetime
    import concurrent.futures

    energy_start_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")

    channel = grpc.insecure_channel(api_url) if target == "tgis" else None

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_users) as executor:
        futures = []
        for i in range(num_users):
            futures.append(executor.submit(worker, wid=i, channel=channel))

        results = []
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    energy_stop_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")

    all_outputs = []
    for i in range(num_users):
        with open("results_wid%d" % (i), "rb") as f:
            tmp = json.load(f)
        all_outputs.extend(tmp)

    def check_consistent(row):
        if row["ok"]:
            tmp = sample_requests[row["sample_idx"]]["expected"]
            tmp = tmp[row["response_idx"]]
            consistent = row["response"] == approx(tmp)
            return consistent
        else:
            return False

    for row in all_outputs:
        row["consistent"] = check_consistent(row)

    # collect and summarize energy metrics
    energy = {}
    if os.environ.get("PROM_URL") is None:
        print(
            ">> skipped collecting energy metrics because prometheus is not available."
        )
    else:
        step = os.environ.get("NUM_PROM_STEPS", "30")
        ns = os.environ["NAMESPACE"]
        collect_metrics(energy_start_time, energy_stop_time, step, ns)
        all_energy_metrics = summarize_energy(energy_start_time)
        print(all_energy_metrics)
        energy = all_energy_metrics[["num_users", "energy"]].to_dict()

    merged_data = {"results": all_outputs, "energy": energy}

    print(">> writing results to file: %s" % (outfile))
    with open(outfile, "w") as f:
        json.dump(merged_data, f)

    return all_outputs


if __name__ == "__main__":
    parse_results(run(), print_df=True)
