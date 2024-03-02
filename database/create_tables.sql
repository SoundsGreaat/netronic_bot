CREATE TABLE departments
(
    id   SERIAL PRIMARY KEY,
    name VARCHAR(60) UNIQUE NOT NULL
);

CREATE TABLE sub_departments
(
    id            SERIAL PRIMARY KEY,
    department_id INTEGER REFERENCES departments (id),
    name          VARCHAR(60),
    UNIQUE (department_id, name)
);

CREATE TABLE employees
(
    id                SERIAL PRIMARY KEY,
    sub_department_id INTEGER REFERENCES sub_departments (id),
    name              VARCHAR(60)                          NOT NULL,
    phone             VARCHAR(15)                          NOT NULL,
    gender            CHAR(1) CHECK (gender IN ('M', 'F')) NOT NULL,
    position          VARCHAR(60)                          NOT NULL,
    telegram_username VARCHAR(60)                          NOT NULL,
    telegram_user_id  INTEGER                              NOT NULL
);

CREATE TABLE admins
(
    id          SERIAL PRIMARY KEY,
    employee_id INTEGER UNIQUE REFERENCES employees (id)
);