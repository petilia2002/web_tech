CREATE SCHEMA IF NOT EXISTS catalog;

-- Компании (фирмы)
CREATE TABLE IF NOT EXISTS catalog.companies (
    company_id BIGSERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Автомобили
CREATE TABLE IF NOT EXISTS catalog.cars (
    car_id BIGSERIAL PRIMARY KEY,
    company_id BIGINT NOT NULL REFERENCES catalog.companies(company_id) ON DELETE CASCADE,
    model VARCHAR(200) NOT NULL,
    year INT,
    price NUMERIC(12,2),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Семпл-данные
INSERT INTO catalog.companies (name) VALUES
  ('АвтоМир'), ('СуперАвто'), ('МоторСервис')
ON CONFLICT DO NOTHING;

INSERT INTO catalog.cars (company_id, model, year, price)
SELECT c.company_id, v.model, v.year, v.price
FROM (VALUES
    ('АвтоМир', 'AM-100', 2019, 750000.00),
    ('АвтоМир', 'AM-200', 2021, 1250000.00),
    ('СуперАвто', 'SA-X', 2018, 520000.00),
    ('СуперАвто', 'SA-Z', 2022, 1890000.00),
    ('МоторСервис', 'MS-compact', 2017, 350000.00),
    ('МоторСервис', 'MS-pro', 2020, 980000.00)
) AS v(company_name, model, year, price)
JOIN catalog.companies c ON c.name = v.company_name
ON CONFLICT DO NOTHING;
