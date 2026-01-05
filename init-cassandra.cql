-- Crear keyspace para predicciones de vuelos
CREATE KEYSPACE IF NOT EXISTS flight_delays
WITH replication = {
  'class': 'SimpleStrategy',
  'replication_factor': 1
};

-- Usar el keyspace
USE flight_delays;

-- Crear tabla para almacenar las predicciones
CREATE TABLE IF NOT EXISTS flight_predictions (
  id UUID PRIMARY KEY,
  origin TEXT,
  dest TEXT,
  carrier TEXT,
  flightdate TEXT,
  dep_time TEXT,
  dep_delay DOUBLE,
  arr_time TEXT,
  arr_delay DOUBLE,
  distance DOUBLE,
  prediction INT,
  created_at TIMESTAMP
);

-- Crear índices secundarios para consultas comunes
CREATE INDEX IF NOT EXISTS ON flight_predictions (flightdate);
CREATE INDEX IF NOT EXISTS ON flight_predictions (origin);
CREATE INDEX IF NOT EXISTS ON flight_predictions (dest);
CREATE INDEX IF NOT EXISTS ON flight_predictions (carrier);
