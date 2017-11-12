from os import path
from shutil import rmtree
from unittest import TestCase
import mock
import pandas as pd
import pandas.util.testing as pdt
from datetime import datetime

from .. import api
from .. import live_data_api

TEST_DIR = path.dirname(__file__)


def _read_data_frame_csv(filename):
    return pd.read_csv(filename, parse_dates=True, index_col=0)

def web_reader(ticker, source, *args, **kwargs):
    filename = path.join(TEST_DIR, "mock-stock-data",
                         ticker + "." + source + ".csv")
    start = kwargs["start"] if "start" in kwargs else None
    end = kwargs["end"] if "end" in kwargs else None
    return _read_data_frame_csv(filename).ix[start:end]

def _read_quote(filename):
    """
    Read the file containing json response of Google finance API
    :param filename: the name of the file
    :return:
    """
    with open(filename, "r") as quote_file:
        return quote_file.read()

def fetch_quote_data(ticker):
    """
    Retrive quote under Google finance API from a file
    :param ticker: the instrument ticker
    :return:
    """
    filename = path.join(TEST_DIR, "mock-stock-data", ticker + ".json")
    return _read_quote(filename)

def fetch_quote_txt_data(ticker):
    """
    Retrive quote under Google finance API from a file
    :param ticker: the instrument ticker
    :return:
    """
    filename = path.join(TEST_DIR, "mock-stock-data", ticker + ".txt")
    return _read_quote(filename)

def today():
    return '2017-11-2'

@mock.patch(api.__name__ + ".mkdir")
def test_mkdir_if_not_exist(m_mkdir):
    dir_path = path.join(TEST_DIR, "dummy")
    api.mkdir_if_not_exist(dir_path)
    m_mkdir.assert_called_with(dir_path)


