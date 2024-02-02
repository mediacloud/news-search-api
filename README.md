Web Archive Search Index API and UI
===================================

An API wrapper to the Elasticsearch index of web archival collections and a web UI to explore those
indexes. A part of the [story-indexer stack](https://github.com/mediacloud/story-indexer). Maintained as a
separate repository for future legibility.  This exposes an FastAPI-based API server and a Streamlit-based
search UI (for quick testing). Both are managed as internal services as part of the Media Cloud Online News
Archive.

## ES Index

The API service expects the following ES index schema, where `title` and `snippet` fields must have
the `fielddata` enabled (if they have the type `text`). This is currently defined in the story-indexer
stack, but is replicated here for convenience (but might be out of date).
<details>

```json
{
    "properties": {
        "original_url": {"type": "keyword"},
        "url": {"type": "keyword"},
        "normalized_url": {"type": "keyword"},
        "canonical_domain": {"type": "keyword"},
        "publication_date": {"type": "date", "ignore_malformed": true},
        "language": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
        "full_language": {"type": "keyword"},
        "text_extraction": {"type": "keyword"},
        "article_title": {
            "type": "text",
            "fields": {"keyword": {"type": "keyword"}}
        },
        "normalized_article_title": {
            "type": "text",
            "fields": {"keyword": {"type": "keyword"}}
        },
        "text_content": {"type": "text", "fields": {"keyword": {"type": "keyword"}}}
    }
}
```

</details>

## Run Services

Configurations is set using environment variables by setting corresponding upper-case names of the
config parameters. Environment variables that accept a list (e.g., `ESHOSTS` and `INDEXES`) can have
commas or spaces as separators. Configuration via a config file in the syntax of the provided
`config.yml.sample` can be used for testing.

Then run the API and UI services using Docker Compose:

```
$ docker compose up
```

Access an interactive API documentation and a collection index explorer in a web browser:

- API: http://localhost:8000/docs
- UI: http://localhost:8001/

## Building and Releasing

Deployments are now configured to be automatically built and released via GitHub Actions.

1. Change the version number stored in `ApiVersion.v1` in `api.py`
2. Add a small note to the version history below indicating what changed
3. Commit and tag the repo with the same number
4. Push the tag to GitHub to trigger the build and release
5. Once it is done, the labeled image will be ready at https://hub.docker.com/r/mcsystems/news-search-api

## Version History

* __v1.2.0__ - Change related to ID update in backend ES, including refurbishing the article endpoint and tests 
* __v1.1.0__ - Change to return `None` when data is missing (including publication date), update dependencies
* __v1.0.0__ - First official release
