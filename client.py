import base64
import os
import time
from enum import Enum
from typing import Dict, Optional, TypeAlias, Union

import mcmetadata.urls as urls
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import TransportError
from fastapi import HTTPException, Request, Response
from pydantic import BaseModel, computed_field
from pydantic_settings import BaseSettings

from utils import assert_elasticsearch_connection, logger


class ClientConfig(BaseSettings):
    maxpage: int = 1000
    elasticsearch_index_name_prefix: str = ""


client_config = ClientConfig()


# used to package paging keys for url transport
def decode_key(strng: str):
    return base64.b64decode(strng.replace("~", "=").encode(), b"-_").decode()


def encode_key(strng: str):
    return base64.b64encode(strng.encode(), b"-_").decode().replace("=", "~")


class QueryBuilder:

    """
    Utility Class to encapsulate the query construction logic for news-search-api

    """

    VALID_SORT_ORDERS = ["asc", "desc"]
    VALID_SORT_FIELDS = ["publication_date", "indexed_date"]

    def __init__(self, query_text):
        self.query_text = query_text
        self._source = [
            "article_title",
            "normalized_article_title",
            "publication_date",
            "indexed_date",
            "language",
            "full_language",
            "canonical_domain",
            "url",
            "normalized_url",
            "original_url",
        ]
        self._expanded_source = self._source.extend(["text_content", "text_extraction"])

    def _validate_sort_order(self, sort_order: Optional[str]):
        if sort_order and sort_order not in self.VALID_SORT_ORDERS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid sort order (must be on of {', '.join(self.VALID_SORT_ORDERS)})",
            )
        return sort_order

    def _validate_sort_field(self, sort_field: Optional[str]):
        if sort_field and sort_field not in self.VALID_SORT_FIELDS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid sort field (must be on of {', '.join(self.VALID_SORT_FIELDS)})",
            )
        return sort_field

    def _validate_page_size(self, page_size: Optional[int]):
        if page_size and page_size < 1:
            raise HTTPException(
                status_code=400, detail="Invalid page size (must be greater than 0)"
            )
        return page_size

    def basic_query(self, expanded: bool = False) -> Dict:
        default: dict = {
            "_source": self._expanded_source if expanded else self._source,
            "query": {
                "query_string": {
                    "default_field": "text_content",
                    "default_operator": "AND",
                    "query": self.query_text,
                }
            },
        }
        return default

    def overview_query(self):
        query = self.basic_query()
        query.update(
            {
                "aggregations": {
                    "daily": {
                        "date_histogram": {
                            "field": "publication_date",
                            "calendar_interval": "day",
                            "min_doc_count": 1,
                        }
                    },
                    "lang": {"terms": {"field": "language.keyword", "size": 100}},
                    "domain": {"terms": {"field": "canonical_domain", "size": 100}},
                    "tld": {"terms": {"field": "tld", "size": 100}},
                },
                "track_total_hits": True,
            }
        )
        return query

    def terms_query(self, field):
        resct = 200
        aggr_map = {
            "terms": {
                "field": field.name,
                "size": resct,
                "min_doc_count": 10,
                "shard_min_doc_count": 5,
            }
        }
        query = self.basic_query()
        query.update(
            {
                "track_total_hits": False,
                "_source": False,
                "aggregations": {
                    "sample": {
                        "sampler": {"shard_size": 500},
                        "aggregations": {"topterms": aggr_map},
                    }
                },
            }
        )
        return query

    def paged_query(
        self,
        resume: Union[str, None],
        expanded: bool,
        sort_field=Optional[str],
        sort_order=Optional[str],
        page_size=Optional[int],
    ) -> Dict:
        query = self.basic_query(expanded)
        final_sort_field = self._validate_sort_field(sort_field or "publication_date")
        final_sort_order = self._validate_sort_order(sort_order or "desc")
        query.update(
            {
                "size": self._validate_page_size(page_size or 1000),
                "track_total_hits": False,
                "sort": {
                    final_sort_field: {
                        "order": final_sort_order,
                        "format": "basic_date_time_no_millis",
                    }
                },
            }
        )
        if resume:
            # important to use `search_after` instead of 'from' for memory reasons related to paging through more
            # than 10k results
            query["search_after"] = [decode_key(resume)]
        return query

    def article_query(self):
        default: dict = {
            "_source": self._expanded_source,
            "query": {"match": {"_id": self.query_text}},
        }

        return default


