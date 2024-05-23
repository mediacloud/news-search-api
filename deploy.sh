#!/bin/bash
# deploy.sh - Deployment script for News Search API and UI

# Environment variables
APP_NAME="news-search-api"
API_PORT_BASE=8000
UI_PORT_BASE=8501
IMAGE_TAG="latest"

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
    echo "-a, --use-latest-image Allow deployment without requiring a checked-out tag, uses 'latest' as image tag (only for dev)"
    echo "-d, --deployment-type  Specify the deployment type (dev, staging or production)"
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

if [ $# -eq 0 ]; then
    help
    exit 1
fi

USE_LATEST_IMAGE=false
# Parse command-line options
while (( "$#" )); do
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
        -*|--*=) # unsupported flags
            echo "Error: Unsupported flag $1" >&2
            help
            exit 1
            ;;
    esac
done

if $USE_LATEST_IMAGE && [ "$DEPLOYMENT_TYPE" != "dev" ]; then
    echo "Error: The -a option is only allowed for 'dev' deployment type."
    exit 1
fi

case "$DEPLOYMENT_TYPE" in
    dev)
        API_PORT=$(expr $API_PORT_BASE + 100)
        UI_PORT=$(expr $UI_PORT_BASE + 100)
        PROJECT_NAME="$LOGIN_USER-dev"
        ENV_FILE="dev"
        ;;
    staging)
        API_PORT=$(expr $API_PORT_BASE + 200)
        UI_PORT=$(expr $UI_PORT_BASE + 200)
        PROJECT_NAME="staging"
        ENV_FILE="staging"
        ;;
    production)
        API_PORT=$API_PORT_BASE
        UI_PORT=$UI_PORT_BASE
        PROJECT_NAME="prod"
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

PRIVATE_CONF_DIR="news-search-private-conf"
rm -rf $PRIVATE_CONF_DIR
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

case "$DEPLOYMENT_TYPE" in
staging,production)
    PRIVATE_CONF_FILE=$PRIVATE_CONF_REPO/$APP_NAME.$ENV_FILE.sh
    cd ..
    ;;
dev)
    PRIVATE_CONF_FILE=./dev.sh
    ;;
esac


if [ ! -f $PRIVATE_CONF_FILE ]; then
    echo "FATAL: could not access $PRIVATE_CONF_FILE" 1>&2
    exit 1
fi
#source private conf to load SENTRY_DSN
. $PRIVATE_CONF_FILE

GH_REPO_PREFIX=$(zzz uggcf://tvguho.pbz/zrqvnpybhq)
GH_REPO_NAME=$(zzz arjf-frnepu-ncv)
DOCKER_COMPOSE_FILE="docker-compose.yml"

if $USE_LATEST_IMAGE; then
    BRANCH_OR_TAG=$(git rev-parse --abbrev-ref HEAD)
else
    BRANCH_OR_TAG=$IMAGE_TAG
fi

mv -f docker-compose.yml docker-compose-old.yml
echo "Fetching $DOCKER_COMPOSE_FILE from $GH_REPO_NAME repo..."
if ! curl -sSfL "$GH_REPO_PREFIX/$GH_REPO_NAME/raw/$BRANCH_OR_TAG/$DOCKER_COMPOSE_FILE" -o "$(pwd)/$DOCKER_COMPOSE_FILE"; then
    echo "FATAL: Could not fetch $DOCKER_COMPOSE_FILE from config repo"
    exit 1
fi

export INDEXES="mc_search"
export ESOPTS='{"timeout": 60, "max_retries": 3}' # 'timeout' parameter is deprecated
export ELASTICSEARCH_INDEX_NAME_PREFIX="mc_search-*"
export TERMFIELDS="article_title,text_content"
export TERMAGGRS="top,significant,rare"
export ESHOSTS=${ESHOSTS}
export SENTRY_DSN=${SENTRY_DSN}
export SENTRY_ENVIRONMENT=${SENTRY_ENVIRONMENT}
export API_PORT=${API_PORT}
export UI_PORT=${UI_PORT}
export IMAGE_TAG

# Deploy services using Docker Compose
echo "Deploying services with image, project name: $PROJECT_NAME & tag: $IMAGE_TAG"
if [ "$DEPLOYMENT_TYPE" = "dev" ] && $USE_LATEST_IMAGE; then
    docker compose -f "$(pwd)/$DOCKER_COMPOSE_FILE" -p "$PROJECT_NAME" up --build -d
else
    docker compose -f "$(pwd)/$DOCKER_COMPOSE_FILE" -p "$PROJECT_NAME" up -d
fi
echo "Deployment completed successfully!"
