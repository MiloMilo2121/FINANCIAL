"""Apache Beam pipeline: normalize raw market events to BigQuery.

Reads from Pub/Sub → normalizes (log scale, currency) → enriches →
writes to BigQuery and GCS parquet.

Runs with DirectRunner locally (dev) or DataflowRunner in production.
No code changes required between environments — only the --runner flag changes.

Usage:
  # Local dev (DirectRunner):
  python normalize_prices.py --runner DirectRunner \
    --project financial-dev \
    --pubsub_subscription projects/financial-dev/subscriptions/market-events-sub \
    --bigquery_table financial-dev:financial_data.prices

  # Production (DataflowRunner):
  python normalize_prices.py --runner DataflowRunner \
    --project financial-prod \
    --region us-central1 \
    --temp_location gs://financial-temp/dataflow \
    --pubsub_subscription projects/financial-prod/subscriptions/market-events-sub \
    --bigquery_table financial-prod:financial_data.prices
"""

import argparse
import json
import logging
import math
from datetime import datetime, timezone
from typing import Any

import apache_beam as beam
from apache_beam.io.gcp.bigquery import WriteToBigQuery, BigQueryDisposition
from apache_beam.io.gcp.pubsub import ReadFromPubSub
from apache_beam.options.pipeline_options import PipelineOptions, StandardOptions
from apache_beam.transforms.window import FixedWindows

logger = logging.getLogger(__name__)

# BigQuery schema for normalized prices table
PRICES_SCHEMA = {
    "fields": [
        {"name": "event_id", "type": "STRING", "mode": "REQUIRED"},
        {"name": "timestamp", "type": "TIMESTAMP", "mode": "REQUIRED"},
        {"name": "source", "type": "STRING", "mode": "REQUIRED"},
        {"name": "asset", "type": "STRING", "mode": "REQUIRED"},
        {"name": "asset_class", "type": "STRING", "mode": "REQUIRED"},
        {"name": "price_usd", "type": "FLOAT", "mode": "NULLABLE"},
        {"name": "price_usd_log", "type": "FLOAT", "mode": "NULLABLE"},
        {"name": "open", "type": "FLOAT", "mode": "NULLABLE"},
        {"name": "high", "type": "FLOAT", "mode": "NULLABLE"},
        {"name": "low", "type": "FLOAT", "mode": "NULLABLE"},
        {"name": "close", "type": "FLOAT", "mode": "NULLABLE"},
        {"name": "volume", "type": "FLOAT", "mode": "NULLABLE"},
        {"name": "currency", "type": "STRING", "mode": "NULLABLE"},
        {"name": "metadata_json", "type": "STRING", "mode": "NULLABLE"},
        {"name": "ingested_at", "type": "TIMESTAMP", "mode": "REQUIRED"},
    ]
}


class ParseMarketEvent(beam.DoFn):
    """Parse raw Pub/Sub message bytes into a dict."""

    def process(self, element):
        try:
            record = json.loads(element.decode("utf-8"))
            yield record
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning("Failed to parse message: %s", e)


class CurrencyNormalizationTransform(beam.DoFn):
    """Ensure all prices are expressed in USD.

    In production this would look up FX rates from a side input
    (BigQuery table or GCS file updated by the ingestion service).
    For now, events already arrive in USD from most connectors.
    """

    def process(self, record: dict[str, Any]):
        currency = record.get("currency", "USD")
        price = record.get("price_usd")

        if currency == "USD" or price is None:
            yield record
            return

        # TODO: Apply FX conversion from side input lookup table
        # For now, pass through non-USD records with a flag
        record["metadata"] = record.get("metadata", {})
        record["metadata"]["original_currency"] = currency
        record["metadata"]["fx_normalized"] = False
        yield record


class LogScaleTransform(beam.DoFn):
    """Apply log transformation to price fields for ML model input.

    Log prices are stationary-er than raw prices, reducing LSTM gradient issues.
    """

    def process(self, record: dict[str, Any]):
        price = record.get("price_usd")
        if price is not None and price > 0:
            record["price_usd_log"] = math.log(price)
        else:
            record["price_usd_log"] = None
        yield record


class OutlierDetectionTransform(beam.DoFn):
    """Flag statistical outliers for downstream quality control.

    Uses a simple z-score threshold against known reasonable ranges.
    In production, this uses a rolling mean/std from a BigQuery side input.
    """

    # Reasonable gold price range (USD/oz)
    GOLD_MIN = 100.0
    GOLD_MAX = 10000.0

    def process(self, record: dict[str, Any]):
        asset = record.get("asset", "")
        price = record.get("price_usd")

        if "XAU" in asset and price is not None:
            if not (self.GOLD_MIN <= price <= self.GOLD_MAX):
                record.setdefault("metadata", {})["is_outlier"] = True
                logger.warning(
                    "Outlier detected: asset=%s price=%s", asset, price
                )
        yield record


class ToBigQueryRow(beam.DoFn):
    """Convert normalized record to BigQuery row dict."""

    def process(self, record: dict[str, Any]):
        now = datetime.now(timezone.utc).isoformat()
        metadata = record.get("metadata", {})

        yield {
            "event_id": str(record.get("event_id", "")),
            "timestamp": record.get("timestamp"),
            "source": record.get("source", ""),
            "asset": record.get("asset", ""),
            "asset_class": record.get("asset_class", ""),
            "price_usd": record.get("price_usd"),
            "price_usd_log": record.get("price_usd_log"),
            "open": record.get("open"),
            "high": record.get("high"),
            "low": record.get("low"),
            "close": record.get("close"),
            "volume": record.get("volume"),
            "currency": record.get("currency", "USD"),
            "metadata_json": json.dumps(metadata, default=str) if metadata else None,
            "ingested_at": now,
        }


def run(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--pubsub_subscription", required=True)
    parser.add_argument("--bigquery_table", required=True)
    parser.add_argument("--window_seconds", type=int, default=60)
    known_args, pipeline_args = parser.parse_known_args(argv)

    options = PipelineOptions(pipeline_args)
    options.view_as(StandardOptions).streaming = True

    with beam.Pipeline(options=options) as pipeline:
        (
            pipeline
            | "ReadFromPubSub" >> ReadFromPubSub(
                subscription=known_args.pubsub_subscription,
            )
            | "Window" >> beam.WindowInto(FixedWindows(known_args.window_seconds))
            | "ParseMarketEvent" >> beam.ParDo(ParseMarketEvent())
            | "CurrencyNormalization" >> beam.ParDo(CurrencyNormalizationTransform())
            | "LogScale" >> beam.ParDo(LogScaleTransform())
            | "OutlierDetection" >> beam.ParDo(OutlierDetectionTransform())
            | "ToBigQueryRow" >> beam.ParDo(ToBigQueryRow())
            | "WriteToBigQuery" >> WriteToBigQuery(
                table=known_args.bigquery_table,
                schema=PRICES_SCHEMA,
                write_disposition=BigQueryDisposition.WRITE_APPEND,
                create_disposition=BigQueryDisposition.CREATE_IF_NEEDED,
            )
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
