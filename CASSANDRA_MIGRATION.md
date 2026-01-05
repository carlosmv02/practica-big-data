# Migración de MongoDB a Cassandra

Este documento explica los cambios realizados para migrar el sistema de predicción de retrasos de vuelos desde MongoDB a Apache Cassandra.

## Motivación del Cambio

La migración de MongoDB a Cassandra se realizó por las siguientes razones:

1. **Escalabilidad Horizontal**: Cassandra está diseñada para escalar horizontalmente de manera más eficiente que MongoDB, permitiendo agregar nodos sin interrupciones.

2. **Alto Rendimiento en Escritura**: Cassandra optimiza las escrituras distribuidas, ideal para sistemas de streaming donde Spark escribe predicciones continuamente.

3. **Sin Punto Único de Fallo**: Cassandra utiliza una arquitectura peer-to-peer sin nodos maestros, eliminando puntos únicos de fallo.

4. **Mejor para Series Temporales**: El modelo de datos de Cassandra es más adecuado para datos de series temporales como predicciones de vuelos.

5. **Tolerancia a Particiones**: Cassandra prioriza disponibilidad y tolerancia a particiones (AP en teorema CAP), ideal para sistemas distribuidos.

## Cambios Realizados

### 1. Configuración de Docker (`docker-compose.yml`)

**Antes:**
```yaml
mongodb:
  image: mongo:latest
  ports:
    - "27017:27017"
  volumes:
    - mongodb_data:/data/db
  healthcheck:
    test: ["CMD", "mongosh", "--eval", "db.adminCommand('ping')"]
```

**Después:**
```yaml
cassandra:
  image: cassandra:4.1
  ports:
    - "9042:9042"
  volumes:
    - cassandra_data:/var/lib/cassandra
  environment:
    - CASSANDRA_CLUSTER_NAME=FlightDelayCluster
    - CASSANDRA_DC=datacenter1
    - CASSANDRA_RACK=rack1
  healthcheck:
    test: ["CMD-SHELL", "cqlsh -e 'describe cluster'"]
    interval: 30s
    timeout: 10s
    retries: 5
    start_period: 60s
```

**Cambios:**
- Puerto: `27017` → `9042`
- Imagen: `mongo:latest` → `cassandra:4.1`
- Volumen: `mongodb_data` → `cassandra_data`
- Healthcheck: `mongosh` → `cqlsh`
- Tiempo de inicio aumentado a 60s (Cassandra tarda más en arrancar)

### 2. Dependencias Python (`requirements.txt`)

**Antes:**
```
pymongo
```

**Después:**
```
cassandra-driver
```

**Cambio:** Reemplazado el driver de MongoDB por el driver oficial de Cassandra para Python.

### 3. Dependencias Scala (`build.sbt`)

**Antes:**
```scala
"org.mongodb.spark" %% "mongo-spark-connector" % "10.4.1"
```

**Después:**
```scala
"com.datastax.spark" %% "spark-cassandra-connector" % "3.4.1"
```

**Cambio:** Reemplazado el conector de MongoDB por el conector oficial de Cassandra para Spark.

### 4. Esquema de Base de Datos (`init-cassandra.cql`)

Se creó un nuevo archivo para inicializar el esquema de Cassandra:

```cql
CREATE KEYSPACE IF NOT EXISTS flight_delays
WITH replication = {
  'class': 'SimpleStrategy',
  'replication_factor': 1
};

USE flight_delays;

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

-- Índices secundarios para consultas comunes
CREATE INDEX IF NOT EXISTS ON flight_predictions (flightdate);
CREATE INDEX IF NOT EXISTS ON flight_predictions (origin);
CREATE INDEX IF NOT EXISTS ON flight_predictions (dest);
CREATE INDEX IF NOT EXISTS ON flight_predictions (carrier);
```

**Diferencias con MongoDB:**
- Cassandra requiere un esquema definido (no es schema-less como MongoDB)
- Se usa un keyspace (equivalente a database en MongoDB)
- Se define una PRIMARY KEY (UUID) para particionamiento
- Se crean índices secundarios para consultas frecuentes
- Los tipos de datos deben especificarse explícitamente

### 5. Código Scala Spark (`MakePrediction.scala`)

#### Imports

