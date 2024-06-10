import argparse
import requests
import datetime
import pandas as pd
import urllib3
import yaml
import os
import re
from urllib3.exceptions import InsecureRequestWarning

urllib3.disable_warnings(InsecureRequestWarning)

metrics = [
    "DCGM_FI_DEV_POWER_USAGE",
    "kepler_container_gpu_joules_total",
    "kepler_container_package_joules_total",
    "kepler_container_dram_joules_total",
]


class MetricData:
    def __init__(self, metric: str, start: str, end: str, pod: str, data: {}):
        try:
            if metric == "":
                raise Exception("No metric name")

            self.metric = metric
            self.data = data
            # Check the format of timestamps

            start_date = start.split("T")
            time_arr = start_date[1].split(":")
            self.start = "{}_{}-{}-{}".format(
                start_date[0], time_arr[0], time_arr[1], time_arr[2]
            )

            end_date = end.split("T")
            etime_arr = end_date[1].split(":")
            self.end = "{}_{}-{}-{}".format(
                end_date[0], etime_arr[0], etime_arr[1], etime_arr[2]
            )

            if len(pod) > 0:
                if "kepler" in metric:
                    self.pod = pod["pod_name"]
                else:
                    self.pod = pod["exported_pod"]
            else:
                self.pod = ""

        except AttributeError as e:
            print("catch AttributeError: ", e)
        except TypeError as e:
            print("catch TypeError: ", e)
        except KeyError as e:
            print("catch KeyError:", e)
        except IndexError as e:
            print("catch IndexError: {}, may fail to parse timestamps".format(e))
        except Exception as e:
            print("catch Exception: ", e)


# query the specified metrics to Prometheus between the given start and end timestamps
def get_prom_results(uri, metric, query, step, start, end):
    metric_data = None
    if uri is None or uri == "":
        raise Exception("PROM_URL: {}".format(uri))

    try:
        access_token = os.environ.get("PROM_TOKEN")
        # start_unix = datetime.datetime.strptime(start, "%Y-%m-%dT%H:%M:%SZ")
        # end_unix = datetime.datetime.strptime(end, "%Y-%m-%dT%H:%M:%SZ")
        params = {"query": query, "start": start, "end": end, "step": step}

        # generate header if PROM_TOKEN exists
        if access_token:
            headers = {"Authorization": "Bearer {}".format(access_token)}
        else:
            headers = None

        # print(uri, headers)
        # send a request
        response = requests.get(uri, verify=False, headers=headers, params=params)
        response.raise_for_status()
        # parse a response
        json_data = response.json()
        if len(json_data["data"]["result"]) > 0:
            # print(json_data["data"]["result"][0]["metric"])
            pod = json_data["data"]["result"][0]["metric"]
            values = json_data["data"]["result"][0]["values"]
            metric_data = MetricData(metric, start, end, pod, values)
            # print(metric_data)
        else:
            metric_data = MetricData(metric, start, end, "", {})

    except requests.exceptions.HTTPError as e:
        print("catch HTTPError: ", e)
    except KeyError as e:
        print("catch KeyError: ", e)
    except Exception as e:
        print("catch Exception: ", e)
    return metric_data


# Export energy data to csv file
def write_to_file(data: MetricData):
    try:
        num_users = os.environ["NUM_USERS"]
        path = os.environ.get("METRICS_DIR", "/requests")
        filename = "{}/{}_{}_{}.csv".format(path, num_users, data.start, data.metric)
        df = pd.DataFrame(data.data)
        # print(df)
        df.to_csv(filename, header=["timestamp", data.metric], index=False)
    except Exception as e:
        print("catch Exception: ", e)


# get file prefix based for current exp based on start time
def get_file_prefix(start_ts: str):
    start_time = start_ts.replace("T", "_").replace(":", "-")

    try:
        num_users = os.environ["NUM_USERS"]
        path = os.environ.get("METRICS_DIR", "/requests")
        fprefix = "{}_{}".format(num_users, start_time)
    except Exception as e:
        print("catch Exception: ", e)

    return fprefix


# get target metrics from a file specified by TARGET_METRICS_LIST env variable
def get_target_metrics():
    global metrics
    metric_list = os.environ.get("TARGET_METRICS_LIST", "default_metrics.yaml")
    if metric_list is not None:
        with open(metric_list, "r") as yml:
            try:
                config = yaml.safe_load(yml)
                mlist = config["metrics"]
                if len(mlist) > 0:
                    metrics.extend(mlist)
                # remove redundant metrics
                metrics = list(dict.fromkeys(metrics))
            except Exception as e:
                print("catch Exception: ", e)
    return metrics


