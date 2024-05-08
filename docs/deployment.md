## Prerequisites

Before you begin, ensure you have the following prerequisites in place:

1. Docker: Docker must be installed on the host where you plan to set up the Swarm. You can download and install Docker from Docker's [official website](https://docs.docker.com/engine/install/ubuntu/#install-from-a-package).

2. Docker Compose: Make sure you have Docker Compose installed, as it's essential for managing multi-container applications. You can install Docker Compose by following the instructions in the official [documentation](https://docs.docker.com/compose/install/).

## Network Setup

### Local Development
The New Search API expects to connect to an Elasticsearch cluster. When running this with an external cluster, we need to define the `news-search-api` and the Elasticsearch cluster to run from the same docker network.

If relying on a shared network for the Search API and the `story-indexer`, ensure the `docker-compose.yml` is attached to th overlay network created above.

To create the network (if non exists)

    `docker network create -d overlay --attachable story-indexer`

### Dev, Staging & production

A staging/production deployment expects to connect to an external Elasticsearch cluster, with the Elasticsearch urls provides as the env variable `ESHOSTS`


## Deployment

### Local Development

Deployment in the dev environment can be done using the `Makefile` command `make up`.
For development purposes all our images are build and tagged with the `latest` tags, as initialized in the Makefile.

## Dev, Staging & Production

All releases are built and pushed to Dockerhub using the github workflow [here](../.github/workflows/docker-release.yml). We pull the pre-built images when deploying, based on the checked ou deploy tag

When deploying a staging or production environment, use the `deploy.sh` script available [here](./deploy.sh).
The `deploy.sh` script expects us to deploy from a checked out tag. The docker images for each of the stages are tagged with the git tag, the tagging should conform to [PEP 440](https://peps.python.org/pep-0440/). Further instructions on release and tagging available [here](../README.md)

The `deploy.sh` script expects a deploy option -d (that specifies the deployment stage (dev, staging/production))

e.g

```
Staging deployment
sudo ./deploy.sh -d staging

Production
sudo ./deploy.sh -d prod
```

A `dev` deployment creates a docker compose project prefixed with the logged_in user, as

``` sudo docker compose -p $"LOGIN-USER-dev" up -d```

To cleanup a dev deployment, run the command

``` sudo docker compose down -p $"LOGIN-USER-dev" ```