class EsClientWrapper:
    # A wrapper to actually make the calls to elasticsearch
    def __init__(self, eshosts, **esopts):
        self.ES = Elasticsearch(eshosts, **esopts)
        self.maxpage = client_config.maxpage
        max_retries = 10
        retries = 0

        while not assert_elasticsearch_connection(self.ES):
            retries += 1
            if retries < max_retries:
                time.sleep(5)
                logger.info(
                    f"Connection to elasticsearch failed {retries} times, retrying"
                )
            else:
                raise RuntimeError(
                    f"Elasticsearch connection failed {max_retries} times, giving up."
                )

        self.index_name_prefix = client_config.elasticsearch_index_name_prefix
        logger.info("Initialized ES client wrapper")

    def get_allowed_collections(self):
        # Only expose indexes with the correct prefix, and add a wildcard as well.

        all_indexes = [
            index
            for index in self.ES.indices.get(index="*")
            if index.startswith(self.index_name_prefix)
        ]
        for aliases in self.ES.indices.get_alias().values():
            # returns: {"index_name":{"aliases":{"alias_name":{"is_write_index":bool}}}}
            for alias in aliases["aliases"].keys():
                if alias not in all_indexes:
                    all_indexes.append(alias)

        all_indexes.append(f"{self.index_name_prefix}-*")

        logger.info(f"Exposed indices: {all_indexes}")
        return all_indexes

    def format_match(self, hit: dict, collection: str, expanded: bool = False):
        src = hit["_source"]
        res = {
            "article_title": src.get("article_title"),
            "normalized_article_title": src.get("normalized_article_title"),
            "publication_date": src.get("publication_date")[:10]
            if src.get("publication_date")
            else None,
            "indexed_date": src.get("indexed_date"),
            "language": src.get("language"),
            "full_langauge": src.get("full_language"),
            "url": src.get("url"),
            "normalized_url": src.get("normalized_url"),
            "original_url": src.get("original_url"),
            "canonical_domain": src.get("canonical_domain"),
            "id": urls.unique_url_hash(src.get("url")),
        }
        if expanded:
            res["text_content"] = src.get("text_content")
            res["text_extraction"] = src.get("text_extraction")
        return res

    def format_day_counts(self, bucket: list):
        return {item["key_as_string"][:10]: item["doc_count"] for item in bucket}

    def format_counts(self, bucket: list):
        return {item["key"]: item["doc_count"] for item in bucket}

    def search_overview(self, collection: str, q: str, req: Request):
        """
        Get overview statistics for a query
        """
        res = self.ES.search(index=collection, body=QueryBuilder(q).overview_query())  # type: ignore [call-arg]
        if not res["hits"]["hits"]:
            raise HTTPException(status_code=404, detail="No results found!")

        total = res["hits"]["total"]["value"]
        tldsum = sum(
            item["doc_count"] for item in res["aggregations"]["tld"]["buckets"]
        )
        return {
            "query": q,
            "total": max(total, tldsum),
            "topdomains": self.format_counts(res["aggregations"]["domain"]["buckets"]),
            "toptlds": self.format_counts(res["aggregations"]["tld"]["buckets"]),
            "toplangs": self.format_counts(res["aggregations"]["lang"]["buckets"]),
            "dailycounts": self.format_day_counts(
                res["aggregations"]["daily"]["buckets"]
            ),
            "matches": [self.format_match(h, collection) for h in res["hits"]["hits"]],
        }

    def search_result(
        self,
        collection: str,
        q: str,
        req: Request,
        resp: Response,
        resume: Union[str, None] = None,
        expanded: bool = False,
        sort_field: Optional[str] = None,
        sort_order: Optional[str] = None,
        page_size: Optional[int] = None,
    ):
        """
        Get the search results for a query (including full text, if `expanded`)
        """
        query = QueryBuilder(q).paged_query(
            resume, expanded, sort_field, sort_order, page_size
        )
        res = self.ES.search(index=collection, body=query)  # type: ignore [call-arg]

        if not res["hits"]["hits"]:
            raise HTTPException(status_code=404, detail="No results found!")

        if len(res["hits"]["hits"]) == (page_size or self.maxpage):
            resume_key = encode_key(str(res["hits"]["hits"][-1]["sort"][0]))
            resp.headers["x-resume-token"] = resume_key

        return [self.format_match(h, collection, expanded) for h in res["hits"]["hits"]]

    def get_terms(
        self,
        collection: str,
        q: str,
        field: str,
        aggr: str,
    ):
        """
        Get top terms associated with a query
        """
        res = self.ES.search(index=collection, body=QueryBuilder(q).terms_query(field))  # type: ignore [call-arg]
        if (
            not res["hits"]["hits"]
            or not res["aggregations"]["sample"]["topterms"]["buckets"]
        ):
            raise HTTPException(status_code=404, detail="No results found!")
        return self.format_counts(res["aggregations"]["sample"]["topterms"]["buckets"])

    def get_article(self, collection: str, id: str, req):
        """
        Get an individual article by id.
        """
        try:
            res = self.ES.search(
                index=collection, body=QueryBuilder(id).article_query()
            )
            hits = res["hits"]["hits"]
        except (TransportError, TypeError, KeyError) as e:
            raise HTTPException(
                status_code=500,
                detail=f"An error occured when searching for article with ID {id}",
            ) from e
        if len(hits) > 0:
            hit = hits[0]
        else:
            raise HTTPException(
                status_code=404, detail=f"An article with ID {id} not found!"
            )

        return self.format_match(hit, collection, True)
