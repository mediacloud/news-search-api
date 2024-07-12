#!/usr/bin/env python3
import base64
import os
import time
from enum import Enum
from typing import Dict, List, Optional, TypeAlias, Union
from urllib.parse import quote_plus

import mcmetadata.urls as urls
import sentry_sdk
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import TransportError
from fastapi import Body, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, computed_field
from pydantic_settings import BaseSettings
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from client import EsClientWrapper
from utils import assert_elasticsearch_connection, logger


class Config(BaseSettings):
    eshosts: str = "http://localhost:9200"
    termfields: str = "article_title,text_content"
    termaggrs: str = "top"
    esopts: Dict = {}
    title: str = "Interactive API"
    description: str = "A wrapper API for ES indexes."
    debug: bool = False
    sentry_dsn: str = ""
    tracing_sample_rate: float = 1.0
    profiles_sample_rate: float = 1.0
    root_path: str = ""
    deployment_type: str = "dev"

    @computed_field()
    def eshosts_list(self) -> List[str]:
        return self.eshosts.split(",")

    @computed_field()
    def termfields_list(self) -> List[str]:
        return self.termfields.split(",")

    @computed_field()
    def termaggrs_list(self) -> List[str]:
        return self.termaggrs.split(",")


config = Config()
logger.info(f"Loaded config: {config}")

# Initialize our sentry integration
if config.sentry_dsn:
    sentry_sdk.init(
        dsn=config.sentry_dsn,
        environment=config.deployment_type,
        traces_sample_rate=config.tracing_sample_rate,
        profiles_sample_rate=config.profiles_sample_rate,
        integrations=[
            StarletteIntegration(transaction_style="url"),
            FastApiIntegration(transaction_style="url"),
        ],
    )

app = FastAPI()


class ApiVersion(str, Enum):
    v1 = "1.3.7"


ES = EsClientWrapper(config.eshosts_list, **config.esopts)

Collection = Enum("Collection", [f"{kv}:{kv}".split(":")[:2] for kv in ES.get_allowed_collections()])  # type: ignore [misc]
TermField = Enum("TermField", [f"{kv}:{kv}".split(":")[:2] for kv in config.termfields_list])  # type: ignore [misc]
TermAggr = Enum("TermAggr", [f"{kv}:{kv}".split(":")[:2] for kv in config.termaggrs_list])  # type: ignore [misc]


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
if config.debug:
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
    title=config.title + " Docs",
    description=config.description,
    version=ApiVersion.v1.value,
    openapi_tags=tags,
)


class Query(BaseModel):
    q: str


class PagedQuery(Query):
    resume: Union[str, None] = None
    expanded: bool = False
    sort_field: Optional[str] = None
    sort_order: Optional[str] = None
    page_size: Optional[int] = None


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


@v1.get("/{collection}/search/overview", tags=["data"])
@v1.head("/{collection}/search/overview", include_in_schema=False)
def search_overview_via_query_params(collection: Collection, q: str, req: Request):
    """
    Report overview summary of the search result
    """
    return ES.search_overview(collection.name, q)


@v1.post("/{collection}/search/overview", tags=["data"])
def search_overview_via_payload(collection: Collection, req: Request, payload: Query):
    """
    Report summary of the search result
    """
    return ES.search_overview(collection.name, payload.q)


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

    result, resume_key = ES.search_result(
        collection.name,
        q,
        resume,
        expanded,
        sort_field,
        sort_order,
        page_size,
    )
    if resume_key:
        resp.headers["x-resume-token"] = resume_key
    return result


@v1.post("/{collection}/search/result", tags=["data"])
def search_result_via_payload(
    collection: Collection, req: Request, resp: Response, payload: PagedQuery
):
    """
    Paged response of search result
    """
    result, resume_key = ES.search_result(
        collection.name,
        payload.q,
        payload.resume,
        payload.expanded,
        payload.sort_field,
        payload.sort_order,
        payload.page_size,
    )
    if resume_key:
        resp.headers["x-resume-token"] = resume_key
    return result


if config.debug:

    @v1.post("/{collection}/search/esdsl", tags=["debug"])
    def search_esdsl_via_payload(collection: Collection, payload: dict = Body(...)):
        """
        Search using ES Query DSL as JSON payload
        """
        return ES.ES.search(index=collection.name, body=payload)  # type: ignore [call-arg]


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
    return ES.get_terms(collection.name, q, field.name, aggr.name)


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
    return ES.get_terms(collection.name, payload.q, field.name, aggr.name)


@v1.get("/{collection}/article/{id}", tags=["data"])
@v1.head("/{collection}/article/{id}", include_in_schema=False)
def get_article(
    collection: Collection, id: str, req: Request
):  # pylint: disable=redefined-builtin
    """
    Fetch an individual article record by ID.
    """

    return ES.get_article(collection.name, id)


app.mount(f"/{ApiVersion.v1.name}", v1)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="0.0.0.0", reload=True, root_path=config.root_path)
