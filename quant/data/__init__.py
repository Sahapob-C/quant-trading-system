"""Data handlers for loading market data from various sources.

Supported sources:
  - Historic: Load OHLCV parquet files from disk
  - Alpaca: Stream live data from Alpaca broker API
  - (Future) Yahoo Finance, IQFeed, etc.
"""
from quant.data.base import DataHandler
from quant.data.historic import HistoricParquetDataHandler

__all__ = ["DataHandler", "HistoricParquetDataHandler"]