**Antes:**
```scala
import com.mongodb.spark._
import org.apache.spark.sql.functions.{concat, from_json, lit, col, to_json, struct}
```

**Después:**
```scala
import org.apache.spark.sql.functions.{concat, from_json, lit, col, to_json, struct, current_timestamp}
```

**Cambio:** Eliminado import de MongoDB, agregado `current_timestamp` para timestamps.

#### Escritura a Base de Datos

**Antes:**
```scala
val dataStreamWriter = finalPredictions
  .writeStream
  .format("mongodb")
  .option("spark.mongodb.connection.uri", "mongodb://mongodb:27017")
  .option("spark.mongodb.database", "agile_data_science")
  .option("checkpointLocation", "/tmp/spark_checkpoint_mongo")
  .option("spark.mongodb.collection", "flight_delay_ml_response")
  .outputMode("append")

val query = dataStreamWriter.start()
```

**Después:**
```scala
def writeToCassandra(batchDF: DataFrame, batchId: Long): Unit = {
  import org.apache.spark.sql.functions.{col, uuid, current_timestamp}
  
  val cassandraDF = batchDF
    .withColumn("id", uuid())
    .withColumn("created_at", current_timestamp())
    .select(
      col("id"),
      col("Origin").alias("origin"),
      col("Dest").alias("dest"),
      col("Carrier").alias("carrier"),
      col("FlightDate").cast("string").alias("flightdate"),
      col("Timestamp").cast("string").alias("dep_time"),
      col("DepDelay").alias("dep_delay"),
      lit(null).cast("string").alias("arr_time"),
      lit(null).cast("double").alias("arr_delay"),
      col("Distance").alias("distance"),
      col("prediction").cast("int"),
      col("created_at")
    )
  
  cassandraDF.write
    .format("org.apache.spark.sql.cassandra")
    .options(Map(
      "keyspace" -> "flight_delays",
      "table" -> "flight_predictions"
    ))
    .mode("append")
    .save()
}

val cassandraStreamWriter = finalPredictions
  .writeStream
  .foreachBatch(writeToCassandra _)
  .option("checkpointLocation", "/tmp/spark_checkpoint_cassandra")
  .outputMode("append")

val query = cassandraStreamWriter.start()
```

**Cambios principales:**
1. **foreachBatch**: Cassandra streaming connector requiere usar `foreachBatch` en lugar de `.format("cassandra")`.
2. **UUID generación**: Se genera un UUID único para cada predicción como PRIMARY KEY.
3. **Timestamp**: Se agrega `created_at` con la fecha actual.
4. **Mapeo de columnas**: Se renombran y castean columnas para coincidir con el esquema de Cassandra.
5. **Configuración**: Se especifica keyspace y tabla en lugar de URI de conexión.

### 6. Aplicación Flask (`predict_flask.py`)

#### Imports y Conexión

**Antes:**
```python
from pymongo import MongoClient
from bson import json_util

client = MongoClient('mongodb:27017')
```

**Después:**
```python
from cassandra.cluster import Cluster
from cassandra.query import dict_factory
import json

cluster = Cluster(['cassandra'])
session = cluster.connect()
session.set_keyspace('flight_delays')
session.row_factory = dict_factory
```

**Cambios:**
- Driver: `pymongo` → `cassandra-driver`
- Conexión: `MongoClient` → `Cluster`
- Host: `mongodb:27017` → `cassandra:9042` (puerto implícito)
- Serialización: `bson.json_util` → `json` estándar
- `row_factory = dict_factory`: Convierte resultados a diccionarios Python

#### Consultas

**Antes (MongoDB):**
```python
prediction = client.agile_data_science.flight_delay_ml_response.find_one(
    {"UUID": unique_id}
)
```

**Después (Cassandra):**
```python
query = "SELECT * FROM flight_predictions WHERE id = %s ALLOW FILTERING"
result = session.execute(query, (unique_id,))
prediction = result.one() if result else None
```

**Cambios:**
- Sintaxis: MongoDB query dict → CQL (Cassandra Query Language)
- `ALLOW FILTERING`: Necesario para filtrar por columna no-partición (menos eficiente)
- Método: `.find_one()` → `.execute()` + `.one()`

