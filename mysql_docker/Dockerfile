FROM mysql:8.0

# Add a database
ENV MYSQL_DATABASE=gatekeeper
ENV MYSQL_ROOT_PASSWORD=`~G0Q3,Ju#

# Add the content of the sql-scripts/ directory to your image
# All scripts in docker-entrypoint-initdb.d/ are automatically
# executed during container startup
COPY ./sql_scripts/ /docker-entrypoint-initdb.d/
