#!/usr/bin/env python3
import base64
import os
import time
from enum import Enum
from typing import Dict, Optional, TypeAlias, Union
from urllib.parse import quote_plus

import mcmetadata.urls as urls
import sentry_sdk
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import TransportError
from fastapi import Body, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from utils import (
    assert_elasticsearch_connection,
    env_to_dict,
    env_to_list,
    load_config,
    logger,
)

def getenv_float(name: str, defval: float | None) -> float | None:
    """
    fetch environment variable with name `name`
    if not set, return defval
    if set to empty string, return None
    else interpret as floating point number
    """
    val = os.getenv(name)
    if val is None:
        return defval
    if val == "":
        return None
    return float(val)


if os.getenv("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        traces_sample_rate=getenv_float("TRACING_SAMPLE_RATE", 1.0),
        profiles_sample_rate=getenv_float("PROFILES_SAMPLE_RATE", 1.0),
        integrations=[
            StarletteIntegration(transaction_style="url"),
            FastApiIntegration(transaction_style="url"),
        ],
    )

app = FastAPI()


class ApiVersion(str, Enum):
    v1 = "1.3.3"


config = load_config()
config["termfields"] = env_to_list("TERMFIELDS") or config.get("termfields", [])
config["termaggrs"] = env_to_list("TERMAGGRS") or config.get("termaggrs", [])
config["eshosts"] = env_to_list("ESHOSTS") or config.get(
    "eshosts", ["http://localhost:9200"]
)
config["esopts"] = env_to_dict("ESOPTS") or config.get("esopts", {})
config["maxpage"] = int(os.getenv("MAXPAGE", config.get("maxpage", 1000)))
config["title"] = os.getenv("TITLE", config.get("title", ""))
config["description"] = os.getenv("DESCRIPTION", config.get("description", ""))
config["debug"] = str(os.getenv("DEBUG", config.get("debug", False))).lower() in (
    "true",
    "1",
    "t",
)

ELASTICSEARCH_INDEX_NAME_PREFIX = os.getenv("ELASTICSEARCH_INDEX_NAME_PREFIX", "")

ES = Elasticsearch(config["eshosts"], **config["esopts"])

max_retries = 10
retries = 0
while not assert_elasticsearch_connection(ES):
    retries += 1
    if retries < max_retries:
        time.sleep(5)
        logger.info(f"Connection to elasticsearch failed {retries} times, retrying")
    else:
        raise RuntimeError(
            f"Elasticsearch connection failed {max_retries} times, giving up."
        )


def get_allowed_collections():
    # Only expose indexes with the correct prefix, and add a wildcard as well.

    all_indexes = [
        index
        for index in ES.indices.get(index="*")
        if index.startswith(ELASTICSEARCH_INDEX_NAME_PREFIX)
    ]
    for aliases in ES.indices.get_alias().values():
        # returns: {"index_name":{"aliases":{"alias_name":{"is_write_index":bool}}}}
        for alias in aliases["aliases"].keys():
            if alias not in all_indexes:
                all_indexes.append(alias)
    all_indexes.append(f"{ELASTICSEARCH_INDEX_NAME_PREFIX}-*")

    logger.info(f"Exposed indices: {all_indexes}")
    return all_indexes


# A little annoying- the list comprehension could be removed in py3.11 by using StrEnum, but this is backwards compatable.
Collection = Enum("Collection", [f"{kv}:{kv}".split(":")[:2] for kv in get_allowed_collections()])  # type: ignore [misc]
TermField = Enum("TermField", [f"{kv}:{kv}".split(":")[:2] for kv in config["termfields"]])  # type: ignore [misc]
TermAggr = Enum("TermAggr", [f"{kv}:{kv}".split(":")[:2] for kv in config["termaggrs"]])  # type: ignore [misc]


tags = [
    {
        "name": "info",
        "description": "Informational endpoints with human-readable responses to fill the hierarchy.",
    },
    {
        "name": "data",
        "description": "Data endpoints with machine-readable responses to interact with the collection indexes.",
    },
]
if config["debug"]:
    tags.append(
        {
            "name": "debug",
            "description": "Debugging endpoints with raw data from the backend, not suitable to be enabled in production.",
        }
    )


app = FastAPI(
    version=list(ApiVersion)[-1].value, docs_url=None, redoc_url=None, openapi_url=None
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "HEAD", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["x-resume-token", "x-api-version"],
)


@app.middleware("http")
async def add_api_version_header(req: Request, call_next):
    res = await call_next(req)
    res.headers["x-api-version"] = f"{req.app.version}"
    return res


