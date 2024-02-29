CREATE TABLE departments (
    id SERIAL PRIMARY KEY,
    name VARCHAR(60) UNIQUE
);

CREATE TABLE sub_departments (
    id SERIAL PRIMARY KEY,
    department_id INTEGER REFERENCES departments(id),
    name VARCHAR(60)
);

CREATE TABLE employees (
    id SERIAL PRIMARY KEY,
    sub_department_id INTEGER REFERENCES sub_departments(id),
    name VARCHAR(60),
    phone VARCHAR(15)
);
