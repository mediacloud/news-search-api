#!/bin/bash
# deploy.sh - Deployment script for News Search API and UI

# Environment variables

INDEXES="mc_search"
ESHOSTS="" #source from private config repo
ESOPTS="{'timeout': 60, 'max_retries': 3}" # 'timeout' parameter is deprecated
ELASTICSEARCH_INDEX_NAME_PREFIX="mc_search-*"
TERMFIELDS="article_title,text_content"
TERMAGGRS="top,significant,rare"
APP_NAME="news-search-api"

# Check if running on a checked-out tag
if git describe --exact-match --tags HEAD >/dev/null 2>&1; then
    return 0
else
    echo "This script must be run on a checked-out tag."
    exit 1
fi

# Check if running as root
if [ $(whoami) != "root" ]; then
    echo "This script must be run as root."
    exit 1
fi

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
    echo "-h, --help    Show this help message"
    echo ""
    echo "This script deploys the News Search API and UI. It must be run on a checked-out git tag."
    echo "The script will use the checked-out git tag as the image tag for deployment."
    echo "If the script is not run on a checked-out git tag, it will exit with an error message."
}


log()
{
    echo "$1"
}

zzz() {
    echo $1 | tr 'A-Za-z' 'N-ZA-Mn-za-m'
}

IMAGE_TAG=$(git describe --tags --abbrev=0)

# Parse command-line options
while (( "$#" )); do
    case "$1" in
        -h|--help)
            help
            exit 0
            ;;
        -d|--deployment-type)
            shift
            DEPLOYMENT_TYPE="$1"
            ;;
        -*|--*=) # unsupported flags
            echo "Error: Unsupported flag $1" >&2
            help
            exit 1
            ;;
        *) # preserve positional arguments
            PARAMS="$PARAMS $1"
            shift
            ;;
    esac
done

eval set -- "$PARAMS"

case "$DEPLOYMENT_TYPE" in
    staging)
        ENV_FILE=".staging"
        ;;
    production)
        ENV_FILE=".prod"
        ;;
    *)
        echo "Error: Invalid deployment type. Specify either 'staging' or 'prod'."
        exit 1
        ;;
esac

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
PRIVATE_CONF_FILE=$PRIVATE_CONF_REPO/$APP_NAME/$ENV_FILE.sh
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

echo "Deployment completed successfully!"
