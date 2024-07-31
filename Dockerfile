# Use an official Python runtime as a parent image
FROM python:3.12

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory to /var/www
WORKDIR /var/www

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
    libpq-dev \
    dnsutils \
    build-essential \
    default-mysql-client \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create the directory for log files
RUN mkdir -p /var/www/logs
RUN chown -R www-data:www-data /var/www/logs

# Upgrade pip
RUN pip install --upgrade pip

COPY requirements.txt /var/www/
RUN pip install -r requirements.txt --upgrade

# Copy the current directory contents into the container at /var/www
COPY . /var/www

EXPOSE 9000

COPY entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh

# Set the entrypoint
ENTRYPOINT ["entrypoint.sh"]