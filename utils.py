import json
import os

from enum import Enum
from elasticsearch import Elasticsearch

import yaml


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
    return Enum(name, [f"{kv}:{kv}".split(":")[:2] for kv in koptv])

def assert_elasticsearch_connection(es: Elasticsearch) -> bool:
    try:
        info = es.info()
        if info["version"]["number"]:
            print("Connected to Elasticsearch version:", info["version"]["number"])
            return True
    except Exception as e:
        print("Failed to connect to Elasticsearch:", str(e))
    return False