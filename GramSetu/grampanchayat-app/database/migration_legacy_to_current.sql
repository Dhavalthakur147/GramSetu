CREATE DATABASE IF NOT EXISTS sakhwaniya_gp
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE sakhwaniya_gp;

-- Ensure current app tables exist.
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

-- Detect current/legacy structures.
SET @has_users_table := (
  SELECT COUNT(*) FROM information_schema.tables
  WHERE table_schema = DATABASE() AND table_name = 'users'
);
SET @has_complaints_table := (
  SELECT COUNT(*) FROM information_schema.tables
  WHERE table_schema = DATABASE() AND table_name = 'complaints'
);

SET @has_users_mobile := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'users' AND column_name = 'mobile'
);
SET @has_users_phone := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'users' AND column_name = 'phone'
);

SET @has_complaint_number := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'complaints' AND column_name = 'complaint_number'
);
SET @has_complaints_citizen_id := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'complaints' AND column_name = 'citizen_id'
);
SET @has_complaints_complaint_id := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'complaints' AND column_name = 'complaint_id'
);
SET @has_complaints_full_name := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'complaints' AND column_name = 'full_name'
);
SET @has_complaints_mobile := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'complaints' AND column_name = 'mobile'
);
SET @has_complaints_email := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'complaints' AND column_name = 'email'
);
SET @has_complaints_assigned_department := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'complaints' AND column_name = 'assigned_department'
);

-- users: add mobile column if legacy users table has only phone.
SET @sql := IF(
  @has_users_table > 0 AND @has_users_mobile = 0,
  'ALTER TABLE users ADD COLUMN mobile VARCHAR(20) NULL AFTER full_name',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- users: copy legacy phone -> mobile where needed.
SET @sql := IF(
  @has_users_table > 0 AND @has_users_phone > 0,
  'UPDATE users SET mobile = COALESCE(NULLIF(mobile, ''''), phone) WHERE (mobile IS NULL OR mobile = '''') AND phone IS NOT NULL AND phone <> ''''',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- complaints: add new app columns on legacy table if missing.
SET @sql := IF(
  @has_complaints_table > 0 AND @has_complaints_complaint_id = 0,
  'ALTER TABLE complaints ADD COLUMN complaint_id VARCHAR(50) NULL AFTER id',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF(
  @has_complaints_table > 0 AND @has_complaints_full_name = 0,
  'ALTER TABLE complaints ADD COLUMN full_name VARCHAR(150) NULL AFTER complaint_id',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF(
  @has_complaints_table > 0 AND @has_complaints_mobile = 0,
  'ALTER TABLE complaints ADD COLUMN mobile VARCHAR(20) NULL AFTER full_name',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF(
  @has_complaints_table > 0 AND @has_complaints_email = 0,
  'ALTER TABLE complaints ADD COLUMN email VARCHAR(150) NULL AFTER mobile',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF(
  @has_complaints_table > 0 AND @has_complaints_assigned_department = 0,
  'ALTER TABLE complaints ADD COLUMN assigned_department VARCHAR(100) NOT NULL DEFAULT ''General'' AFTER status',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- complaints: copy legacy complaint_number -> complaint_id.
SET @sql := IF(
  @has_complaints_table > 0 AND @has_complaint_number > 0,
  'UPDATE complaints SET complaint_id = COALESCE(NULLIF(complaint_id, ''''), complaint_number) WHERE complaint_number IS NOT NULL AND complaint_number <> ''''',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- complaints: backfill citizen details from users.
SET @sql := IF(
  @has_complaints_table > 0 AND @has_complaints_citizen_id > 0,
  'UPDATE complaints c LEFT JOIN users u ON u.id = c.citizen_id
   SET c.full_name = COALESCE(NULLIF(c.full_name, ''''), u.full_name),
       c.mobile = COALESCE(NULLIF(c.mobile, ''''), u.mobile),
       c.email = COALESCE(NULLIF(c.email, ''''), u.email)',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- complaints: fallback values for mandatory new fields.
SET @sql := IF(
  @has_complaints_table > 0,
  'UPDATE complaints
   SET full_name = COALESCE(NULLIF(full_name, ''''), ''Citizen''),
       mobile = COALESCE(NULLIF(mobile, ''''), ''NA''),
       assigned_department = COALESCE(NULLIF(assigned_department, ''''), ''General'')',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Migrate legacy applications/services -> service_requests.
SET @has_applications := (
  SELECT COUNT(*) FROM information_schema.tables
  WHERE table_schema = DATABASE() AND table_name = 'applications'
);
SET @has_services := (
  SELECT COUNT(*) FROM information_schema.tables
  WHERE table_schema = DATABASE() AND table_name = 'services'
);

SET @sql := IF(
  @has_applications = 0,
  'SELECT 1',
  IF(
    @has_services > 0,
    'INSERT INTO service_requests
      (request_id, service_code, applicant_name, mobile, email, details_json, status, submitted_at, updated_at)
     SELECT
      a.application_number,
      COALESCE(s.code, CONCAT(''service_'', a.service_id)),
      COALESCE(u.full_name, ''Citizen''),
      COALESCE(NULLIF(u.mobile, ''''), CONCAT(''LEGACY'', a.applicant_id)),
      u.email,
      a.data,
      CASE a.status
        WHEN ''pending'' THEN ''under_review''
        WHEN ''submitted'' THEN ''submitted''
        WHEN ''approved'' THEN ''approved''
        WHEN ''rejected'' THEN ''rejected''
        ELSE ''submitted''
      END,
      COALESCE(a.submitted_at, CURRENT_TIMESTAMP),
      COALESCE(a.reviewed_at, a.submitted_at, CURRENT_TIMESTAMP)
     FROM applications a
     LEFT JOIN services s ON s.id = a.service_id
     LEFT JOIN users u ON u.id = a.applicant_id
     LEFT JOIN service_requests sr ON sr.request_id = a.application_number
     WHERE sr.id IS NULL',
    'INSERT INTO service_requests
      (request_id, service_code, applicant_name, mobile, email, details_json, status, submitted_at, updated_at)
     SELECT
      a.application_number,
      CONCAT(''service_'', a.service_id),
      COALESCE(u.full_name, ''Citizen''),
      COALESCE(NULLIF(u.mobile, ''''), CONCAT(''LEGACY'', a.applicant_id)),
      u.email,
      a.data,
      CASE a.status
        WHEN ''pending'' THEN ''under_review''
        WHEN ''submitted'' THEN ''submitted''
        WHEN ''approved'' THEN ''approved''
        WHEN ''rejected'' THEN ''rejected''
        ELSE ''submitted''
      END,
      COALESCE(a.submitted_at, CURRENT_TIMESTAMP),
      COALESCE(a.reviewed_at, a.submitted_at, CURRENT_TIMESTAMP)
     FROM applications a
     LEFT JOIN users u ON u.id = a.applicant_id
     LEFT JOIN service_requests sr ON sr.request_id = a.application_number
     WHERE sr.id IS NULL'
  )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
