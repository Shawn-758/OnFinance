CREATE DATABASE IF NOT EXISTS `onFinance`
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE `onFinance`;

CREATE TABLE IF NOT EXISTS clients (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(255) NULL,
  pan VARCHAR(20) NULL,
  aadhaar VARCHAR(20) NULL,
  email VARCHAR(255) NULL,
  phone VARCHAR(20) NULL,
  service_needed VARCHAR(50) NULL,
  gstin VARCHAR(20) NULL,
  status VARCHAR(40) NOT NULL DEFAULT 'received',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX ix_clients_pan (pan),
  INDEX ix_clients_email (email)
);

CREATE TABLE IF NOT EXISTS ingestion_jobs (
  id INT AUTO_INCREMENT PRIMARY KEY,
  source_type VARCHAR(40) NOT NULL,
  status VARCHAR(40) NOT NULL DEFAULT 'received',
  source_ref VARCHAR(255) NULL,
  raw_text TEXT NULL,
  extracted_json TEXT NULL,
  error_message TEXT NULL,
  client_id INT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  completed_at DATETIME NULL,
  CONSTRAINT fk_jobs_client FOREIGN KEY (client_id) REFERENCES clients (id)
);

CREATE TABLE IF NOT EXISTS documents (
  id INT AUTO_INCREMENT PRIMARY KEY,
  job_id INT NULL,
  client_id INT NULL,
  filename VARCHAR(255) NOT NULL,
  stored_path VARCHAR(500) NOT NULL,
  document_type VARCHAR(50) NOT NULL DEFAULT 'unknown',
  mime_type VARCHAR(100) NULL,
  extracted_text TEXT NULL,
  quality_flag VARCHAR(40) NOT NULL DEFAULT 'ok',
  blur_score VARCHAR(20) NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_docs_job FOREIGN KEY (job_id) REFERENCES ingestion_jobs (id),
  CONSTRAINT fk_docs_client FOREIGN KEY (client_id) REFERENCES clients (id)
);
