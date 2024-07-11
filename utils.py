import logging

from elasticsearch import Elasticsearch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