v1 = FastAPI(
    title=config.get("title", "Interactive API") + " Docs",
    description=config.get("description", "A wrapper API for ES indexes."),
    version=ApiVersion.v1.value,
    openapi_tags=tags,
)


VALID_SORT_ORDERS = ["asc", "desc"]
VALID_SORT_FIELDS = ["publication_date", "indexed_date"]


class Query(BaseModel):
    q: str


class PagedQuery(Query):
    resume: Union[str, None] = None
    expanded: bool = False
    sort_field: Optional[str] = None
    sort_order: Optional[str] = None
    page_size: Optional[int] = None


def encode(strng: str):
    return base64.b64encode(strng.encode(), b"-_").decode().replace("=", "~")


def decode(strng: str):
    return base64.b64decode(strng.replace("~", "=").encode(), b"-_").decode()


def cs_basic_query(q: str, expanded: bool = False) -> Dict:
    default: dict = {
        "_source": [
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
        ],
        "query": {
            "query_string": {
                "default_field": "text_content",
                "default_operator": "AND",
                "query": q,
            }
        },
    }
    if expanded:
        default["_source"].extend(["text_content", "text_extraction"])
    return default


def cs_overview_query(q: str):
    query = cs_basic_query(q)
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


def cs_terms_query(q: str, field: TermField, aggr: TermAggr):
    resct = 200
    aggr_map = {
        "top": {
            "terms": {
                "field": field.name,
                "size": resct,
                "min_doc_count": 10,
                "shard_min_doc_count": 5,
            }
        },
        "significant": {
            "significant_terms": {
                "field": field.name,
                "size": resct,
                "min_doc_count": 10,
                "shard_min_doc_count": 5,
            }
        },
        "rare": {"rare_terms": {"field": field.name, "exclude": "[0-9].*"}},
    }
    query = cs_basic_query(q)
    query.update(
        {
            "track_total_hits": False,
            "_source": False,
            "aggregations": {
                "sample": {
                    "sampler": {"shard_size": 10 if aggr.name == "rare" else 500},
                    "aggregations": {"topterms": aggr_map[aggr.name]},
                }
            },
        }
    )
    return query


def _validate_sort_order(sort_order: Optional[str]):
    if sort_order and sort_order not in VALID_SORT_ORDERS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sort order (must be on of {', '.join(VALID_SORT_ORDERS)})",
        )
    return sort_order


def _validate_sort_field(sort_field: Optional[str]):
    if sort_field and sort_field not in VALID_SORT_FIELDS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sort field (must be on of {', '.join(VALID_SORT_FIELDS)})",
        )
    return sort_field


def _validate_page_size(page_size: Optional[int]):
    if page_size and page_size < 1:
        raise HTTPException(
            status_code=400, detail="Invalid page size (must be greater than 0)"
        )
    return page_size


