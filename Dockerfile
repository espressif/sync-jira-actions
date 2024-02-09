FROM node:20-bookworm-slim

# Setting environment variables
ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8

# Install Python, venv, and other essentials
RUN : \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        python3.11 \
        python3.11-venv \
        python3-pip \
        python3-setuptools \
    && rm -rf /var/lib/apt/lists/*

# Enable virtual environment for subsequent commands (safe for Debian BookWorm)
RUN python3.11 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip

# Install Python dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Install Node.js dependencies
RUN npm i -g @shogobg/markdown2confluence@0.1.6

# Copy Python scripts
COPY sync_jira_actions/ /sync_jira_actions

# Define the entrypoint to use the virtual environment's Python interpreter
ENTRYPOINT ["/opt/venv/bin/python", "/sync_jira_actions/sync_to_jira.py"]
