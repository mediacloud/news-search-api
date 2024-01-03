import datetime as dt
import os
from test import ELASTICSEARCH_URL, INDEX_NAME, NUMBER_OF_TEST_STORIES
from unittest import TestCase

from fastapi.testclient import TestClient

from api import ApiVersion, app

# make sure to set these env vars before importing the app so it runs against a test ES you've set up with
# the `create_fixtures.py` script
os.environ["INDEXES"] = INDEX_NAME
os.environ["ESHOSTS"] = ELASTICSEARCH_URL
os.environ["ELASTICSEARCH_INDEX_NAME_PREFIX"] = "mediacloud"


TIMEOUT = 30


class ApiTest(TestCase):
    def setUp(self):
        self._client = TestClient(app)

    def test_api_version_response_header(self):
        response = self._client.get("/", timeout=TIMEOUT)
        assert response.status_code == 200
        assert "x-api-version" in response.headers
        assert response.headers["x-api-version"] == ApiVersion.v1

    def test_overview_all(self):
        # make sure all stories come back and domain is right
        response = self._client.post(
            f"/v1/{INDEX_NAME}/search/overview", json={"q": "*"}, timeout=TIMEOUT
        )
        assert response.status_code == 200
        results = response.json()
        assert "total" in results
        assert results["total"] > 1000
        assert "matches" in results
        for story in results["matches"]:
            assert "canonical_domain" in story
            assert story["canonical_domain"] == "example.com"

    def test_overview_no_results(self):
        response = self._client.post(
            f"/v1/{INDEX_NAME}/search/overview", json={"q": "asdfdf"}, timeout=TIMEOUT
        )
        assert response.status_code == 404

    def test_overview_by_content(self):
        response = self._client.post(
            f"/v1/{INDEX_NAME}/search/overview", json={"q": "article"}, timeout=TIMEOUT
        )
        assert response.status_code == 200
        results = response.json()
        assert "total" in results
        assert results["total"] > 1000
        response = self._client.post(
            f"/v1/{INDEX_NAME}/search/overview", json={"q": "1"}, timeout=TIMEOUT
        )
        assert response.status_code == 200
        results = response.json()
        assert "total" in results
        assert results["total"] < 1000

    def test_overview_by_pub_date(self):
        response = self._client.post(
            f"/v1/{INDEX_NAME}/search/overview",
            json={"q": "* AND publication_date:[2023-11-01 TO 2023-12-10]"},
            timeout=TIMEOUT,
        )
        assert response.status_code == 200
        results = response.json()
        assert "total" in results
        assert results["total"] > 300
        assert results["total"] < 1200

    def test_paging_token(self):
        response = self._client.post(
            f"/v1/{INDEX_NAME}/search/result", json={"q": "*"}, timeout=TIMEOUT
        )
        assert response.status_code == 200
        results = response.json()
        assert len(results) == 1000
        next_page_token = response.headers.get("x-resume-token")
        assert next_page_token is not None
        # now try with cusotm page size
        response = self._client.post(
            f"/v1/{INDEX_NAME}/search/result",
            json={"q": "*", "page_size": 23},
            timeout=TIMEOUT,
        )
        assert response.status_code == 200
        results = response.json()
        assert len(results) == 23
        next_page_token = response.headers.get("x-resume-token")
        assert next_page_token is not None

    def _get_all_stories(self, page_size: int, query: str = "*"):
        more_stories = True
        next_page_token = None
        page_count = 0
        stories = []
        while more_stories:
            response = self._client.post(
                f"/v1/{INDEX_NAME}/search/result",
                json={"q": query, "page_size": page_size, "resume": next_page_token},
                timeout=TIMEOUT,
            )
            assert response.status_code == 200
            results = response.json()
            assert len(results) > 0
            next_page_token = response.headers.get("x-resume-token")
            stories += results
            more_stories = next_page_token is not None
            page_count += 1
        return page_count, stories

    def test_paging_all(self):
        # get total count
        response = self._client.post(
            f"/v1/{INDEX_NAME}/search/overview", json={"q": "*"}, timeout=TIMEOUT
        )
        assert response.status_code == 200
        results = response.json()
        assert "total" in results
        assert results["total"] == NUMBER_OF_TEST_STORIES
        total_expected_stories = results["total"]
        # now page through to make sure it matches
        page_size = 1000
        page_count, stories = self._get_all_stories(page_size)
        assert len(stories) >= (
            total_expected_stories * 0.9
        )  # weird that not all results returned
        assert page_count == (1 + int(total_expected_stories / 1000))
        # now try it with small page size
        page_size = 900
        page_count, stories = self._get_all_stories(page_size)
        assert len(stories) >= (
            total_expected_stories * 0.9
        )  # weird that not all results returned
        assert page_count == (1 + int(total_expected_stories / 1000))

    def test_text_content_expanded(self):
        response = self._client.post(
            f"/v1/{INDEX_NAME}/search/result",
            json={"q": "*", "expanded": 1},
            timeout=TIMEOUT,
        )
        assert response.status_code == 200
        results = response.json()
        assert len(results) == 1000
        for story in results:
            assert "text_content" in story
            assert len(story["text_content"]) > 0

    def test_story_sort_order(self):
        # desc
        response = self._client.post(
            f"/v1/{INDEX_NAME}/search/result", json={"q": "*"}, timeout=TIMEOUT
        )
        assert response.status_code == 200
        results = response.json()
        future = dt.date(2050, 1, 1)
        last_pub_date = future
        for story in results:
            assert "text_content" not in story
            assert "publication_date" in story
            story_pub_date = dt.date.fromisoformat(story["publication_date"])
            assert story_pub_date <= last_pub_date
            last_pub_date = story_pub_date
        # asc
        response = self._client.post(
            f"/v1/{INDEX_NAME}/search/result",
            json={"q": "*", "sort_order": "asc"},
            timeout=TIMEOUT,
        )
        results = response.json()
        a_long_time_ago = dt.date(2000, 1, 1)
        last_pub_date = a_long_time_ago
        for story in results:
            assert "publication_date" in story
            story_pub_date = dt.date.fromisoformat(story["publication_date"])
            assert story_pub_date >= last_pub_date
            last_pub_date = story_pub_date
        # invalid
        response = self._client.post(
            f"/v1/{INDEX_NAME}/search/result",
            json={"q": "*", "sort_order": "foo"},
            timeout=TIMEOUT,
        )
        assert response.status_code == 400

    def test_story_sort_field(self):
        # desc
        response = self._client.post(
            f"/v1/{INDEX_NAME}/search/result",
            json={"q": "*", "sort_field": "publication_date"},
            timeout=TIMEOUT,
        )
        assert response.status_code == 200
        results = response.json()
        future = dt.date(2050, 1, 1)
        last_date = future
        for story in results:
            assert "text_content" not in story
            assert "publication_date" in story
            story_date = dt.date.fromisoformat(story["publication_date"])
            assert story_date <= last_date
            last_date = story_date
        # indexed date
        response = self._client.post(
            f"/v1/{INDEX_NAME}/search/result",
            json={"q": "*", "sort_field": "indexed_date"},
            timeout=TIMEOUT,
        )
        assert response.status_code == 200
        results = response.json()
        future = dt.datetime(2050, 1, 1)
        last_date = future
        for story in results:
            assert "indexed_date" in story
            story_date = dt.datetime.fromisoformat(story["indexed_date"])
            assert story_date <= last_date
            last_date = story_date
        # invalid
        response = self._client.post(
            f"/v1/{INDEX_NAME}/search/result",
            json={"q": "*", "sort_field": "imagined_date"},
            timeout=TIMEOUT,
        )
        assert response.status_code == 400

    def test_page_size(self):
        # test valid number
        response = self._client.post(
            f"/v1/{INDEX_NAME}/search/result",
            json={"q": "*", "page_size": 103},
            timeout=TIMEOUT,
        )
        assert response.status_code == 200
        results = response.json()
        assert len(results) == 103
        # test invalid value
        response = self._client.post(
            f"/v1/{INDEX_NAME}/search/result",
            json={"q": "*", "page_size": "💩"},
            timeout=TIMEOUT,
        )
        assert response.status_code == 422
        response = self._client.post(
            f"/v1/{INDEX_NAME}/search/result",
            json={"q": "*", "page_size": -10},
            timeout=TIMEOUT,
        )
        assert response.status_code == 400

    def test_date_formats(self):
        response = self._client.post(
            f"/v1/{INDEX_NAME}/search/result", json={"q": "*"}, timeout=TIMEOUT
        )
        assert response.status_code == 200
        results = response.json()
        for story in results:
            # publication date is just date
            assert "publication_date" in story
            assert len(story["publication_date"]) == 10
            # indexed date is datetime
            assert "indexed_date" in story
            assert len(story["indexed_date"]) == 19
            assert "T" in story["indexed_date"]

    def test_filter_by_indexed_date(self):
        response = self._client.post(
            f"/v1/{INDEX_NAME}/search/result",
            json={"q": "*", "sort_field": "indexed_date", "page_size": 100},
            timeout=TIMEOUT,
        )
        assert response.status_code == 200
        results = response.json()
        newest_indexed_date = results[0]["indexed_date"]
        oldest_indexed_date = results[-1]["indexed_date"]
        assert oldest_indexed_date < newest_indexed_date
        # test filter
        response = self._client.post(
            f"/v1/{INDEX_NAME}/search/result",
            json={
                "q": f"* AND indexed_date:[2010-01-01T00:00:00 TO {oldest_indexed_date}]",
                "sort_field": "indexed_date",
                "page_size": 100,
            },
            timeout=TIMEOUT,
        )
        assert response.status_code == 200
        results = response.json()
        for story in results:
            assert story["indexed_date"] <= oldest_indexed_date

    def test_sort_duplicate_pub_date(self):
        small_page_size = 20
        query = "* AND publication_date:[2023-12-01 TO 2023-12-05]"
        # check enough stories
        response = self._client.post(
            f"/v1/{INDEX_NAME}/search/overview", json={"q": query}, timeout=TIMEOUT
        )
        assert response.status_code == 200
        results = response.json()
        assert "total" in results
        assert results["total"] > small_page_size * 2
        # now pull the same results twice to compare
        _, stories1 = self._get_all_stories(small_page_size, query)
        url_list_take1 = [s["normalized_url"] for s in stories1]
        _, stories2 = self._get_all_stories(small_page_size, query)
        url_list_take2 = [s["normalized_url"] for s in stories2]
        # make sure order is same across the two identical queries
        assert len(url_list_take1) == len(url_list_take2)
        for idx in range(0, len(url_list_take2)):
            assert url_list_take1[idx] == url_list_take2[idx]
