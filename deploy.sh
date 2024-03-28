#!/bin/bash
# deploy.sh - Deployment script for News Search API and UI

# Environment variables

IMAGE_TAG="staging"  # Change this based on your use case
INDEXES="mc_search"
ESHOSTS="http://ramos.angwin:9200,http://woodward.angwin:9200,http://bradley.angwin:9200"
ESOPTS="{'timeout': 60, 'max_retries': 3}" # 'timeout' parameter is deprecated
ELASTICSEARCH_INDEX_NAME_PREFIX="mc_search-*"
TERMFIELDS="article_title,text_content"
TERMAGGRS="top,significant,rare"

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    echo "This script must be run as root."
    exit 1
fi

help()
{
    echo "Usage: ./deploy.sh [options]"
    echo "Options:"
    echo "-h show help message"
    echo "-t specify the image tag (staging, release, v1.3.1 e.t.c)"
}

log()
{
    echo "$1"
}
# Parse command-line options
while getopts :h:t optname; do
    log "Option $optname set with value ${OPTARG}"
    case $optname in
        t)
            IMAGE_TAG=${OPTARG}
            ;;
        h)
            help
            exit 2
            ;;
        *)
            echo "Invalid option: $1"
            help
            exit 2
            ;;
    esac
done

# Create a directory for private configuration
PRIVATE_CONF_DIR="/news_search_api"
rm -rf "$PRIVATE_CONF_DIR"
mkdir -p "$PRIVATE_CONF_DIR"
chmod go-rwx "$PRIVATE_CONF_DIR"

# Fetch the docker-compose.yml file from GitHub
CONFIG_REPO_PREFIX="https://github.com/mediacloud"  # Replace with your actual GitHub URL
CONFIG_REPO_NAME="news-search-api"  # Change to your actual repo name
DOCKER_COMPOSE_FILE="docker-compose.yml"  # Name of the Docker Compose file
echo "Fetching $DOCKER_COMPOSE_FILE from $CONFIG_REPO_NAME repo..."
if ! curl -sSfL "$CONFIG_REPO_PREFIX/$CONFIG_REPO_NAME/raw/main/$DOCKER_COMPOSE_FILE" -o "$PRIVATE_CONF_DIR/$DOCKER_COMPOSE_FILE"; then
    echo "FATAL: Could not fetch $DOCKER_COMPOSE_FILE from config repo"
    exit 1ls

fi

# Deploy services using Docker Compose
echo "Deploying services with image tag: $IMAGE_TAG"
docker-compose -f "$PRIVATE_CONF_DIR/$DOCKER_COMPOSE_FILE" up -d

# Additional steps (e.g., database migrations, cache clearing, etc.)
# ...

echo "Deployment completed successfully!"
