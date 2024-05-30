import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin


class CustomHistogram(BaseEstimator, TransformerMixin):
    def __init__(self, n_bins=12):
        self.n_bins = n_bins
        self.n_bins_ = {}
        self.bin_edges_ = {}
        self.bin_labels_ = {}

    def fit_transform(self, data, y=None):
        self.columns_ = data.columns

        out = pd.DataFrame(columns=data.columns)

        for c in data.columns:
            vals = data[c].values
            n_val = vals.shape[0]
            sortind = np.argsort(vals)
            sortval = np.array(vals)[sortind]

            dd = [
                {
                    "count": 1,
                    "rank": 0,
                    "val": sortval[0],
                }
            ]

            for i in range(1, n_val):
                prev_val = dd[-1]["val"]
                next_val = sortval[i]
                if next_val != prev_val:
                    dd.append({"count": 1, "rank": i, "val": next_val})
                else:
                    dd[-1]["count"] += 1

            rank_value = []
            self.bin_edges_[c] = []
            self.bin_labels_[c] = []

            if len(dd) <= self.n_bins:
                self.n_bins_[c] = len(dd)
                for i, x in enumerate(dd):
                    self.bin_edges_[c].append(x["val"])
                    self.bin_labels_[c].append(x["val"])
                    rank_value.append(x["rank"])
                rank_value.append(n_val)
            else:
                freqvals = []
                for i, x in enumerate(dd):
                    frac = x["count"] / n_val
                    if frac > 0.1:
                        freqvals.append(i)

                num = n_val
                den = self.n_bins
                for i in freqvals:
                    num -= dd[i]["count"]
                    den -= 1

                targ = int(np.floor(num / den))

                bin_idx = 0
                pos = 0

                while bin_idx < self.n_bins and pos < len(dd):
                    bin_pos = pos
                    bin_len = 0
                    bin_weight = 0
                    bin_rank = dd[pos]["rank"]
                    bin_val = dd[pos]["val"]
                    bin_label = 0.0

                    while bin_weight < targ and pos < len(dd):
                        bin_len += 1
                        bin_label += dd[pos]["count"] * dd[pos]["val"]
                        bin_weight += dd[pos]["count"]
                        pos += 1

                    if float(bin_weight) > 1.2 * targ and pos > (bin_pos + 1):
                        pos -= 1
                        bin_len -= 1
                        bin_weight -= dd[pos]["count"]
                        bin_label -= dd[pos]["count"] * dd[pos]["val"]

                    self.bin_edges_[c].append(bin_val)
                    self.bin_labels_[c].append(bin_label / bin_weight)
                    rank_value.append(bin_rank)
                    bin_idx += 1

                self.n_bins_[c] = bin_idx
                rank_value.append(n_val)

            # transform
            tmp = np.zeros(shape=(n_val,), dtype=np.uint8)
            for i in range(len(rank_value) - 1):
                for j in range(rank_value[i], rank_value[i + 1]):
                    tmp[sortind[j]] = i

            out[c] = tmp

        out = self.__decode(out)

        histogram = out.value_counts()
        histogram = histogram / np.sum(histogram)
        self.indices_flat_ = list(histogram.index)
        self.probs_flat_ = list(histogram.values)
        self.total_bins_ = len(self.probs_flat_)

        return out

    def __decode(self, df):
        decoded = pd.DataFrame()
        for c in df.columns:
            decoded[c] = df[c].apply(lambda x: self.bin_labels_[c][x])

        for c in [
            "generated_token_count",
            "input_token_count",
            "batch_size",
            "params.top_k",
            "is_greedy",
        ]:
            if c in decoded.columns:
                decoded[c] = decoded[c].apply(round)

        if "is_greedy" in decoded.columns:
            decoded[c] = decoded[c].apply(bool)

        return decoded

    def transform(self, data):
        out = pd.DataFrame()

        for c in data.columns:
            vals = data[c].values
            n_val = vals.shape[0]

            tmp = np.zeros(shape=(n_val,), dtype=np.uint8)
            for i in range(n_val):
                found = None
                for bin_idx in range(self.n_bins_[c] - 1):
                    if (
                        vals[i] >= self.bin_edges_[c][bin_idx]
                        and vals[i] < self.bin_edges_[c][bin_idx + 1]
                    ):
                        found = bin_idx

                if found is None:
                    found = self.n_bins_[c] - 1

                tmp[i] = found

            out[c] = tmp

        return self.__decode(out)

    def sample(self, n=1):
        tmp = np.random.choice(
            range(len(self.indices_flat_)), p=self.probs_flat_, size=n, replace=True
        )
        out = pd.DataFrame(
            np.array(self.indices_flat_, dtype=object)[tmp], columns=self.columns_
        )
        return out
