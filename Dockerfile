# Use an official Python runtime as a parent image
FROM python:3.10

# Update and upgrade the package manager
RUN apt-get update && \
    apt-get install -y \
    sudo \
    vim \
    nano \
    curl \
    wget \
    unzip \
    git \
    iputils-ping \
    net-tools \
    dnsutils \
    build-essential \
    default-mysql-client \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --upgrade pip

# Set the working directory to /var/www
WORKDIR /var/www

# Only copy the files necessary for the application to run
COPY requirements.txt /var/www/
RUN pip install -r requirements.txt --upgrade

# Copy the current directory contents into the container at /var/www
COPY . /var/www

# Add the entrypoint script and set the execute permissions
COPY runsetup.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/runsetup.sh

# Set the entrypoint script
ENTRYPOINT ["runsetup.sh"]
