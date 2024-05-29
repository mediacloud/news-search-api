#!/bin/sh
# deploy.sh - Deployment script for News Search API and UI

# Environment variables
APP_NAME="news-search-api"
API_REPLICAS=2
API_PORT_BASE=8000
UI_PORT_BASE=8501
IMAGE_TAG="latest"

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
    echo "-h, --help             Show this help message"
    echo "-a, --use-latest-image Allow deployment without requiring a checked-out tag, uses 'latest' as image tag (only for dev)"
    echo "-d, --deployment-type  Specify the deployment type (dev, staging or prod)"
    echo "-R, --replicas         Set the number of API replicas (default: $API_REPLICAS)"
}

log()
{
    echo "$1"
}

zzz() {
    echo $1 | tr 'A-Za-z' 'N-ZA-Mn-za-m'
}

if [ $# -eq 0 ]; then
    help
    exit 1
fi

USE_LATEST_IMAGE=false
# Parse command-line options
while [ "$#" -gt 0 ]; do
    case "$1" in
        -h|--help)
            help
            exit 0
            ;;
        -d|--deployment-type)
            if [ -n "$2" ]; then
                DEPLOYMENT_TYPE="$2"
                shift 2
            else
                echo "Error: --deployment-type requires an argument." >&2
                help
                exit 1
            fi
            ;;
        -a|--use-latest-image)
            USE_LATEST_IMAGE=true
            shift
            ;;
        -R|--replicas)
            API_REPLICAS="$2"
            shift 2
            ;;
        -*|--*=) # unsupported flags
            echo "Error: Unsupported flag $1" >&2
            help
            exit 1
            ;;
    esac
done

# Check if running as root
if [ $(whoami) != "root" ]; then
    echo "This script must be run as root."
    exit 1
fi

echo "Running as root"

if $USE_LATEST_IMAGE && [ "$DEPLOYMENT_TYPE" != "dev" ]; then
    echo "Error: The -a option is only allowed for 'dev' deployment type."
    exit 1
fi

case "$DEPLOYMENT_TYPE" in
    dev)
        API_PORT=$(expr $API_PORT_BASE + 100)
        UI_PORT=$(expr $UI_PORT_BASE + 100)
        STACK_NAME="$LOGIN_USER-$APP_NAME"
        ;;
    staging)
        API_PORT=$(expr $API_PORT_BASE + 200)
        UI_PORT=$(expr $UI_PORT_BASE + 200)
        STACK_NAME="staging-$APP_NAME"
        ENV_FILE="staging"
        ;;
    prod)
        API_PORT=$API_PORT_BASE
        UI_PORT=$UI_PORT_BASE
        STACK_NAME="$APP_NAME"
        ENV_FILE="prod"
        ;;
    *)
        echo "Error: Invalid deployment type. Specify either 'dev', 'staging' or 'prod'."
        exit 1
        ;;
esac

# Check if running on a checked-out tag (staging/prod)
if ! $USE_LATEST_IMAGE; then
    if git describe --exact-match --tags HEAD >/dev/null 2>&1; then
        echo "Running on a checked-out tag: $(git describe --tags --abbrev=0)"
        IMAGE_TAG=$(git describe --tags --abbrev=0)
    else
        echo "This script must be run on a checked-out tag."
        exit 1
    fi
fi

case "$DEPLOYMENT_TYPE" in
staging|prod)
    PRIVATE_CONF_DIR="news-search-private-conf"
    run_as_login_user mkdir -p $PRIVATE_CONF_DIR
    chmod go-rwx $PRIVATE_CONF_DIR

    cd $PRIVATE_CONF_DIR
    CONFIG_REPO_PREFIX=$(zzz tvg@tvguho.pbz:zrqvnpybhq)
    CONFIG_REPO_NAME=$(zzz arjf-frnepu-ncv-pbasvt)
    PRIVATE_CONF_REPO=$(pwd)/$CONFIG_REPO_NAME

    echo cloning $CONFIG_REPO_NAME repo 1>&2
    if ! run_as_login_user "git clone $CONFIG_REPO_PREFIX/$CONFIG_REPO_NAME.git" >/dev/null 2>&1; then
        echo "FATAL: could not clone config repo" 1>&2
        exit 1
    fi
    PRIVATE_CONF_FILE=$PRIVATE_CONF_REPO/$APP_NAME.$ENV_FILE.sh
    cd ..

    if [ ! -f $PRIVATE_CONF_FILE ]; then
        echo "FATAL: could not access $PRIVATE_CONF_FILE" 1>&2
        exit 1
    fi

    . $PRIVATE_CONF_FILE
    rm -rf $PRIVATE_CONF_DIR
    ;;
esac

DOCKER_COMPOSE_FILE="docker-compose.yml"

export ESOPTS='{"timeout": 60, "max_retries": 3}' # 'timeout' parameter is deprecated
export TERMFIELDS="article_title,text_content"
export TERMAGGRS="top,significant,rare"
export ELASTICSEARCH_INDEX_NAME_PREFIX
export API_PORT
export API_REPLICAS
export UI_PORT
export ESHOSTS
export SENTRY_DSN
export SENTRY_ENVIRONMENT
export IMAGE_TAG
export NEWS_SEARCH_UI_TITLE

if $USE_LATEST_IMAGE; then
    echo "Building Docker images..."
    docker compose build
    STATUS=$?
    if [ $STATUS != 0 ]; then
        echo "docker compose build failed: $STATUS" >&2
        exit 1
    fi
fi

# Validation & Interpolation of docker compose file
rm -f docker-compose.yml.dump

docker stack config -c "$DOCKER_COMPOSE_FILE" > docker-compose.yml.dump
STATUS=$?
if [ $STATUS != 0 ]; then
    echo "docker stack config failed: $STATUS" >&2
    exit 1
fi

echo "Deploying services with stack name: $STACK_NAME and tag: $IMAGE_TAG"

docker stack deploy -c docker-compose.yml.dump "$STACK_NAME"
STATUS=$?
if [ $STATUS != 0 ]; then
    echo "docker stack deploy failed: $STATUS" >&2
    exit 1
fi

echo "Deployment completed successfully!"
