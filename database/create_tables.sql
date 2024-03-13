CREATE TABLE IF NOT EXISTS departments
(
    id   SERIAL PRIMARY KEY,
    additional_instance BOOLEAN DEFAULT FALSE,
    name VARCHAR(60) UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS intermediate_departments
(
    id            SERIAL PRIMARY KEY,
    department_id INTEGER REFERENCES departments (id),
    name          VARCHAR(60),
    UNIQUE (department_id, name)
);

CREATE TABLE IF NOT EXISTS sub_departments
(
    id                         SERIAL PRIMARY KEY,
    department_id              INTEGER REFERENCES departments (id),
    intermediate_department_id INTEGER REFERENCES intermediate_departments (id),
    name                       VARCHAR(60),
    UNIQUE (department_id, name)
);

CREATE TABLE IF NOT EXISTS employees
(
    id                SERIAL PRIMARY KEY,
    sub_department_id INTEGER REFERENCES sub_departments (id),
    name              VARCHAR(60) NOT NULL,
    phone             VARCHAR(13) NOT NULL,
    position          VARCHAR(60) NOT NULL,
    telegram_username VARCHAR(32),
    telegram_user_id  BIGINT      NOT NULL
);


CREATE TABLE IF NOT EXISTS admins
(
    id          SERIAL PRIMARY KEY,
    employee_id INTEGER UNIQUE REFERENCES employees (id) ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS link_types
(
    id   SERIAL PRIMARY KEY,
    name VARCHAR(60) UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS links
(
    id           SERIAL PRIMARY KEY,
    name         VARCHAR(60)  NOT NULL,
    link         VARCHAR(255) NOT NULL,
    link_type_id INTEGER      NOT NULL REFERENCES link_types (id)
);