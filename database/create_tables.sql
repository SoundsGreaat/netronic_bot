CREATE TABLE IF NOT EXISTS departments
(
    id   SERIAL PRIMARY KEY,
    name VARCHAR(60) UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS sub_departments
(
    id            SERIAL PRIMARY KEY,
    department_id INTEGER REFERENCES departments (id),
    name          VARCHAR(60),
    UNIQUE (department_id, name)
);

CREATE TABLE IF NOT EXISTS employees
(
    id                SERIAL PRIMARY KEY,
    sub_department_id INTEGER REFERENCES sub_departments (id),
    name              VARCHAR(60)                          NOT NULL,
    phone             VARCHAR(13)                          NOT NULL,
    gender            CHAR(1) CHECK (gender IN ('M', 'F')) NOT NULL,
    position          VARCHAR(60)                          NOT NULL,
    telegram_username VARCHAR(32),
    telegram_user_id  INTEGER                              NOT NULL
);

CREATE TABLE IF NOT EXISTS admins
(
    id          SERIAL PRIMARY KEY,
    employee_id INTEGER UNIQUE REFERENCES employees (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS business_process_links
(
    id   SERIAL PRIMARY KEY,
    name VARCHAR(60) UNIQUE NOT NULL,
    link VARCHAR(255)       NOT NULL
);

CREATE TABLE IF NOT EXISTS news_feed_links
(
    id   SERIAL PRIMARY KEY,
    name VARCHAR(60) UNIQUE NOT NULL,
    link VARCHAR(255)       NOT NULL
);

CREATE TABLE IF NOT EXISTS knowledge_base_links
(
    id   SERIAL PRIMARY KEY,
    name VARCHAR(60) UNIQUE NOT NULL,
    link VARCHAR(255)       NOT NULL
);