def cs_paged_query(
    q: str,
    resume: Union[str, None],
    expanded: bool,
    sort_field=Optional[str],
    sort_order=Optional[str],
    page_size=Optional[int],
) -> Dict:
    query = cs_basic_query(q, expanded)
    final_sort_field = _validate_sort_field(sort_field or "publication_date")
    final_sort_order = _validate_sort_order(sort_order or "desc")
    query.update(
        {
            "size": _validate_page_size(page_size or config["maxpage"]),
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
        query["search_after"] = [decode(resume)]
    return query


def format_match(hit: dict, base: str, collection: str, expanded: bool = False):
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


def format_day_counts(bucket: list):
    return {item["key_as_string"][:10]: item["doc_count"] for item in bucket}


def format_counts(bucket: list):
    return {item["key"]: item["doc_count"] for item in bucket}


def proxy_base_url(req: Request):
    return f'{str(os.getenv("PROXY_BASE", req.base_url)).rstrip("/")}/{req.scope.get("root_path").lstrip("/")}'  # type: ignore [union-attr]


@app.get("/", response_class=HTMLResponse)
@app.head("/", response_class=HTMLResponse)
def api_entrypoint(req: Request):
    """
    Link to the interactive API documentation
    """
    ver = req.app.version.name if isinstance(req.app.version, Enum) else req.app.version
    href = f"{req.scope.get('root_path')}/{ver}/docs"
    return "\n".join(
        ["<ul>", f'<li><a href="{href}">Interactive API Docs ({ver})</a></li>', "</ul>"]
    )


@app.get("/docs", response_class=RedirectResponse)
@app.head("/docs", response_class=RedirectResponse)
def api_entrypoint_docs(req: Request):
    """
    Redirect to recent API documentation
    """
    ver = req.app.version.name if isinstance(req.app.version, Enum) else req.app.version
    return f'{req.scope.get("root_path")}/{ver}/docs'


@app.get("/redoc", response_class=RedirectResponse)
@app.head("/redoc", response_class=RedirectResponse)
def api_entrypoint_redoc(req: Request):
    """
    Redirect to recent API documentation
    """
    ver = req.app.version.name if isinstance(req.app.version, Enum) else req.app.version
    return f'{req.scope.get("root_path")}/{ver}/redoc'


@v1.get("/", response_class=HTMLResponse, tags=["info"])
@v1.head("/", response_class=HTMLResponse, include_in_schema=False)
def version_root(req: Request):
    """
    Links to various collections
    """
    lis = [
        f'<li><a href="{req.scope.get("root_path")}/{col.name}">{col.name}</a></li>'
        for col in Collection
    ]
    return "\n".join(["<ul>"] + lis + ["</ul>"])


@v1.get("/collections", tags=["data"])
@v1.head("/collections", include_in_schema=False)
def get_collections(req: Request):
    return [col.name for col in Collection]


@v1.get("/{collection}", response_class=HTMLResponse, tags=["info"])
@v1.head("/{collection}", response_class=HTMLResponse, include_in_schema=False)
def collection_root(collection: Collection, req: Request):
    """
    Links to various collection API endpoints
    """
    return "\n".join(
        [
            "<ul>",
            f'<li><a href="{req.scope.get("root_path")}/{collection.name}/search">Search API</a></li>',
            f'<li><a href="{req.scope.get("root_path")}/{collection.name}/terms">Related Terms API</a></li>',
            f'<li><a href="{req.scope.get("root_path")}/{collection.name}/article">Article</a></li>',
            "</ul>",
        ]
    )


@v1.get("/{collection}/search", response_class=HTMLResponse, tags=["info"])
@v1.head("/{collection}/search", response_class=HTMLResponse, include_in_schema=False)
def search_root(collection: Collection, req: Request):
    """
    Links to various search API endpoints
    """
    spath = f"{req.scope.get('root_path')}/{collection.name}/search"
    return "\n".join(
        [
            "<ul>",
            f'<li><a href="{spath}/overview">Search Overview</a></li>',
            f'<li><a href="{spath}/result">Search Result</a></li>',
            "</ul>",
        ]
    )


def _search_overview(collection: Collection, q: str, req: Request):
    res = ES.search(index=collection.name, body=cs_overview_query(q))  # type: ignore [call-arg]

    if not res["hits"]["hits"]:
        raise HTTPException(status_code=404, detail="No results found!")
    total = res["hits"]["total"]["value"]
    tldsum = sum(item["doc_count"] for item in res["aggregations"]["tld"]["buckets"])
    base = proxy_base_url(req)
    return {
        "query": q,
        "total": max(total, tldsum),
        "topdomains": format_counts(res["aggregations"]["domain"]["buckets"]),
        "toptlds": format_counts(res["aggregations"]["tld"]["buckets"]),
        "toplangs": format_counts(res["aggregations"]["lang"]["buckets"]),
        "dailycounts": format_day_counts(res["aggregations"]["daily"]["buckets"]),
        "matches": [
            format_match(h, base, collection.name) for h in res["hits"]["hits"]
        ],
    }


@v1.get("/{collection}/search/overview", tags=["data"])
@v1.head("/{collection}/search/overview", include_in_schema=False)
def search_overview_via_query_params(collection: Collection, q: str, req: Request):
    """
    Report overview summary of the search result
    """
    return _search_overview(collection, q, req)


@v1.post("/{collection}/search/overview", tags=["data"])
def search_overview_via_payload(collection: Collection, req: Request, payload: Query):
    """
    Report summary of the search result
    """
    return _search_overview(collection, payload.q, req)


def _search_result(
    collection: Collection,
    q: str,
    req: Request,
    resp: Response,
    resume: Union[str, None] = None,
    expanded: bool = False,
    sort_field: Optional[str] = None,
    sort_order: Optional[str] = None,
    page_size: Optional[int] = None,
):
    query = cs_paged_query(q, resume, expanded, sort_field, sort_order, page_size)
    res = ES.search(index=collection.name, body=query)  # type: ignore [call-arg]
    if not res["hits"]["hits"]:
        raise HTTPException(status_code=404, detail="No results found!")
    base = proxy_base_url(req)
    qurl = f"{base}/{collection.name}/search/result?q={quote_plus(q)}"
    if len(res["hits"]["hits"]) == (page_size or config["maxpage"]):
        resume_key = encode(str(res["hits"]["hits"][-1]["sort"][0]))
        resp.headers["x-resume-token"] = resume_key
        
    return [
        format_match(h, base, collection.name, expanded) for h in res["hits"]["hits"]
    ]


@v1.get("/{collection}/search/result", tags=["data"])
@v1.head("/{collection}/search/result", include_in_schema=False)
def search_result_via_query_params(
    collection: Collection,
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
    Paged response of search result
    """
    return _search_result(
        collection, q, req, resp, resume, expanded, sort_field, sort_order, page_size
    )


@v1.post("/{collection}/search/result", tags=["data"])
def search_result_via_payload(
    collection: Collection, req: Request, resp: Response, payload: PagedQuery
):
    """
    Paged response of search result
    """
    return _search_result(
        collection,
        payload.q,
        req,
        resp,
        payload.resume,
        payload.expanded,
        payload.sort_field,
        payload.sort_order,
        payload.page_size,
    )


if config["debug"]:

    @v1.post("/{collection}/search/esdsl", tags=["debug"])
    def search_esdsl_via_payload(collection: Collection, payload: dict = Body(...)):
        """
        Search using ES Query DSL as JSON payload
        """
        return ES.search(index=collection.name, body=payload)  # type: ignore [call-arg]


def _get_terms(collection: Collection, q: str, field: TermField, aggr: TermAggr):
    res = ES.search(index=collection.name, body=cs_terms_query(q, field, aggr))  # type: ignore [call-arg]
    if (
        not res["hits"]["hits"]
        or not res["aggregations"]["sample"]["topterms"]["buckets"]
    ):
        raise HTTPException(status_code=404, detail="No results found!")
    return format_counts(res["aggregations"]["sample"]["topterms"]["buckets"])


@v1.get("/{collection}/terms", response_class=HTMLResponse, tags=["info"])
@v1.head("/{collection}/terms", response_class=HTMLResponse, include_in_schema=False)
def term_field_root(collection: Collection, req: Request):
    """
    Links to various term fields
    """
    tbase = f"{req.scope.get('root_path')}/{collection.name}/terms"
    lis = [
        f'<li><a href="{tbase}/{field.name}">{field.name}</a></li>'
        for field in TermField
    ]
    return "\n".join(["<ul>"] + lis + ["</ul>"])


@v1.get("/{collection}/terms/{field}", response_class=HTMLResponse, tags=["info"])
@v1.head(
    "/{collection}/terms/{field}", response_class=HTMLResponse, include_in_schema=False
)
def term_aggr_root(collection: Collection, req: Request, field: TermField):
    """
    Links to various term aggregations
    """
    fbase = f"{req.scope.get('root_path')}/{collection.name}/terms/{field.name}"
    lis = [
        f'<li><a href="{fbase}/{aggr.name}">{aggr.name}</a></li>' for aggr in TermAggr
    ]
    return "\n".join(["<ul>"] + lis + ["</ul>"])


@v1.get("/{collection}/terms/{field}/{aggr}", tags=["data"])
@v1.head("/{collection}/terms/{field}/{aggr}", include_in_schema=False)
def get_terms_via_query_params(
    collection: Collection, q: str, field: TermField, aggr: TermAggr
):
    """
    Top terms with frequencies in matching articles
    """
    return _get_terms(collection, q, field, aggr)


@v1.post("/{collection}/terms/{field}/{aggr}", tags=["data"])
def get_terms_via_payload(
    collection: Collection,
    payload: Query,
    field: TermField,
    aggr: TermAggr,
):
    """
    Top terms with frequencies in matching articles
    """
    return _get_terms(collection, payload.q, field, aggr)


@v1.get("/{collection}/article/{id}", tags=["data"])
@v1.head("/{collection}/article/{id}", include_in_schema=False)
def get_article(
    collection: Collection, id: str, req: Request
):  # pylint: disable=redefined-builtin
    """
    Fetch an individual article record by ID.
    """
    source = {"includes": cs_basic_query(id, expanded=True)["_source"]}
    query = {"match": {"_id": id}}

    try:
        res = ES.search(index=collection.name, source=source, query=query)
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
    base = proxy_base_url(req)
    return format_match(hit, base, collection.name, True)  # type: ignore[arg-type]


app.mount(f"/{ApiVersion.v1.name}", v1)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api:app", host="0.0.0.0", reload=True, root_path=os.getenv("ROOT_PATH", "")
    )
