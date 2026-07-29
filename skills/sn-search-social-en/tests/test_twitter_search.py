"""Twitter search provider tests."""

import importlib
import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

twitter_search = importlib.import_module("twitter_search")


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.raise_calls = 0

    def raise_for_status(self) -> None:
        self.raise_calls += 1

    def json(self) -> dict:
        return self.payload


class FakeClient:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.calls: list[tuple[str, dict]] = []

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback) -> None:
        return None

    def get(self, url: str, params: dict) -> FakeResponse:
        self.calls.append((url, params))
        return self.response


class ClientFactory:
    def __init__(self, client: FakeClient) -> None:
        self.client = client
        self.calls: list[dict] = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return self.client


class TwitterSearchProviderTests(unittest.TestCase):
    def test_default_provider_keeps_tikhub_contract(self) -> None:
        response = FakeResponse(
            {
                "data": {
                    "data": [
                        {
                            "content": {
                                "id_str": "321",
                                "full_text": "Existing provider result",
                                "user": {"screen_name": "legacy", "name": "Legacy"},
                            }
                        }
                    ]
                }
            }
        )
        client = FakeClient(response)
        factory = ClientFactory(client)

        items = twitter_search.search(
            "AI agents",
            5,
            token="tikhub_test_token",
            client_factory=factory,
        )

        self.assertEqual(
            factory.calls,
            [
                {
                    "timeout": 30,
                    "headers": {
                        "Authorization": "Bearer tikhub_test_token",
                        "Accept": "application/json",
                    },
                }
            ],
        )
        self.assertEqual(
            client.calls,
            [
                (
                    "https://api.tikhub.io/api/v1/twitter/web/fetch_search_timeline",
                    {"keyword": "AI agents", "search_type": "Latest"},
                )
            ],
        )
        self.assertEqual(items[0]["url"], "https://x.com/legacy/status/321")
        self.assertEqual(items[0]["source"], "tikhub")

    def test_requires_api_key(self) -> None:
        with self.assertRaisesRegex(ValueError, "XQUIK_API_KEY"):
            twitter_search.search("AI agents", 10, provider="xquik")

    def test_rejects_nonpositive_limit(self) -> None:
        with self.assertRaisesRegex(ValueError, "limit"):
            twitter_search.search_xquik("AI agents", 0, "xq_test_key")

    def test_calls_published_search_contract_and_maps_results(self) -> None:
        response = FakeResponse(
            {
                "tweets": [
                    {
                        "id": "123",
                        "text": "A useful result",
                        "createdAt": "2026-08-23T10:00:00Z",
                        "likeCount": 9,
                        "retweetCount": 4,
                        "replyCount": 2,
                        "viewCount": 120,
                        "author": {"username": "example", "name": "Example"},
                    }
                ],
                "has_next_page": False,
                "next_cursor": "",
            }
        )
        client = FakeClient(response)
        factory = ClientFactory(client)

        items = twitter_search.search(
            "AI agents",
            10,
            provider="xquik",
            api_key="xq_test_key",
            client_factory=factory,
        )

        self.assertEqual(
            factory.calls,
            [
                {
                    "timeout": 30,
                    "headers": {
                        "x-api-key": "xq_test_key",
                        "Accept": "application/json",
                    },
                }
            ],
        )
        self.assertEqual(
            client.calls,
            [
                (
                    "https://xquik.com/api/v1/x/tweets/search",
                    {"q": "AI agents", "limit": 10, "queryType": "Latest"},
                )
            ],
        )
        self.assertEqual(response.raise_calls, 1)
        self.assertEqual(
            items,
            [
                {
                    "title": "@example",
                    "url": "https://x.com/example/status/123",
                    "snippet": "A useful result",
                    "author": "Example",
                    "screen_name": "example",
                    "tweet_id": "123",
                    "favorite_count": 9,
                    "retweet_count": 4,
                    "reply_count": 2,
                    "view_count": 120,
                    "created_at": "2026-08-23T10:00:00Z",
                    "source": "xquik",
                }
            ],
        )

    def test_preserves_api_url_and_caps_request_limit(self) -> None:
        response = FakeResponse(
            {
                "tweets": [
                    {"id": "456", "text": "Result", "url": "https://x.com/i/status/456"}
                ],
            }
        )
        client = FakeClient(response)

        items = twitter_search.search_xquik(
            "launch",
            20_000,
            "xq_test_key",
            ClientFactory(client),
        )

        self.assertEqual(client.calls[0][1]["limit"], 10_000)
        self.assertEqual(items[0]["url"], "https://x.com/i/status/456")

    def test_rejects_invalid_tweets_shape(self) -> None:
        client = FakeClient(FakeResponse({"tweets": {"id": "123"}}))

        with self.assertRaisesRegex(ValueError, "tweets"):
            twitter_search.search_xquik(
                "AI agents",
                10,
                "xq_test_key",
                ClientFactory(client),
            )

    def test_rejects_unknown_provider(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown"):
            twitter_search.search("AI agents", 10, provider="unknown")


if __name__ == "__main__":
    unittest.main()
