"""
Kevin Fung
Github: kkf18
"""

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib as mpl


class BaseData:

    def __init__(self, dfs=None, dicts=None, datasets=None):
        """
        Not all child classes will require these data dictionaries.
        """
        if dfs is None:
            self.dfs = {}
        else:
            self.dfs = dfs
            self.dicts = {}
            # The first instantiation with DataFrames should also generate a corresponding grouped dict format.
            # Regardless of sample inconsistency.
            for data in self.dfs.keys():
                self.dicts[data] = self._df2dict(self.dfs[data])

        if (dfs is None) & (dicts is None):
            self.dicts = {}
        if (dfs is None) & (dicts is not None):
            self.dicts = dicts

        if datasets is None:
            self.datasets = {}
        else:
            self.datasets = datasets

        self.CB_color_cycle = ['#a65628', '#984ea3',
                               '#999999', '#e41a1c', '#dede00']

        self.sets = {}

    def cache_data(self, *args):
        """

        """
        for data in args:
            assert data in self.dfs.keys(), "{} does not exist in class".format(data)

            self.dfs[data].cache()

            if data in self.dicts.keys():
                for feat, df in self.dicts[data].items():
                    df.cache()

    def _dict2df(self, ow_dict, datename="datetime", valname="value", sort=True, drop_nulls=True):
        """Convert a dictionary of timeseries features into a Spark DataFrame of columns of these features.
        Each DataFrame in the dictionary must have the same formatted datetime columns and sizes!
        Args:
            ow_dict (dict): Input dictionary of features
            datename (str): Name of the column to join by
            valname (str): Name of the value column

        Returns:
            Spark DataFrame: DataFrame with columns of features
        """
        for df in ow_dict.values():
            assert datename in df.schema.names, "Inconsistent datetime column names"
            assert valname in df.schema.names, "Inconsistent value column names"

        if sort:
            # Must pull the smallest sampled kv pair first:
            counter = {}
            for feat, df in ow_dict.items():
                counter[str(df.count())] = feat

            smallest_feat = counter[str(min([int(i) for i in list(counter.keys())]))]

            dfs = ow_dict[smallest_feat]
            dfs = dfs.select(dfs[datename], dfs[valname].alias(smallest_feat))

        else:
            # Assume everything the same size, just pull the first kv pair in dict.
            dfs = ow_dict[list(ow_dict.keys())[0]]
            dfs = dfs.select(dfs[datename], dfs[valname].alias(list(ow_dict.keys())[0]))

        for i, (head, df) in enumerate(ow_dict.items()):
            if sort:
                if head == smallest_feat:
                    continue
            else:
                if i == 0:
                    continue

            df = df.select(df[datename], df[valname].alias(head))
            dfs = dfs.join(df, df[datename] == dfs[datename], how="left").drop(df[datename])

        #       precautionary measure to remove any possible nulls from the joining.
        if drop_nulls:
            dfs = dfs.na.drop()

        return dfs

    def _df2dict(self, df):
        """Convert a Spark DataFrame of columns of timeseries features into an organised dictionary.
            EXAMPLE:
                ow_dict = {feature name : timeseries dataframe}
        Args:
            df (Spark DataFrame): input Spark DataFrame with different features
            date_head (str): column name of datetime in Spark DataFrame

        Returns:
            Dict: organised dictionary of features from Spark DataFrame
        """
        assert "datetime" in df.columns, "no datetime column in given DataFrame!"

        ow_dict = {}
        for feat in df.columns:
            if feat == "datetime":
                continue
            ow_dict[feat] = df.select(df["datetime"], df[feat].alias("value"))
        return ow_dict

    def plot(self, title, dicts_dfs, third_axis=None, marker_dict=None, is_sets=False):
        """Plot multiple timeseries Spark DataFrames onto a figure, x axis = time, y axis = value.
        Args:
            title (str): Name of Spark DataFrame
            dicts_dfs (dict): {data: [WHP, DHP], data: [DHT, Qliq]}
            third_axis (dict): {data: [WHP, DHP], data: [DHT, Qliq]}
            marker_dict (dict): dict of lists of dataframes with desired marker styles {marker:list}

        Returns:
            None
        """
        if is_sets:
            # functionality intended for visualising sets
            # where we only have dataframes
            for data in dicts_dfs.keys():
                assert data in self.sets.keys(), "data does not exist in sets"

            for data in dicts_dfs.keys():
                # Transform dataframe to dictionary format
                self.dicts[data] = self._df2dict(self.sets[data])

            if third_axis:
                for data in third_axis.keys():
                    assert data in self.sets.keys(), "data does not exist in sets"

                for data in third_axis.keys():
                    # Transform dataframe to dictionary format
                    self.dicts[data] = self._df2dict(self.sets[data])

        for data in dicts_dfs.keys():
            assert data in self.dicts.keys(), "data does not exist in dictionary format"

        plt.gca().set_prop_cycle(None)

        fig, axs = plt.subplots(1, 1, figsize=(24, 8))
        axs = self._plot(axs, dicts_dfs, marker_dict)
        axs.set_title(title, fontsize=16)
        axs.set_xlabel("datetime", fontsize=16)
        axs.set_ylabel("value", fontsize=16)

        axs.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d %H:%M"))
        axs.xaxis.set_minor_formatter(mdates.DateFormatter("%Y-%m-%d"))

        axs.legend(loc="best")

        if third_axis:
            for data in third_axis.keys():
                assert data in self.dicts.keys(), "data does not exist in dictionary format"

            mpl.rcParams['axes.prop_cycle'] = mpl.cycler(color=self.CB_color_cycle)

            ax2 = axs.twinx()  # instantiate a second axes that shares the same x-axis
            ax2 = self._plot(ax2, third_axis, marker_dict)

            ax2.set_ylabel('value')  # we already handled the x-label with ax1
            ax2.tick_params(axis='y', labelcolor="black")

            handles1, labels1 = axs.get_legend_handles_labels()
            handles2, labels2 = ax2.get_legend_handles_labels()
            axs.get_legend().remove()

            axs.legend(handles1 + handles2, labels1 + labels2, loc='best')

        fig.tight_layout(pad=0.4, w_pad=0.5, h_pad=3.0)
        return fig, axs

    def _plot(self, ax, dict_dfs, marker_dict):
        for data, feat_list in dict_dfs.items():
            for feat in feat_list:
                ts_pd = self.dicts[data][feat].orderBy("datetime").toPandas()
                y = ts_pd['value'].tolist()
                x = ts_pd['datetime'].tolist()

                if marker_dict is not None:
                    marked = False
                    for marker, marker_feat_list in marker_dict.items():
                        if feat in marker_feat_list:
                            ax.plot(x, y, marker, label=feat)
                            ax.grid(True)
                            marked = True

                    if not marked:
                        ax.plot(x, y, '--', label=feat)
                        ax.grid(True)
                else:
                    ax.plot(x, y, '*--', label=feat)
                    ax.grid(True)
        return ax