# Dockerfile for project

# inherit from python image
FROM ghcr.io/napari/napari:sha-77fc0af
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# update to latest pip version 
WORKDIR /app

# copy (locked) dependency files for installation of dependencies in intermediate layer
COPY pyproject.toml /app/pyproject.toml
COPY uv.lock /app/uv.lock
# install dependencies
RUN uv sync --frozen --no-install-workspace

# copy project files
COPY . /app

# initialize uv for project
RUN uv sync

# set entrypoint to run the application
ENTRYPOINT [ "uv", "run", "/app/startup.py" ]