**Nota:** En producción, deberías diseñar el esquema para evitar `ALLOW FILTERING`, usando la PRIMARY KEY adecuada.

#### Serialización

**Antes:**
```python
return json_util.dumps(response)
```

**Después:**
```python
return json.dumps(response)
```

**Cambio:** Cassandra no necesita serialización especial como BSON; se usa JSON estándar.

### 7. Entrypoint de Spark (`docker-entrypoint-spark.sh`)

**Antes:**
```bash
echo "Waiting for MongoDB to be ready..."
for i in {1..30}; do
  if nc -z mongodb 27017; then
    echo "MongoDB is ready!"
    break
  fi
  sleep 2
done

/opt/spark/bin/spark-submit \
  --packages org.mongodb.spark:mongo-spark-connector_2.12:10.4.1,... \
  --conf spark.mongodb.write.connection.uri="mongodb://mongodb:27017" \
  --conf spark.mongodb.read.connection.uri="mongodb://mongodb:27017" \
  ...
```

**Después:**
```bash
echo "Waiting for Cassandra to be ready..."
for i in {1..60}; do
  if nc -z cassandra 9042; then
    echo "Cassandra port is open, checking if CQL is ready..."
    sleep 5
    echo "Cassandra is ready!"
    break
  fi
  sleep 2
done

echo "Initializing Cassandra schema..."
sleep 10
cqlsh cassandra -f /opt/spark-apps/init-cassandra.cql || echo "Schema may already exist..."

/opt/spark/bin/spark-submit \
  --packages com.datastax.spark:spark-cassandra-connector_2.12:3.4.1,... \
  --conf spark.cassandra.connection.host=cassandra \
  --conf spark.cassandra.connection.port=9042 \
  ...
```

**Cambios:**
1. **Puerto**: `27017` → `9042`
2. **Tiempo de espera**: Aumentado de 30 a 60 iteraciones (Cassandra tarda más)
3. **Inicialización de esquema**: Se ejecuta `cqlsh` con el script `.cql` antes de iniciar Spark
4. **Paquetes**: `mongo-spark-connector` → `spark-cassandra-connector`
5. **Configuración**: URIs de MongoDB → host y puerto de Cassandra

### 8. Dockerfile de Spark (`Dockerfile.spark`)

**Antes:**
```dockerfile
RUN apt-get update && apt-get install -y netcat && rm -rf /var/lib/apt/lists/*
```

**Después:**
```dockerfile
RUN apt-get update && \
    apt-get install -y netcat python3-pip && \
    pip3 install cqlsh && \
    rm -rf /var/lib/apt/lists/*

COPY init-cassandra.cql /opt/spark-apps/
```

**Cambios:**
1. **cqlsh instalado**: Necesario para ejecutar el script de inicialización de Cassandra
2. **Script de init copiado**: `init-cassandra.cql` se copia al contenedor

## Diferencias Clave: MongoDB vs Cassandra

| Aspecto | MongoDB | Cassandra |
|---------|---------|-----------|
| **Modelo de datos** | Document-oriented (JSON/BSON) | Wide-column store |
| **Esquema** | Schema-less (flexible) | Schema requerido |
| **Consultas** | Query language rico y flexible | CQL (similar a SQL pero limitado) |
| **Distribución** | Master-slave replication | Peer-to-peer (sin maestro) |
| **Consistencia** | CP (Consistency, Partition tolerance) | AP (Availability, Partition tolerance) |
| **Escrituras** | Buenas, pero más lentas en clusters grandes | Optimizadas, muy rápidas |
| **Lecturas** | Muy rápidas con índices | Dependen del diseño del esquema |
| **Joins** | Lookup pipelines en agregaciones | No soportados (desnormalización necesaria) |
| **Tiempo de inicio** | ~5-10 segundos | ~30-60 segundos |

## Impacto en el Sistema

### Ventajas
1. ✅ **Mayor rendimiento de escritura**: Ideal para streaming continuo de Spark
2. ✅ **Mejor escalabilidad horizontal**: Fácil agregar más nodos
3. ✅ **Mayor disponibilidad**: Sin punto único de fallo
4. ✅ **Mejor para time-series**: Diseñado para datos con timestamp