# read metrics files and concatenate them to integrate performance data
def summarize_energy(start_ts: str):
    global metrics
    all_df = pd.DataFrame(dtype=float)
    # target metrics
    metrics = get_target_metrics()

    try:
        dirpath = os.environ.get("METRICS_DIR", "/requests")
        steps = float(os.environ.get("NUM_PROM_STEPS", 30))
        dirlist = os.listdir(dirpath)
        start = start_ts.split("T")[1].split("Z")[0]
        fprefix = get_file_prefix(start_ts)

        for m in metrics:
            metric_df = pd.Series(dtype=float)
            if m == "DCGM_FI_DEV_POWER_USAGE":
                idle_df = pd.Series(dtype=float)
                energy_df = pd.Series(dtype=float)
                users = pd.Series(dtype=float)

            for f in dirlist:
                if f.endswith("{}.csv".format(m)) == False:
                    continue
                fpath = os.path.join(dirpath, f)

                # read metric csv file
                df = pd.read_csv(fpath, sep=",", dtype=float)
                pod = df.columns[-1]
                num_users = os.environ["NUM_USERS"]

                if m == "DCGM_FI_DEV_POWER_USAGE":
                    idle = df[pod].iloc[0]
                    # print(idle)
                    metric_df[start] = (df[pod].iloc[1:] - idle).mean()
                    idle_df[start] = idle
                    energy_df[start] = ((df[pod].iloc[1:] - idle) * steps).sum()
                    users[start] = num_users
                elif "DCGM" in m:
                    metric_df[start] = df[pod].iloc[1:].mean()
                elif "kepler" in m:
                    metric_df[start] = (df[pod] * steps).sum()

            if m == "DCGM_FI_DEV_POWER_USAGE":
                all_df["num_users"] = users
                all_df["idle_power"] = idle_df
                all_df["dcgm_total_energy"] = energy_df
            all_df[m] = metric_df

        # print(all_df)
        all_df.columns = [
            "num_users",
            "dcgm_idle_power",
            "dcgm_total_energy",
            "dcgm_power",
        ]
        mlist = metrics.remove("DCGM_FI_DEV_POWER_USAGE")
        all_df.columns.extend(mlist)
        all_df.index.name = "start_time"

        all_df["kepler_total_energy"] = (
            all_df["kepler_dram_energy"]
            .add(all_df["kepler_pkg_energy"], fill_value=0)
            .add(all_df["kepler_gpu_energy"], fill_value=0)
        )
        # if the metrics collected by Kepler are available
        if all_df["kepler_total_energy"].mean() > 0:
            all_df["energy"] = all_df["kepler_total_energy"]
        else:
            # otherwise use DCGM metrics
            all_df["kepler_energy"] = pd.Series(dtype=float)
            all_df["energy"] = all_df["dcgm_total_energy"]
            # print(all_df["dcgm_energy"])

    except KeyError as e:
        print("catch KeyError: ", e)
    except FileNotFoundError as e:
        print("catch FileNotFoundError: ", e)
    except Exception as e:
        print("catch Exception: ", e)

    print(all_df)
    return all_df


# collecting the gpu- or energy-related metrics from Prometheus if PROM_URL is available
def collect_metrics(start, end, step, ns):
    global metrics
    # target metrics
    metrics = get_target_metrics()

    try:
        promuri = os.environ.get("PROM_URL")
        for metric in metrics:
            if "kepler" in metric:
                filter_str = '{{container_namespace="{}"}}'.format(ns)
                query_str = "sum(irate({}{}[1m])) by(pod_name)".format(
                    metric, filter_str
                )
            else:
                filter_str = '{{exported_namespace="{}"}}'.format(ns)
                query_str = "sum({}{}) by(exported_pod)".format(metric, filter_str)
            # query metric to Prometheus
            md = get_prom_results(promuri, metric, query_str, step, start, end)
            # save the data to csv files
            if len(md.data) > 0:
                write_to_file(md)
    except KeyError as e:
        print(
            ">> skipped collecting energy metrics because prometheus is not available: ",
            e,
        )
    except Exception as e:
        print("catch Exception: ", e)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="collect energy metrics from prometheus"
    )
    parser.add_argument("start", help="start timestamp")
    parser.add_argument("end", help="end timestamp")
    parser.add_argument("--step", default=30)
    parser.add_argument("--namespace", default="rina")

    args = parser.parse_args()
    start = args.start
    end = args.end
    step = args.step
    ns = args.namespace
    collect_metrics(start, end, step, ns)
