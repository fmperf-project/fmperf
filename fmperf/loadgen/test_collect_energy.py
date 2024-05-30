import pytest
from unittest.mock import patch
import os
import pandas as pd
import collect_energy as ce


# test MetricData class
@pytest.mark.parametrize(
    "metric, start, end, pod, data",
    [
        (
            "GPU_UTIL",
            "2023-11-14T12:03:21Z",
            "2023-11-14T12:09:04Z",
            {"exported_pod": "test"},
            {
                "timestamp": [1700561535, 1700561550, 1700561565],
                "test": [6.287, 95.539, 95.539, 221.150],
            },
        ),
        (
            "",
            "2023-11-14T12:03:21Z",
            "2023-11-14T12:09:04Z",
            {"exported_pod": "test"},
            {
                "timestamp": [1700561535, 1700561550, 1700561565],
                "test": [6.287, 95.539, 95.539, 221.150],
            },
        ),
        (
            "kepler_power",
            "2023-11-14T12:03:21Z",
            "2023-11-14T12:09:04Z",
            {"pod_name": "test"},
            {
                "timestamp": [1700561535, 1700561550, 1700561565],
                "test": [6.287, 95.539, 95.539, 221.150],
            },
        ),
        (
            "GPU_UTIL",
            "2023-11-14T12:03:21Z",
            "2023-11-14T12:09:04Z",
            "",
            {
                "timestamp": [1700561535, 1700561550, 1700561565],
                "test": [6.287, 95.539, 95.539, 221.150],
            },
        ),
        (
            "GPU_UTIL",
            "2023-11-14T12:03:21Z",
            "2023-11-14T12:09:04Z",
            {"exported_pod": "test"},
            {},
        ),
        ("GPU_UTIL", "", "2023-11-14T12:09:04Z", {"exported_pod": "test"}, {}),
        ("GPU_UTIL", "2023-11-14T12:09:04Z", "", {"exported_pod": "test"}, {}),
    ],
)
def test_metricdata(metric, start, end, pod, data):
    md = ce.MetricData(metric, start, end, pod, data)
    assert md


# test get_prom_results function
@pytest.mark.parametrize(
    "metric, start, end, step, query",
    [
        (
            "GPU_UTIL",
            "2023-11-14T12:03:21Z",
            "2023-11-14T12:09:04Z",
            "15",
            "sum(irate(DCGM_FI_DEV_GPU_UTIL)) by(exported_pod)",
        ),
        (
            "",
            "2023-11-14T12:03:21Z",
            "2023-11-14T12:09:04Z",
            "15",
            "sum(irate(DCGM_FI_DEV_GPU_UTIL)) by(exported_pod)",
        ),
        (
            "GPU_UTIL",
            "",
            "2023-11-14T12:09:04Z",
            "15",
            "sum(irate(DCGM_FI_DEV_GPU_UTIL)) by(exported_pod)",
        ),
        (
            "GPU_UTIL",
            "2023-11-14T12:03:21Z",
            "",
            "15",
            "sum(irate(DCGM_FI_DEV_GPU_UTIL)) by(exported_pod)",
        ),
        (
            "GPU_UTIL",
            "2023-11-14T12:03:21Z",
            "2023-11-14T12:09:04Z",
            "",
            "sum(irate(DCGM_FI_DEV_GPU_UTIL)) by(exported_pod)",
        ),
        ("GPU_UTIL", "2023-11-14T12:03:21Z", "2023-11-14T12:09:04Z", "15", ""),
    ],
)
def test_get_prom(metric, start, end, step, query):
    with patch.dict(
        "os.environ", {"PROM_URL": "http://localhost:8080/api/query_range"}
    ):
        os.environ.pop("PROM_URL", default=None)
        uri = os.environ.get("PROM_URL")
        with pytest.raises(Exception):
            data = ce.get_prom_results(uri, metric, query, step, start, end)
    # if prometheus url localhost:8080 is active
    # ce.get_prom_results(os.environ.get("PROM_URL"), metric, query, step, start, end)


# test write_tofile function
@pytest.mark.parametrize(
    "data",
    [
        {
            "timestamp": [1700561535, 1700561550, 1700561565],
            "test": [6.287, 95.539, 95.539, 221.150],
        },
        {},
    ],
)
def test_write_success(data):
    md = ce.MetricData("test", "", "", {"exported_pod": "test"}, data)

    with patch.dict(
        "os.environ",
        {"NUM_USERS": "1", "MODEL_ID": "google/flan-t5", "METRICS_DIR": "."},
    ):
        ce.write_to_file(md)
    with patch.dict(
        "os.environ", {"NUM_USERS": "1", "MODEL_ID": "flan-t5", "METRICS_DIR": "."}
    ):
        ce.write_to_file(md)
    with patch.dict(
        "os.environ",
        {"NUM_USERS": "user", "MODEL_ID": "google/flan-t5", "METRICS_DIR": "."},
    ):
        ce.write_to_file(md)
    with patch.dict("os.environ", {"MODEL_ID": "google/flan-t5", "METRICS_DIR": "."}):
        ce.write_to_file(md)
    with patch.dict("os.environ", {"NUM_USERS": "1", "METRICS_DIR": "."}):
        ce.write_to_file(md)
    with patch.dict("os.environ", {"NUM_USERS": "1", "MODEL_ID": "google/flan-t5"}):
        ce.write_to_file(md)


# test summarize_energy function
def test_summarize_energy():
    columns = [
        "num_users",
        "dcgm_idle_power",
        "dcgm_energy",
        "dcgm_power",
        "gpu_util",
        "mem_util",
        "tensor_active",
        "kepler_gpu_energy",
        "kepler_pkg_energy",
        "kepler_dram_energy",
        "kepler_energy",
        "energy",
    ]
    # files exist
    with patch.dict("os.environ", {"METRICS_DIR": "tests/sample_metrics"}):
        actual_df = ce.summarize_energy()
        expected_data_list = [
            [
                1.0,
                76.487,
                1465.5000000000002,
                48.85,
                43.0,
                10.0,
                float("nan"),
                1971.648,
                373.0500000000001,
                69.756,
                2414.454,
                2414.454,
            ]
        ]
        index = ["06:36:31"]
        expected_df = pd.DataFrame(
            data=expected_data_list, columns=columns, index=index
        )
        expected_df.index.name = "start_time"
        pd.testing.assert_frame_equal(left=expected_df, right=actual_df)

    # no files exist
    with patch.dict("os.environ", {"METRICS_DIR": "tests/no_files"}):
        actual_df = ce.summarize_energy()

    # "DCGM_FI_DEV_POWER_USAGE" file does not exist
    with patch.dict("os.environ", {"METRICS_DIR": "tests/file_power_lacks"}):
        actual_df = ce.summarize_energy()

    # one of the target metrics file does not exist
    with patch.dict("os.environ", {"METRICS_DIR": "tests/file_lacks"}):
        actual_df = ce.summarize_energy()
        index = ["06:36:31"]
        expected_data_list = [
            [
                1.0,
                76.487,
                1465.5000000000002,
                48.85,
                43.0,
                10.0,
                float("nan"),
                float("nan"),
                373.0500000000001,
                69.756,
                442.80600000000015,
                442.80600000000015,
            ]
        ]
        expected_df = pd.DataFrame(
            data=expected_data_list, columns=columns, index=index
        )
        expected_df.index.name = "start_time"
        pd.testing.assert_frame_equal(left=expected_df, right=actual_df)

    # METRICS_DIR is not set
    with patch.dict("os.environ", {"METRICS_DIR": ""}):
        actual_df = ce.summarize_energy()
