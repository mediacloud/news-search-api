## Prerequisites

Before you begin, ensure you have the following prerequisites in place:

1. Docker: Docker must be installed on the host where you plan to set up the Swarm. You can download and install Docker from Docker's [official website](https://docs.docker.com/engine/install/ubuntu/#install-from-a-package).

2. Docker Compose: Make sure you have Docker Compose installed, as it's essential for managing multi-container applications. You can install Docker Compose by following the instructions in the official [documentation](https://docs.docker.com/compose/install/).


### Dev, Staging & production

A staging/production deployment expects to connect to an external Elasticsearch cluster, with the Elasticsearch urls provides as the env variable `ESHOSTS`


## Deployment

### deploy.sh options

```
Usage: ./deploy.sh [options]
Options:
-h, --help             Show this help message
-a, --use-latest-image Allow deployment without requiring a checked-out tag, uses 'latest' as image tag (only for dev)
-d, --deployment-type  Specify the deployment type (dev, staging or production)

```

### Local Development

Deployment in the dev environment can be done using the `deploy.sh` script.
The `deploy.sh` script expects us to deploy from a checked out tag, however for a deploy in development, we can use the `latest` tag to build our images.
The News Search API expects to connect to an Elasticsearch cluster. The staging & production deployments source the Elasticsearch cluster URL via `ESHOSTS` in the private configuration files.
In Dev deployment, export your ESHOSTS using the command

`export ESHOSTS="http://localhost:9200"`

Deployment in dev using latest tag

```
make dev-latest
```

Deployment in dev in a checked out tag

```
make dev
```

## Staging & Production

All releases are built and pushed to Dockerhub using the github workflow [here](../.github/workflows/docker-release.yml). We pull the pre-built images when deploying, based on the checked out deploy tag

When deploying a staging or production environment, use the `deploy.sh` script available [here](./deploy.sh).
The docker images for each of the stages are tagged with the git tag. The tagging should conform to [PEP 440](https://peps.python.org/pep-0440/). Further instructions on release and tagging available [here](../README.md)

For a staging deployment
```
make staging
```

A production deployment
```
make production
```

### Cleanup

A `dev` deployment creates a docker compose project prefixed with the logged_in user, while staging and production creates project_names `staging` and `production`

To cleanup dev compose project

``` sudo docker compose -p <project_name> down ```

To cleanup a staging & production deployments, run the commands

```
Staging

docker compose -p staging down
```

```
Production

docker compose -p production down
```
