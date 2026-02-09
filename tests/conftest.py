"""Shared fixtures for the data-pipeline test suite."""

from pathlib import Path

import pytest

from src.data_pipeline.cleaning import DataCleaner
from src.data_pipeline.ingestion import FantasyProsIngester
from src.data_pipeline.transformation import DataTransformer
from src.data_pipeline.vor_calculation import VORCalculator

DATA_DIR = Path(__file__).parent.parent / "data" / "raw" / "2025"

# Skip the entire test run when CSV data files are absent (e.g. in CI
# without test-data checked out).
_RANKINGS_FILE = DATA_DIR / "FantasyPros_2025_Draft_ALL_Rankings.csv"
requires_csv_data = pytest.mark.skipif(
    not _RANKINGS_FILE.exists(),
    reason=f"Test CSV data not found at {DATA_DIR}",
)


def pytest_collection_modifyitems(items):
    """Auto-apply the *requires_csv_data* skip to every test that uses a
    fixture which reads from DATA_DIR (ingester, cleaned_data, etc.)."""
    data_fixtures = {
        "ingester", "cleaned_data", "merged_projections",
        "projections_with_scoring", "transformed_data",
    }
    for item in items:
        if data_fixtures & set(item.fixturenames):
            item.add_marker(requires_csv_data)


# ------------------------------------------------------------------
# Lightweight factories – cheap to construct, no I/O
# ------------------------------------------------------------------

@pytest.fixture(scope="module")
def cleaner():
    return DataCleaner()


@pytest.fixture(scope="module")
def transformer():
    return DataTransformer()


# ------------------------------------------------------------------
# Data-reading fixtures – expensive, reused across an entire module
# ------------------------------------------------------------------

@pytest.fixture(scope="module")
def ingester():
    """Ingester pointing at the real 2025 data directory."""
    return FantasyProsIngester(DATA_DIR, year=2025)


@pytest.fixture(scope="module")
def cleaned_data(ingester, cleaner):
    """Full cleaned dataset from the real 2025 CSVs."""
    raw = ingester.read_all()
    return cleaner.clean_all(raw)


@pytest.fixture(scope="module")
def merged_projections(transformer, cleaned_data):
    """Merged projections DataFrame (before scoring/rankings)."""
    return transformer.merge_projections(
        cleaned_data["qb"],
        cleaned_data["flex"],
        cleaned_data["k"],
        cleaned_data["dst"],
    )


@pytest.fixture(scope="module")
def projections_with_scoring(transformer, merged_projections):
    """Merged projections with scoring variants calculated."""
    return transformer.calculate_scoring_variants(merged_projections)


@pytest.fixture(scope="module")
def transformed_data(transformer, cleaned_data):
    """Full transform output (merge + scoring + rankings + player IDs)."""
    return transformer.transform(cleaned_data)


@pytest.fixture(scope="module")
def vor_calculator():
    return VORCalculator()
