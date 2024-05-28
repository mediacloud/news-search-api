## Prerequisites

Before you begin, ensure you have the following prerequisites in place:

1. Docker: Docker must be installed on the host where you plan to set up the Swarm. You can download and install Docker from Docker's [official website](https://docs.docker.com/engine/install/ubuntu/#install-from-a-package).

2. Docker Compose: Make sure you have Docker Compose installed, as it's essential for managing multi-container applications. You can install Docker Compose by following the instructions in the official [documentation](https://docs.docker.com/compose/install/).

3. Docker Swarm setup: We require Docker swarm setup to deploy the News-Search-API. After installing docker and docker compose as per above, ensure Docker Swarm is setup following the instructions in the official [documentation](https://docs.docker.com/engine/swarm/)


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

To do a dev deployment, first export your `ESHOSTS` using the command

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


For a staging deployment
```
make staging
```

A production deployment
```
make production
```

### Cleanup

All deployments use distinct stack names to make them easily distinguishable. `dev` deployments use logged_in user prefix (to allow multiple deployments from different users on the same machine), while staging and production uses `staging` and `prod` stack name prefixes respectively.

To cleanup/shutdown `news-search-api` deployment, use the following command:

```docker stack rm <stack_name>```

To cleanup a dev deployment by user `johndoe`, run the command:
```docker stack rm johndoe```
