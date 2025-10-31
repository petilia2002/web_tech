CREATE EXTENSION IF NOT EXISTS citext;

CREATE TABLE auth.users (
    user_id BIGSERIAL PRIMARY KEY,
    last_name VARCHAR(100) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    email CITEXT NOT NULL UNIQUE,
    login CITEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT email_format_chk CHECK (email ~* '^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$')
);

CREATE TABLE auth.roles (
    role_id SMALLSERIAL PRIMARY KEY,
    role_name VARCHAR(50) NOT NULL UNIQUE,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE auth.user_roles (
    user_id BIGINT NOT NULL REFERENCES auth.users(user_id) ON DELETE CASCADE,
    role_id SMALLINT NOT NULL REFERENCES auth.roles(role_id) ON DELETE RESTRICT,
    granted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    granted_by BIGINT NULL REFERENCES auth.users(user_id),
    PRIMARY KEY (user_id, role_id)
);

CREATE TABLE auth.user_visits(
    visit_id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES auth.users(user_id) ON DELETE CASCADE,
    page_name VARCHAR(100) NOT NULL,
    visited_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
