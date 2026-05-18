from app.formats import FORMATTERS
from app.jobs.models import OutputFormat


def test_registry_covers_all_formats():
    assert set(FORMATTERS.keys()) == set(OutputFormat)
