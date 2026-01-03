# Dockerización del Sistema de Predicción de Vuelos

Este documento describe cómo desplegar el sistema completo utilizando Docker Compose.

## Arquitectura de servicios

El sistema está compuesto por 6 contenedores:

1. **mongodb** - Base de datos para persistir predicciones
2. **kafka** - Sistema de mensajería (modo KRaft, sin Zookeeper)
3. **spark-master** - Nodo maestro de Spark
4. **spark-worker-1** - Worker de Spark (ejecuta el job de predicción)
5. **spark-worker-2** - Worker de Spark (redundancia)
6. **flask-app** - Aplicación web con Socket.IO

## Requisitos previos

1. Docker y Docker Compose instalados
2. Compilar el proyecto Spark antes de construir la imagen:
   ```bash
   cd flight_prediction
   sbt package
   ```
3. Entrenar el modelo (si no existe):
   ```bash
   source env/bin/activate
   python3 resources/train_spark_mllib_model.py .
   ```

## Despliegue

Para levantar todo el escenario:

```bash
docker-compose up -d
```

Para verificar el estado de los servicios:

```bash
docker-compose ps
```

Para ver los logs:

```bash
# Todos los servicios
docker-compose logs -f

# Un servicio específico
docker-compose logs -f flask-app
docker-compose logs -f spark-worker-1
```

## Acceso a los servicios

- **Aplicación Web**: http://localhost:5001
- **Spark Master UI**: http://localhost:8080
- **MongoDB**: localhost:27017
- **Kafka**: localhost:9092

## Flujo de predicción

1. El usuario rellena el formulario en http://localhost:5001/flights/delays/predict_kafka
2. Flask envía la solicitud al topic Kafka `flight-delay-ml-request`
3. Spark Streaming (en los workers) consume el mensaje, aplica el modelo y:
   - Guarda el resultado en MongoDB
   - Publica el resultado en el topic `flight-delay-ml-response`
4. Flask consume el resultado y lo envía al cliente vía Socket.IO
5. El cliente muestra la predicción sin polling

## Comandos útiles

### Detener los servicios
```bash
docker-compose down
```

### Detener y eliminar volúmenes (limpieza completa)
```bash
docker-compose down -v
```

### Reconstruir las imágenes después de cambios
```bash
docker-compose build --no-cache
docker-compose up -d
```

### Acceder a un contenedor
```bash
docker exec -it practica-flask bash
docker exec -it practica-mongodb mongosh
```

### Ver logs de Spark en tiempo real
```bash
docker-compose logs -f spark-worker-1 spark-worker-2
```

## Troubleshooting

### Los workers no se conectan a Spark Master
- Verificar que el master esté corriendo: `docker-compose ps spark-master`
- Revisar logs: `docker-compose logs spark-master`

### Kafka no está disponible
- Esperar unos segundos, Kafka tarda en inicializarse
- Verificar: `docker-compose logs kafka`

### No se reciben predicciones en el navegador
1. Verificar que los workers están ejecutando el job:
   ```bash
   docker-compose logs spark-worker-1 | grep "Flight predictor"
   ```
2. Verificar que Flask está consumiendo Kafka:
   ```bash
   docker-compose logs flask-app | grep "Kafka Consumer"
   ```
3. Verificar que Spark está publicando en Kafka:
   ```bash
   docker-compose logs spark-worker-1 | grep "Kafka writer"
   ```

### Reconstruir después de cambios en el código

Si modificas el código Scala:
```bash
cd flight_prediction
sbt package
docker-compose build spark-worker-1 spark-worker-2
docker-compose up -d spark-worker-1 spark-worker-2
```

Si modificas el código Python:
```bash
docker-compose build flask-app
docker-compose up -d flask-app
```

## Notas importantes

- Los dos workers Spark proporcionan redundancia pero solo uno ejecutará el job de Streaming (Spark lo asigna automáticamente)
- Los checkpoints de Spark se guardan dentro de los contenedores en `/tmp/spark_checkpoint_*`
- Los datos de MongoDB y Kafka persisten en volúmenes Docker
- Si cambias el código, debes recompilar el JAR y reconstruir las imágenes

## Red y comunicación

Todos los servicios están en la red `prediction-network`. Las conexiones internas usan los nombres de servicio:
- `kafka:9092` para Kafka
- `mongodb:27017` para MongoDB  
- `spark-master:7077` para el master de Spark

Las conexiones desde el host usan `localhost` con los puertos mapeados.
