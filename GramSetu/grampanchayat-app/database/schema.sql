CREATE DATABASE IF NOT EXISTS sakhwaniya_gp
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE sakhwaniya_gp;

-- Citizens + staff/admin users
CREATE TABLE IF NOT EXISTS users (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  full_name VARCHAR(150) NOT NULL,
  mobile VARCHAR(20) NOT NULL UNIQUE,
  email VARCHAR(150) NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  role ENUM('citizen','admin','staff') NOT NULL DEFAULT 'citizen',
  status ENUM('active','inactive') NOT NULL DEFAULT 'active',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_users_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Service application requests
CREATE TABLE IF NOT EXISTS service_requests (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  request_id VARCHAR(50) NOT NULL UNIQUE,
  service_code VARCHAR(50) NOT NULL,
  applicant_name VARCHAR(150) NOT NULL,
  mobile VARCHAR(20) NOT NULL,
  email VARCHAR(150) NULL,
  details_json JSON NULL,
  status ENUM('submitted','under_review','approved','rejected')
    NOT NULL DEFAULT 'submitted',
  submitted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_service_requests_mobile (mobile)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Citizen complaints
CREATE TABLE IF NOT EXISTS complaints (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  complaint_id VARCHAR(50) NOT NULL UNIQUE,
  full_name VARCHAR(150) NOT NULL,
  mobile VARCHAR(20) NOT NULL,
  email VARCHAR(150) NULL,
  category VARCHAR(100) NOT NULL,
  location VARCHAR(150) NOT NULL,
  details TEXT NOT NULL,
  status ENUM('open','in_progress','resolved','closed')
    NOT NULL DEFAULT 'open',
  assigned_department VARCHAR(100) NOT NULL DEFAULT 'General',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_complaints_mobile (mobile)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Public notices managed by admin
CREATE TABLE IF NOT EXISTS notices (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(180) NOT NULL,
  reference_no VARCHAR(80) NULL,
  summary TEXT NOT NULL,
  body TEXT NULL,
  issued_on DATE NOT NULL,
  download_url VARCHAR(255) NULL,
  is_published TINYINT(1) NOT NULL DEFAULT 1,
  created_by_user_id BIGINT UNSIGNED NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_notices_published (is_published, issued_on)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Dynamic government schemes and application forms
CREATE TABLE IF NOT EXISTS service_catalog (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  code VARCHAR(80) NOT NULL UNIQUE,
  slug VARCHAR(120) NOT NULL UNIQUE,
  title VARCHAR(180) NOT NULL,
  department VARCHAR(120) NOT NULL DEFAULT 'Gram Panchayat',
  category VARCHAR(120) NOT NULL DEFAULT 'Citizen Service',
  summary TEXT NOT NULL,
  intro TEXT NULL,
  eligibility TEXT NULL,
  documents TEXT NULL,
  instructions TEXT NULL,
  fields_json JSON NOT NULL,
  is_published TINYINT(1) NOT NULL DEFAULT 1,
  created_by_user_id BIGINT UNSIGNED NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_service_catalog_published (is_published, updated_at),
  INDEX idx_service_catalog_category (category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Uploaded service documents and complaint evidence
CREATE TABLE IF NOT EXISTS uploaded_documents (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  entity_type VARCHAR(40) NOT NULL,
  entity_ref VARCHAR(50) NOT NULL,
  field_name VARCHAR(80) NOT NULL DEFAULT 'supporting_documents',
  original_name VARCHAR(255) NOT NULL,
  stored_name VARCHAR(255) NOT NULL,
  stored_path VARCHAR(255) NOT NULL,
  mime_type VARCHAR(150) NULL,
  file_size BIGINT UNSIGNED NOT NULL DEFAULT 0,
  uploaded_by_mobile VARCHAR(20) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_uploaded_documents_entity (entity_type, entity_ref)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Delivery logs for SMS and email alerts
CREATE TABLE IF NOT EXISTS notification_logs (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  entity_type VARCHAR(40) NULL,
  entity_ref VARCHAR(50) NULL,
  event_code VARCHAR(80) NOT NULL,
  channel VARCHAR(20) NOT NULL,
  recipient VARCHAR(180) NOT NULL,
  subject VARCHAR(255) NULL,
  message_text TEXT NOT NULL,
  status VARCHAR(20) NOT NULL,
  error_text TEXT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_notification_logs_entity (entity_type, entity_ref),
  INDEX idx_notification_logs_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
