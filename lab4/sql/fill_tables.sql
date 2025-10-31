-- 1) Тестовые роли (5 шт.)

INSERT INTO auth.roles (role_name, is_enabled) VALUES
  ('admin', TRUE), ('editor', TRUE), ('user', TRUE),
  ('moderator', FALSE), ('viewer', TRUE);

-- 2) Тестовые пользователи (7 шт.)

INSERT INTO auth.users (last_name, first_name, email, login, password_hash) VALUES
  ('Иванов',   'Иван',    'ivanov@example.com',     'ivanov',     '$2b$12$demo_hash_ivanov_______________60chars'),
  ('Петров',   'Пётр',    'petrov@example.com',     'petrov',     '$2b$12$demo_hash_petrov_______________60chars'),
  ('Сидорова', 'Анна',    'sidorova@example.com',   'asidorova',  '$2b$12$demo_hash_asidorova____________60chars'),
  ('Кузнецова','Мария',   'mkuznetsova@example.com','mkuznetsova','$2b$12$demo_hash_mkuznetsova__________60chars'),
  ('Смирнов',  'Алексей', 'asmirnov@example.com',   'asmirnov',   '$2b$12$demo_hash_asmirnov_____________60chars'),
  ('Васильев', 'Дмитрий', 'dvasiliev@example.com',  'dvasiliev',  '$2b$12$demo_hash_dvasiliev____________60chars'),
  ('Орлова',   'Ирина',   'iorlova@example.com',    'iorlova',    '$2b$12$demo_hash_iorlova______________60chars');

-- 3) Назначения ролей (многие-ко-многим) через подзапросы

-- Иванов: admin, user
INSERT INTO auth.user_roles (user_id, role_id)
SELECT u.user_id, r.role_id FROM auth.users u, auth.roles r
WHERE u.login='ivanov' AND r.role_name IN ('admin','user');

-- Петров: editor, user
INSERT INTO auth.user_roles (user_id, role_id)
SELECT u.user_id, r.role_id FROM auth.users u, auth.roles r
WHERE u.login='petrov' AND r.role_name IN ('editor','user');

-- Сидорова: user
INSERT INTO auth.user_roles (user_id, role_id)
SELECT u.user_id, r.role_id FROM auth.users u, auth.roles r
WHERE u.login='asidorova' AND r.role_name IN ('user');

-- Кузнецова: editor, moderator
INSERT INTO auth.user_roles (user_id, role_id)
SELECT u.user_id, r.role_id FROM auth.users u, auth.roles r
WHERE u.login='mkuznetsova' AND r.role_name IN ('editor','moderator');

-- Смирнов: viewer
INSERT INTO auth.user_roles (user_id, role_id)
SELECT u.user_id, r.role_id FROM auth.users u, auth.roles r
WHERE u.login='asmirnov' AND r.role_name IN ('viewer');

-- Васильев: user
INSERT INTO auth.user_roles (user_id, role_id)
SELECT u.user_id, r.role_id FROM auth.users u, auth.roles r
WHERE u.login='dvasiliev' AND r.role_name IN ('user');

-- Орлова: admin, editor, user
INSERT INTO auth.user_roles (user_id, role_id)
SELECT u.user_id, r.role_id FROM auth.users u, auth.roles r
WHERE u.login='iorlova' AND r.role_name IN ('admin','editor','user');

-- Контрольные выборки для скриншотов
SELECT * FROM auth.users ORDER BY user_id;
SELECT * FROM auth.roles ORDER BY role_id;
SELECT u.login, r.role_name
FROM auth.user_roles ur
JOIN auth.users u ON u.user_id=ur.user_id
JOIN auth.roles r ON r.role_id=ur.role_id
ORDER BY u.login, r.role_name;

-- 4) Посещения пользователя
INSERT INTO auth.user_visits (user_id, page_name)
SELECT user_id, 'Главная страница' FROM auth.users
WHERE last_name = 'Петренков';

INSERT INTO auth.user_visits (user_id, page_name)
SELECT user_id, 'Страница 2' FROM auth.users
WHERE last_name = 'Петренков';

INSERT INTO auth.user_visits (user_id, page_name)
SELECT user_id, 'Страница 3' FROM auth.users
WHERE last_name = 'Петренков';

INSERT INTO auth.user_visits (user_id, page_name)
SELECT user_id, 'Главная страница' FROM auth.users
WHERE last_name = 'Сидорова';
