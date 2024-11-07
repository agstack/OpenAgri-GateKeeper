CREATE DATABASE IF NOT EXISTS gatekeeper;
ALTER DATABASE gatekeeper CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON gatekeeper.* TO 'gatekeeper_admin'@'%' IDENTIFIED BY 'asdasdasd';
FLUSH PRIVILEGES;