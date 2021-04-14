# SimplyE Library Registry

A geographic search engine for matching people to the libraries that serve them.

## Installation

Because the Registry runs in a Docker container, the only required software is [Docker Desktop](https://www.docker.com/products/docker-desktop). The database and webapp containers expect to be able to operate on ports 5432 and 80, respectively--if those ports are in use already you may need to amend the `docker-compose.yml` file to add alternate ports.

_Note: If you would like to use the `Makefile` commands you will also need `make` in your `PATH`. They're purely convenience methods, so it isn't strictly required. If you don't want to use them just run the commands from the corresponding task in the `Makefile` manually. You can run `make help` to see the full list of commands._

### Building the Images

Local development uses two Docker images and one persistent Docker volume (for the PostgreSQL data directory). To create the base images:

```shell
make build
```

## Usage

### Running the Containers

You can start up the local compose cluster in the background with:

```shell
make up
```

Alternatively, if you want to keep a terminal attached to the running containers so you can see their output, use:

```shell
make up-watch
```

### Controlling the Cluster

* `make stop` to stop (but not remove) the running containers
* `make start` to restart a stopped cluster
* `make down` to stop and remove the running containers
* `make clean` to stop and remove the running containers and delete the database container's data volume

### Accessing the Containers

While the cluster is running, you can access the containers with these commands:

* `make db-session` - Starts a `psql` session on the database container as the superuser
* `make webapp-shell` - Open a shell on the webapp container

### Viewing the Web Interface

The registry listens (via Nginx) on port 80, so once the cluster is running you should be able to point a browser at `http://localhost/admin/` and access it with the username/password `admin/admin`.