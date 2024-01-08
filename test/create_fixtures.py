import copy
import datetime as dt
import logging
from random import randrange
from test import ELASTICSEARCH_URL, INDEX_NAME, NUMBER_OF_TEST_STORIES

import mcmetadata.titles as titles
import mcmetadata.urls as urls
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ConflictError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

es_client = Elasticsearch(hosts=[ELASTICSEARCH_URL], verify_certs=False)

# first create the index
es_mappings = {
    "properties": {
        "original_url": {"type": "keyword"},
        "url": {"type": "keyword"},
        "normalized_url": {"type": "keyword"},
        "canonical_domain": {"type": "keyword"},
        "publication_date": {"type": "date", "ignore_malformed": True},
        "language": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
        "full_language": {"type": "keyword"},
        "text_extraction": {"type": "keyword"},
        "article_title": {
            "type": "text",
            "fields": {"keyword": {"type": "keyword"}},
        },
        "normalized_article_title": {
            "type": "text",
            "fields": {"keyword": {"type": "keyword"}},
        },
        "text_content": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
        "indexed_date": {"type": "date"},
    }
}

es_client.indices.create(  # type: ignore [call-arg]
    index=INDEX_NAME, mappings=es_mappings, ignore=400
)  # Ignore 400 to handle index already exists
logger.info(
    f"Index '{INDEX_NAME}' with field mappings created successfully (or already exists."
)

# now import the fixtures
base_fixture = {
    "original_url": "http://example.com/article/",
    "url": "http://example.com/article/",
    "normalized_url": "http://example.com/article/",
    "article_title": "Sample Article ",
    "normalized_article_title": "sample_article_",
    "text_content": "This is the content of the sample article ",
    "canonical_domain": "example.com",
    "publication_date": "2023-11-01",
    "indexed_date": "2023-12-01T12:12:12",
    "language": "en",
    "full_language": "en-us",
    "text_extraction": "trafilatura",
}

imported_count = 0
for idx in range(0, NUMBER_OF_TEST_STORIES):
    fixture = copy.copy(base_fixture)
    fixture["url"] += str(idx)
    fixture["original_url"] = fixture["url"]
    fixture["normalized_url"] = urls.normalize_url(fixture["url"])  # type: ignore [assignment]
    fixture["article_title"] += str(idx)
    fixture["normalized_article_title"] = titles.normalize_title(
        fixture["article_title"]
    )
    fixture["text_content"] += str(idx)
    fixture["publication_date"] = (
        dt.date(2023, 1, 1) + dt.timedelta(days=randrange(365))
    ).isoformat()
    random_time_on_day = dt.datetime.fromisoformat(
        fixture["publication_date"]
    ) + dt.timedelta(minutes=randrange(1440))
    fixture["indexed_date"] = random_time_on_day.isoformat()
    unique_hash = urls.unique_url_hash(fixture["url"])
    try:
        response = es_client.index(index=INDEX_NAME, id=unique_hash, document=fixture)
        imported_count += 1
    except ConflictError:
        logger.warning("  duplicate fixture, ignoring")
logger.info(f"  Imported {imported_count}")
