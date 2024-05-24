## Prerequisites

Before you begin, ensure you have the following prerequisites in place:

1. Docker: Docker must be installed on the host where you plan to set up the Swarm. You can download and install Docker from Docker's [official website](https://docs.docker.com/engine/install/ubuntu/#install-from-a-package).

2. Docker Compose: Make sure you have Docker Compose installed, as it's essential for managing multi-container applications. You can install Docker Compose by following the instructions in the official [documentation](https://docs.docker.com/compose/install/).


### Dev, Staging & production

3. Elasticsearch Cluster: A news-search-api deployment expects to connect to an external Elasticsearch cluster. The URLs to the cluster must be provide via the environment variable `ESHOSTS`


## Deployment

The `news-search-api` deployment are done using the `deploy.sh` script. `deploy.sh` expects deployments to be done from a checked out git tag. However, for a local development run, `deploy.sh` provides `-a` option to run `news-search-api` from current git branch even if the branch doesn't contain a checked out tag. A Docker image tagged `latest` will be created in this case.

This image is neither meant to be pushed to docker hub nor used for staging/prod deployments.

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

## Staging & Prod Deployments

All `news-search-api` images are built and pushed to Docker Hub using Github Action [workflow](../.github/workflows/docker-release.yml). The git tags should conform to [PEP 440](https://peps.python.org/pep-0440/). Further instructions on release and tagging available on the [README.md](../README.md)

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

All deployments use distinct [project names](https://docs.docker.com/compose/project-name/) to make them easily distinguishable. `dev` deployments use logged_in user prefix and `-dev` suffix (to allow multiple deployments from different users on the same machine), while staging and production uses `staging` and `prod` project names respectively.

To cleanup/shutdown `news-search-api` deployment, use the following command:

```sudo docker compose -p <project_name> down```

To cleanup a dev deployment by user `johndoe`, run the command:
```sudo docker compose -p johndoe-dev down```

To cleanup a staging & production deployments, run the commands

```
Staging

docker compose -p staging down
```

```
Production

docker compose -p production down
```
