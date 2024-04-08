#!/bin/bash
# deploy.sh - Deployment script for News Search API and UI

# Environment variables

IMAGE_TAG="latest"  # Change this based on deployment (staging, production, v1.0) - Reference tags in new-search-api Repo
INDEXES="mc_search"
ESHOSTS="http://ramos.angwin:9200,http://woodward.angwin:9200,http://bradley.angwin:9200"
ESOPTS="{'timeout': 60, 'max_retries': 3}" # 'timeout' parameter is deprecated
ELASTICSEARCH_INDEX_NAME_PREFIX="mc_search-*"
TERMFIELDS="article_title,text_content"
TERMAGGRS="top,significant,rare"
APP_NAME="news-search-api"

# Check if running as root
is_root() {
    if [ $(whoami) != "root" ]; then
        echo "This script must be run as root."
        exit 1
    fi
}

is_root
echo "Running as root"

LOGIN_USER=$(who am i | awk '{ print $1 }')
if [ "x$LOGIN_USER" = x ]; then
    # XXX fall back to whoami (look by uid)
    echo could not find login user 1>&2
    exit 1
fi

run_as_login_user() {
	su $LOGIN_USER -c "$*"
}

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

zzz() {
    echo $1 | tr 'A-Za-z' 'N-ZA-Mn-za-m'
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
        \?)
            echo "Invalid option: $1"
            help
            exit 2
            ;;
    esac
done

# Create a directory for private configuration
PRIVATE_CONF_DIR="news_search_api_config"
rm -rf "$PRIVATE_CONF_DIR"
mkdir -p "$PRIVATE_CONF_DIR"
chmod go-rwx "$PRIVATE_CONF_DIR"
CONFIG_REPO_PREFIX=$(zzz tvg@tvguho.pbz:zrqvnpybhq)
CONFIG_REPO_NAME=$(zzz arjf-frnepu-ncv-pbasvt)
echo cloning $CONFIG_REPO_NAME repo 1>&2
if ! run_as_login_user "git clone $CONFIG_REPO_PREFIX/$CONFIG_REPO_NAME.git" >/dev/null 2>&1; then
echo "FATAL: could not clone config repo" 1>&2
exit 1
fi
PRIVATE_CONF_REPO=$(pwd)/$CONFIG_REPO_NAME
PRIVATE_CONF_FILE=$PRIVATE_CONF_REPO/$APP_NAME.sh
cd ..

if [ ! -f $PRIVATE_CONF_FILE ]; then
    echo "FATAL: could not access $PRIVATE_CONF_FILE" 1>&2
    exit 1
fi
#source private conf to load SENTRY_DSN
. $PRIVATE_CONF_FILE


INSTALL_DIR="news_search_api"
mkdir -p "$INSTALL_DIR"

GH_REPO_PREFIX="https://github.com/mediacloud"
GH_REPO_NAME="news-search-api"
DOCKER_COMPOSE_FILE="docker-compose.yml"
echo "Fetching $DOCKER_COMPOSE_FILE from $GH_REPO_NAME repo..."
if ! curl -sSfL "$GH_REPO_PREFIX/$GH_REPO_NAME/raw/$IMAGE_TAG/$DOCKER_COMPOSE_FILE" -o "$INSTALL_DIR/$DOCKER_COMPOSE_FILE"; then
    echo "FATAL: Could not fetch $DOCKER_COMPOSE_FILE from config repo"
    exit 1

fi

# Deploy services using Docker Compose
echo "Deploying services with image tag: $IMAGE_TAG"
docker-compose -f "$INSTALL_DIR/$DOCKER_COMPOSE_FILE" up -d

# Additional steps (e.g., database migrations, cache clearing, etc.)
# ...

echo "Deployment completed successfully!"
