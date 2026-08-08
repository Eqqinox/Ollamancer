---
name: dockerize-project
description: Containerize a project, write a correct Dockerfile and.dockerignore, build the image, and verify it runs. Use when the user asks to dockerize, containerize, "add a Dockerfile", or ship the app in a container.
license: MIT
---

# Dockerize a project

Produce a small, correct, reproducible image, and prove it builds and runs.

## Steps

1. **Understand the app.** Detect the language/runtime and how it starts: read
 `pyproject.toml`/`requirements.txt`, `package.json`, `go.mod`, and the entry point/command
 (`list_directory`, `read_file`). Note the port it listens on, if any.
2. **Write a `.dockerignore`** first (`write_file`): exclude `.venv/`, `node_modules/`, `.git/`,
 `__pycache__/`, `.agentic/`, build artifacts, secrets/`.env`. This keeps the build context small.
3. **Write the `Dockerfile`** (`write_file`) with good practices:
 - A specific, slim base image (e.g. `python:3.12-slim`, `node:20-slim`), not `latest`.
 - Copy only dependency manifests first, install deps, *then* copy the source (layer caching).
 - Use a **multi-stage** build if there's a compile/build step, so the final image is lean.
 - Run as a **non-root** user. Set `WORKDIR`, `EXPOSE <port>` if it serves, and a real
 `CMD`/`ENTRYPOINT` that starts the app.
4. **Build it** (confirm first, needs Docker): `run_command` `docker build -t <name>.`.
 Read the output; fix any build error and rebuild.
5. **Verify it runs**: `docker run --rm <name>` (add `-p host:container` for a server, then curl
 it). Confirm the app actually starts inside the container, not just that the image built.
6. **Report** the build/run commands and the final image size (`docker images <name>`).

## Notes

- Requires Docker to be installed and running; if it isn't, write the files but say the build
 can't be verified here.
- Never bake secrets into the image, use build args / runtime env vars, and keep `.env` ignored.
- Confirm before building/running (it consumes disk and time).