class DataReaderTest(TestCase):
    GoogleTicker = "GOOG"
    YahooSource = "yahoo"
    stock_data_dir = path.join(TEST_DIR, "stock-data")

    def setUp(self):
        """
        Prepare env before running unit tests
        :return:
        """
        api.HOME_DIR = TEST_DIR
        patch_data_reader = mock.patch(api.__name__ + ".web.DataReader",
                              side_effect=web_reader)
        self.m_web_reader = patch_data_reader.start()
        self.addCleanup(patch_data_reader.stop)
        self.reader = api.DataReader()

        patch_time_now = mock.patch(api.__name__ + "._today",
                                    side_effect=today)
        self.m_patch_time_now = patch_time_now.start()
        self.addCleanup(patch_time_now.stop)

        patch_get_quote = mock.patch(live_data_api.__name__
                                     + ".fetch_quote_json_data",
                                     side_effect=fetch_quote_data)
        self.m_fetch_quote_data = patch_get_quote.start()
        self.addCleanup(patch_get_quote.stop)

        patch_get_quote_date = mock.patch(live_data_api.__name__
                                          + ".fetch_quote_txt_data",
                                          side_effect=fetch_quote_txt_data)
        self.m_fetch_quote_data_date = patch_get_quote_date.start()
        self.addCleanup(patch_get_quote_date.stop)

    def test_cache_dir(self):
        self.assertEqual(self.reader.cache_dir, self.stock_data_dir)

    def test_data_reader(self):
        """
        Test if the web-retrieved data are correct
        :return:
        """
        ticker = self.GoogleTicker
        end = "2017-11-01"
        df = api.data_reader(ticker, end=end,
                             enable_cache=False, use_reference=False)
        self.m_web_reader.assert_called_with(
            ticker, self.YahooSource, start="1926-01-01", end=end
        )
        expected = web_reader(ticker, "yahoo")[:end]
        pdt.assert_frame_equal(df, expected)
        rmtree(self.stock_data_dir)

    def test_data_reader_with_live_quote(self):
        """
        Test if the dataframe is successfully updated with the live quote
        :return:
        """
        ticker = self.GoogleTicker
        df = api.data_reader(ticker, end=None,
                             enable_cache=False, use_reference=False)
        end = today()
        columns = ["Open", "High", "Low", "Close", "Volume"]
        expected = web_reader(ticker, "yahoo")[:end][columns]
        pdt.assert_frame_equal(df[columns], expected)
        pdt.assert_almost_equal(df.ix[end]["Adj Close"], 1031.26)
        rmtree(self.stock_data_dir)

    def test_cache_file_consistency(self):
        """
        Test if the cached file is created and if the data inside are valid
        :return:
        """
        ticker = self.GoogleTicker
        end_caching = "2017-09-02"
        df_caching = api.data_reader(ticker, end=end_caching,
                                     use_reference=False)
        cached_filename = path.join(self.stock_data_dir, 'GOOG.yahoo.csv')
        self.assertTrue(path.isfile(cached_filename));
    def test_cache_file_consistency(self):
        """
        Test if the cached file is created and if the data inside are valid
        :return:
        """
        ticker = self.GoogleTicker
        end_caching = "2017-09-02"
        df_caching = api.data_reader(ticker, end=end_caching,
                                     use_reference=False)
        cached_filename = path.join(self.stock_data_dir, 'GOOG.yahoo.csv')
        self.assertTrue(path.isfile(cached_filename));

    def test_data_reader_with_cache(self):
        """
        Tests if the the web datareader is not called twice for the same time
        range.
        Test if the dataframe concatenation of cached and web-retrieved data
        works.
        :return:
        """
        ticker = self.GoogleTicker
        end_caching = "2017-09-01"
        df_caching = api.data_reader(ticker, end=end_caching,
                                     use_reference=False)
        self.m_web_reader.assert_called_with(
            ticker, self.YahooSource, start="1926-01-01", end=end_caching
        )
        end = "2017-11-02"
        df = api.data_reader(ticker, end=end, use_reference=False)
        self.m_web_reader.assert_called_with(
            ticker, self.YahooSource, start="2017-09-01", end=end
        )
        expected = web_reader(ticker, "yahoo")[:end]
        pdt.assert_frame_equal(df_caching, expected[:end_caching])
        pdt.assert_frame_equal(df, expected)
        rmtree(self.stock_data_dir)

    def test_data_reader_using_reference(self):
        """
        Tests if the the web datareader is not called twice for the same time
        range.
        Test if the dataframe concatenation of cached and web-retrieved data
        works.
        :return:
        """
        ticker = self.GoogleTicker
        end_caching = "2017-09-01"
        df_caching = api.data_reader(ticker, end=end_caching,
                                     use_reference=True)
        self.m_web_reader.assert_called_with(
            ticker, self.YahooSource, start="1926-01-01", end=end_caching
        )
        end = "2017-11-02"
        df = api.data_reader(ticker, end=end, use_reference=True)
        self.m_web_reader.assert_called_with(
            ticker, self.YahooSource, start="2017-09-01", end=end
        )
        expected = web_reader(ticker, "yahoo")[:end]
        pdt.assert_frame_equal(df_caching, expected[:end_caching])
        pdt.assert_frame_equal(df, expected)
        rmtree(self.stock_data_dir)

    @classmethod
    def tearDownClass(cls):
        if path.exists(cls.stock_data_dir):
            rmtree(cls.stock_data_dir)

class LiveDataAPITest(TestCase):
    GoogleTicker = "GOOG"

    def setUp(self):
        """
        Prepare env before running unit tests
        :return:
        """
        api.HOME_DIR = TEST_DIR
        patch_get_quote = mock.patch(live_data_api.__name__
                                     + ".fetch_quote_json_data",
                                   side_effect=fetch_quote_data)
        self.m_fetch_quote_data = patch_get_quote.start()
        self.addCleanup(patch_get_quote.stop)

        patch_get_quote_date = mock.patch(live_data_api.__name__
                                     + ".fetch_quote_txt_data",
                                     side_effect=fetch_quote_txt_data)
        self.m_fetch_quote_data_date = patch_get_quote_date.start()
        self.addCleanup(patch_get_quote_date.stop)

    def test_realtime_data_reader(self):
        """
        Test if the dataframe contains realtime price in "Adj close" for the
        current day when end=None
        """
        ticker = self.GoogleTicker
        quote = live_data_api.fetch_live_quote(ticker)
        self.assertEqual(datetime(2017, 11, 2, 20, 0), quote[0])
        self.assertEqual(1031.26, quote[1])
