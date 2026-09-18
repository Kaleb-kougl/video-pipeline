# syntax=docker/dockerfile:1
#
#
# STATUS: this Dockerfile has NOT been built or run. The Docker daemon was
# unavailable on the machine where it was written, so it is unverified --
# reviewed by eye and derived from a dependency set (requirements-demo.txt)
# that WAS proven sufficient by building a clean venv from it and rendering
# the demo. Expect to need small fixes on first build. The estimated ~500 MB
# image size below is an estimate, not a measurement.
# Offline demo image: `docker run` it and it renders a real, playable MP4.
# No API key, no network, no 1.1 GB ML download.
#
# ---------------------------------------------------------------------------
# A note on size, because it is a deliberate trade
# ---------------------------------------------------------------------------
# requirements.txt pins torch, transformers, sentence-transformers, chromadb,
# scipy and scikit-learn: comfortably over 1 GB of wheels, and an image built
# from it lands around 3 GB. The demo path touches none of them - the
# ChromaDB-backed character agent is replaced by a canned stand-in, and both
# agents/ and utils/ already guard those imports behind try/except ImportError.
#
# So this image installs requirements-demo.txt instead (see that file for the
# line-by-line reasoning). This is the DEMO image, not a production image. A
# real run - live Gemini summarisation, Imagen frames, ChromaDB character
# memory - needs the full `pip install -r requirements.txt`.
#
# On ffmpeg: MoviePy shells out to ffmpeg, and the binary it invokes is the
# static build that the pinned imageio-ffmpeg wheel ships. That binary is
# symlinked onto PATH below and pointed at explicitly via FFMPEG_BINARY, so
# ffmpeg is genuinely present and genuinely used. Installing Debian's ffmpeg
# package on top would add a few hundred MB of duplicate codecs for nothing.
# ---------------------------------------------------------------------------

# --- Stage 1: build the virtualenv -----------------------------------------
FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# Every wheel in requirements-demo.txt has a manylinux build, so no compiler is
# needed. The separate stage exists to keep pip's metadata and any build
# scratch out of the shipped layers.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements-demo.txt .
RUN pip install --upgrade pip && pip install -r requirements-demo.txt

# Drop test/doc payloads that some of these wheels carry.
RUN find /opt/venv -type d -name "__pycache__" -prune -exec rm -rf {} + && \
    find /opt/venv -type d -name "tests" -prune -exec rm -rf {} +

# --- Stage 2: runtime -------------------------------------------------------
FROM python:3.12-slim

# make: the reviewer runs `make demo`, same as on the host.
# fonts-dejavu-core (~1 MB): media/media_utils.py hardcodes a macOS Arial path
#   for its placeholder frames and silently falls back to PIL's tiny bitmap
#   font when it is missing, which makes the output unreadable. Rather than
#   edit that module, the image provides a TrueType face at the path it looks
#   for. Cosmetic accommodation, called out here so it is not a surprise.
RUN apt-get update && \
    apt-get install -y --no-install-recommends make fonts-dejavu-core && \
    rm -rf /var/lib/apt/lists/* && \
    mkdir -p /System/Library/Fonts && \
    ln -s /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf /System/Library/Fonts/Arial.ttf

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Put the bundled static ffmpeg on PATH and tell MoviePy to use it explicitly.
RUN ln -s "$(python -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')" \
    /usr/local/bin/ffmpeg && ffmpeg -version | head -1
ENV FFMPEG_BINARY=/usr/local/bin/ffmpeg

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEMO_OUTPUT_DIR=/out

WORKDIR /app
COPY . /app

# The demo renders into /out (DEMO_OUTPUT_DIR above). Mount a host directory
# there to keep the MP4:
#   docker run --rm --network none -v "$PWD/demo_output:/out" <image>
# No VOLUME is declared, so without a mount the output simply stays in the
# container layer and `docker cp` can retrieve it.
#
# This runs as root, so on Linux the files on a bind mount land root-owned.
# Add `--user "$(id -u):$(id -g)"` to the run if that matters.

# VENV=/opt/venv makes the Makefile use the interpreter that is already here
# instead of bootstrapping a new venv.
CMD ["make", "demo", "VENV=/opt/venv"]
