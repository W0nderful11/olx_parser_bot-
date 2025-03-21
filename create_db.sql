-- Создайте базу данных, если она ещё не создана:
CREATE DATABASE olx_db;

-- Подключитесь к базе данных olx_db и выполните:
CREATE TABLE IF NOT EXISTS olx_data (
    id SERIAL PRIMARY KEY,
    external_id TEXT,
    title TEXT,
    price TEXT,
    url TEXT,
    phone TEXT,
    description TEXT,
    category TEXT,
    created TIMESTAMP DEFAULT NOW()
);
