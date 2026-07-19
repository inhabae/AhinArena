# Production API and worker images

The API and worker images are separate, minimal Python 3.12 images. Both use
the same pinned multi-platform Python base manifest and an exact production
dependency lock (including transitive packages). Builds install dependencies before application source is
copied, so changing application code reuses the dependency layer.

The images run as UID/GID `10001` (`ahinarena`) and set
`DEPLOY_ENVIRONMENT=production` and `REQUIRE_SECURE_COOKIES=true`. Supply all
runtime values in `.env.production.example`, including PostgreSQL, explicit
HTTPS CORS/frontend origins, email, and worker sandbox settings; do not place
secrets in an image or its build arguments.

## Build and tag

Build from the repository root. Replace `VERSION` with an immutable release
identifier (for example, a Git tag) and `VCS_REF` with the source commit.

```sh
VERSION=v1.2.3
VCS_REF=$(git rev-parse --verify HEAD)
BUILD_DATE=$(git show -s --format=%cI HEAD)

docker build --pull \
  -f docker/api.Dockerfile \
  --build-arg VERSION="$VERSION" --build-arg VCS_REF="$VCS_REF" --build-arg BUILD_DATE="$BUILD_DATE" \
  -t ghcr.io/your-org/ahinarena-api:"$VERSION" \
  -t ghcr.io/your-org/ahinarena-api:"$VCS_REF" .

docker build --pull \
  -f docker/worker.Dockerfile \
  --build-arg VERSION="$VERSION" --build-arg VCS_REF="$VCS_REF" --build-arg BUILD_DATE="$BUILD_DATE" \
  -t ghcr.io/your-org/ahinarena-worker:"$VERSION" \
  -t ghcr.io/your-org/ahinarena-worker:"$VCS_REF" .
```

Do not deploy a mutable `latest` tag. Promote the commit tag or record the
resulting image digest (`docker image inspect --format '{{index .RepoDigests 0}}' …`).

## Migrate and run

Create a production-only environment file outside source control using
`.env.production.example` and the secret-management guidance in
`docs/production-configuration.md`:

```dotenv
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@postgres.example:5432/ahin_arena
CORS_ALLOWED_ORIGINS=https://arena.example.com
BOT_SANDBOX_IMAGE=ghcr.io/your-org/ahinarena-bot-runner@sha256:REPLACE_ME
```

Apply database migrations once per deployment:

```sh
docker run --rm --env-file /secure/path/ahinarena.production.env \
  ghcr.io/your-org/ahinarena-api:v1.2.3 alembic upgrade head
```

Start the API with a read-only root filesystem. The `/tmp` mount is provided
for libraries that require temporary files.

```sh
docker run -d --name ahinarena-api --restart unless-stopped \
  --env-file /secure/path/ahinarena.production.env \
  --read-only --tmpfs /tmp:rw,noexec,nosuid,nodev,size=64m \
  -p 8000:8000 ghcr.io/your-org/ahinarena-api:v1.2.3
```

The worker starts match containers, so it needs the host Docker socket and
permission to access it. On Linux, add the socket's group ID while retaining
the non-root image user:

```sh
DOCKER_SOCKET_GID=$(stat -c '%g' /var/run/docker.sock)
docker run -d --name ahinarena-worker --restart unless-stopped \
  --env-file /secure/path/ahinarena.production.env \
  --group-add "$DOCKER_SOCKET_GID" \
  -v /var/run/docker.sock:/var/run/docker.sock \
  --read-only --tmpfs /tmp:rw,noexec,nosuid,nodev,size=64m \
  ghcr.io/your-org/ahinarena-worker:v1.2.3
```

Access to the Docker socket is effectively host-root access. Run the worker on
a dedicated host or use a narrowly scoped Docker API proxy; never expose the
socket through a network port. The worker must also be able to pull the pinned
`BOT_SANDBOX_IMAGE` before processing jobs.

## Scan, SBOM, and maintenance

Scan the exact images before publishing and attach an SPDX SBOM to the release:

```sh
trivy image --severity HIGH,CRITICAL --exit-code 1 ghcr.io/your-org/ahinarena-api:v1.2.3
trivy image --severity HIGH,CRITICAL --exit-code 1 ghcr.io/your-org/ahinarena-worker:v1.2.3
syft ghcr.io/your-org/ahinarena-api:v1.2.3 -o spdx-json=ahinarena-api.spdx.json
syft ghcr.io/your-org/ahinarena-worker:v1.2.3 -o spdx-json=ahinarena-worker.spdx.json
```

Treat the pinned image digests and dependency versions as release inputs:
update them intentionally, rebuild, run tests, scan again, and record the new
image digests and SBOMs with the release.
