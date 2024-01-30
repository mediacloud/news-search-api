import json
import logging
import os
from enum import Enum
from typing import TypeAlias

import yaml
from elasticsearch import Elasticsearch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_config():
    conf = os.getenv("CONFIG", "config.yml")
    try:
        return yaml.safe_load(open(conf, encoding="UTF-8"))
    except OSError:
        return {}


def env_to_list(name: str):
    return " ".join(os.getenv(name, "").split(",")).split()


def env_to_dict(name: str):
    return json.loads(os.getenv(name, "{}"))


def list_to_enum(name: str, koptv: list):
    # Just use StrEnum? py3.11 feature- let's attempt.
    return Enum(name, [f"{kv}:{kv}".split(":")[:2] for kv in koptv])


def assert_elasticsearch_connection(es: Elasticsearch) -> bool:
    try:
        info = es.info()
        if info["version"]["number"]:
            logger.info(
                "Connected to Elasticsearch version: %s", info["version"]["number"]
            )
            return True
    except Exception as e:
        logger.error("Failed to connect to Elasticsearch: %s", str(e))
    return False
