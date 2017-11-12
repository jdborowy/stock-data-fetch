from os import path, mkdir
from datetime import datetime
import numpy as np
import pandas as pd
import pandas_datareader.data as web
from live_data_api import fetch_live_quote

HOME_DIR = path.expanduser("~")

def _today():
    return datetime.now().date()

def _market_data_filename(source, ticker):
    if source == "reference":
        return ticker + ".csv"
    else:
        return ticker + "." + source + ".csv"

def mkdir_if_not_exist(dir_path):
    if not path.exists(dir_path):
        mkdir(dir_path)

class DataReader(object):
    OpenCol = "Open"
    CloseCol = "Close"
    AdjCloseCol = "Adj Close"
    HighCol = "High"
    LowCol = "Low"
    VolumeCol = "Volume"

    origin = "1926-01-01"

    def __init__(self, cache_dir=None, enable_cache=True, use_reference=True):
        """

        :param cache_dir:
        :param enable_cache:
        :param use_reference:
        """
        self.cache_dir = cache_dir or path.join(HOME_DIR, "stock-data")
        self.enable_cache = enable_cache
        self.use_reference = use_reference
        mkdir_if_not_exist(self.cache_dir)

    def _read_cache(self, ticker, source):
        """
        Read market data from a file identified by <ticker>.<source>.csv
        :param ticker: the instrument ticker
        :param source: the source vendor of market data
        :param end: the end date of the time series range
        :return: a data frame containing the desired market data
        """
        filepath = path.join(self.cache_dir, _market_data_filename(source,
                                                                   ticker))
        if not path.isfile(filepath):
            return None
        return pd.read_csv(filepath, parse_dates=True, index_col=0)

    def _fetch_web_data(self, ticker, source, start, end):
        """
        Fetch data from the web using pandas web api and normalize data casting
        all columns as float64 and filling out Adj Close if the column doesn't
        exist
        :param ticker: the instrument ticker
        :param source: the source vendor of market data
        :param start: then begin date of the time series range
        :param end: then end date of the time series range
        :return: a data frame containing the web normalized market data
        """
        web_df = web.DataReader(ticker, source, start=start, end=end)
        web_df[self.OpenCol].astype(np.float64)
        web_df[self.CloseCol].astype(np.float64)
        web_df[self.HighCol].astype(np.float64)
        web_df[self.LowCol].astype(np.float64)
        web_df[self.VolumeCol].astype(np.float64)
        if self.AdjCloseCol in web_df.columns:
            web_df[self.AdjCloseCol].astype(np.float64)
        else:
            web_df[self.AdjCloseCol] = web_df[self.CloseCol]
        return web_df[[self.OpenCol, self.HighCol, self.LowCol, self.CloseCol,
                       self.AdjCloseCol, self.VolumeCol]]

    def _read_raw_data(self, ticker, source, start, end):
        """
        Fetch data from the cache as much as possible and using the web api
        to retrieve the missing data
        :param ticker: the instrument ticker
        :param source: the source vendor of market data
        :param start: then begin date of the time series range
        :param end: then end date of the time series range
        :return: a data frame containing the market data
        """
        if not self.enable_cache:
            return self._fetch_web_data(ticker, source, start=start, end=end)

        cache_df = self._read_cache(ticker, source)
        if cache_df is None:
            return self._fetch_web_data(ticker, source, start=start, end=end)

        cache_end = str(cache_df.index[-1].date())
        if cache_end > end:
            return cache_df.ix[:end]

        web_df = self._fetch_web_data(ticker, source, start=str(cache_end), end=end)
        return web_df.combine_first(cache_df)

    def _save_raw_data(self, ticker, source, df):
        """
        Save the data frame under the cache folder with the following format:
        <ticker>.<source>.csv if the data come from one identified source
        <ticker>.csv is it's the reference data
        :param ticker: the instrument ticker
        :param source: the source vendor of market data
        :param df: the data frame to save
        :return:
        """
        filename = path.join(self.cache_dir, _market_data_filename(source,
                                                                   ticker))
        df.to_csv(filename, header=True)

    def _combine_ref_and_raw_data(self, ref_df, raw_df):
        """
        Combine the reference data frame and the raw data frame coming from an
        unique source. Here we just use the the raw data when the reference data
        are missing.
        In a further version we would apply a strategy to improve the reference
        with the raw data
        :param ref_df: the reference data frame
        :param raw_df: the raw data frame
        :return: the combined data frame
        """
        if ref_df is None:
            return raw_df

        ref_end = str(ref_df.index[-1].date())
        return ref_df.combine_first(raw_df.ix[ref_end:])

    def _update_with_live_quote(self, ticker, df):
        quote = fetch_live_quote(ticker)

        if quote is not None:
            quote_date = quote[0].date()
            quote_value = quote[1]
            if df.index[-1].date() == quote_date:
                df.ix[quote_date, self.AdjCloseCol] = quote_value

    def read(self, ticker, source="yahoo", end=None):
        """
        API to fetch source or reference data from the cache and/or the web when
        needed.
        :param ticker: the instrument ticker
        :param source: the source vendor of market data
        :param end: then end date of the time series range
        :return:
        """
        today = str(_today())
        end = end or today

        raw_df = self._read_raw_data(ticker, source, start=self.origin, end=end)
        self._save_raw_data(ticker, source, raw_df)
        df = raw_df

        if self.use_reference:
            ref_df = self._read_cache(ticker, "reference")
            df = self._combine_ref_and_raw_data(ref_df, raw_df)

        if end == today:
            self._update_with_live_quote(ticker, df)

        self._save_raw_data(ticker, "reference", df)

        return df

def data_reader(ticker, source="yahoo", end=None,
                enable_cache=True, use_reference=True):
    reader = DataReader(enable_cache=enable_cache, use_reference=use_reference)
    return reader.read(ticker, source, end)