### Desventajas
1. ❌ **Consultas menos flexibles**: CQL es más limitado que MongoDB queries
2. ❌ **Requiere diseño de esquema**: No se puede cambiar estructura fácilmente
3. ❌ **Tiempo de inicio más lento**: Cassandra tarda más en arrancar
4. ❌ **Curva de aprendizaje**: CQL y modelo de datos diferente

## Comandos Útiles

### Conectar a Cassandra
```bash
docker exec -it <cassandra-container> cqlsh
```

### Ver datos en Cassandra
```cql
USE flight_delays;
SELECT * FROM flight_predictions LIMIT 10;
SELECT COUNT(*) FROM flight_predictions;
```

### Ver logs de Cassandra
```bash
docker logs <cassandra-container>
```

### Verificar estado del cluster
```bash
docker exec -it <cassandra-container> nodetool status
```

## Despliegue

El despliegue sigue siendo el mismo:

```bash
# Construir imágenes
docker compose build

# Iniciar todos los servicios
docker compose up -d

# Ver logs
docker compose logs -f

# Detener servicios
docker compose down

# Limpiar volúmenes (CUIDADO: borra datos)
docker compose down -v
```

## Consideraciones de Producción

Para un entorno de producción con Cassandra, considera:

1. **Replication Factor**: Cambiar de `1` a `3` en el keyspace para redundancia
2. **Múltiples nodos**: Desplegar cluster de 3+ nodos Cassandra
3. **Consistencia**: Ajustar niveles de consistencia según necesidades
4. **Monitoring**: Usar DataStax OpsCenter o Prometheus + Grafana
5. **Backups**: Configurar snapshots automáticos
6. **Tuning**: Ajustar memoria, compactación, y cache según carga

## Migración de Datos

Si tienes datos existentes en MongoDB, puedes migrarlos usando:

```python
from pymongo import MongoClient
from cassandra.cluster import Cluster
import uuid

# Conectar a MongoDB
mongo_client = MongoClient('mongodb:27017')
mongo_db = mongo_client.agile_data_science

# Conectar a Cassandra
cassandra_cluster = Cluster(['cassandra'])
cassandra_session = cassandra_cluster.connect('flight_delays')

# Preparar insert statement
insert_stmt = cassandra_session.prepare("""
    INSERT INTO flight_predictions 
    (id, origin, dest, carrier, flightdate, dep_time, dep_delay, 
     arr_time, arr_delay, distance, prediction, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, toTimestamp(now()))
""")

# Migrar datos
for doc in mongo_db.flight_delay_ml_response.find():
    cassandra_session.execute(insert_stmt, (
        uuid.uuid4(),
        doc.get('Origin'),
        doc.get('Dest'),
        doc.get('Carrier'),
        str(doc.get('FlightDate')),
        str(doc.get('Timestamp')),
        doc.get('DepDelay'),
        None,  # arr_time
        None,  # arr_delay
        doc.get('Distance'),
        int(doc.get('prediction', 0)),
    ))

print("Migration complete!")
```

## Troubleshooting

### Cassandra no arranca
- Verifica que tienes suficiente memoria (mínimo 2GB RAM)
- Aumenta `start_period` en el healthcheck si sigue fallando
- Revisa logs: `docker logs <cassandra-container>`

### Schema ya existe
- Normal en reinicios, el mensaje "Schema may already exist" es esperado
- Para resetear: `docker compose down -v` (borra datos)

### Queries lentas con ALLOW FILTERING
- Rediseña el esquema para usar la PRIMARY KEY en las consultas
- Considera crear tablas desnormalizadas para diferentes patrones de consulta

### Conexión rechazada desde Flask/Spark
- Verifica que Cassandra haya terminado de iniciar (puede tardar 60+ segundos)
- Revisa el healthcheck: `docker inspect <cassandra-container>`
- Usa `docker compose logs cassandra` para ver si hay errores

## Referencias

- [Apache Cassandra Documentation](https://cassandra.apache.org/doc/latest/)
- [DataStax Spark Cassandra Connector](https://github.com/datastax/spark-cassandra-connector)
- [Python Driver for Cassandra](https://docs.datastax.com/en/developer/python-driver/)
- [CQL (Cassandra Query Language)](https://cassandra.apache.org/doc/latest/cassandra/cql/)
