# Instrucciones de ejecución actualizadas (WebSocket + Kafka)

Este documento recoge los pasos actualizados para ejecutar el sistema de predicción que ahora publica los resultados en Kafka y los reenvía al cliente por WebSocket (Flask-SocketIO). Mantiene además la escritura en MongoDB desde el job Spark.

Resumen de cambios relevantes:
- El job Spark (`MakePrediction`) ahora además de guardar en Mongo escribe el resultado en el topic Kafka `flight-delay-ml-response`.
- El servidor Flask (`resources/web/predict_flask.py`) incorpora `Flask-SocketIO` y un consumidor Kafka en background que escucha `flight-delay-ml-response` y reemite los mensajes por Socket.IO al cliente (se usa `UUID` como room id).
- La página cliente `/flights/delays/predict_kafka` ya no hace polling; usa Socket.IO cliente (`/static/flight_delay_predict_socket.js`).

Requisitos previos
- Java (JDK 17 según tu `JAVA_HOME` configurado).
- Spark (ruta en `SPARK_HOME`).
- Kafka (local en `localhost:9092` según los comandos aquí).
- Docker (para MongoDB si lo arrancas con docker).
- Virtualenv de Python (se indica más abajo).

1) Preparar entorno Python

```bash
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
```

Nota: `requirements.txt` fue actualizado para incluir `flask-socketio` y `eventlet`. `eventlet` es recomendado para que `Flask-SocketIO` soporte WebSockets eficientemente.

2) Levantar MongoDB

Si usabas Docker:

```bash
docker start mongo
```

3) Variables de entorno (ejemplo)

```bash
export JAVA_HOME=$(sdk home java 17.0.14-amzn)
export SPARK_HOME=/home/ibdn/.sdkman/candidates/spark/3.5.3
export PROJECT_HOME=/home/ibdn/practica_creativa
```

4) Kafka (KRaft mode) — iniciar broker y crear topics

Ve a tu carpeta de Kafka (ej. `/kafka_2.12-3.9.0`) y, si aún no lo has hecho, formatea el storage y arranca el servidor:

```bash
cd /kafka_2.12-3.9.0
KAFKA_CLUSTER_ID="$(bin/kafka-storage.sh random-uuid)"
bin/kafka-storage.sh format -t "$KAFKA_CLUSTER_ID" -c config/kraft/server.properties
# Inicia el broker
bin/kafka-server-start.sh config/kraft/server.properties
```

Crear los topics necesarios (si no existen):

```bash
bin/kafka-topics.sh --create --bootstrap-server localhost:9092 --topic flight-delay-ml-request --partitions 1
bin/kafka-topics.sh --create --bootstrap-server localhost:9092 --topic flight-delay-ml-response --partitions 1
```

Importante: el `MakePrediction` de Spark escribe en `flight-delay-ml-response`, así que asegúrate de crear ese topic antes de lanzar el job o que Kafka lo permita crear automáticamente.

5) Entrenamiento del modelo (si aplica)

Activa el virtualenv y ejecuta el script de entrenamiento (igual que antes):

```bash
source env/bin/activate
python3 resources/train_spark_mllib_model.py .
```

6) Compilar / empaquetar el job Spark (si no tienes ya el JAR)

```bash
cd flight_prediction
# abre sbt e instala dependencias y genera jar
sbt
  compile
  package
# Sal del prompt sbt con Ctrl+D o exit
```

7) Ejecutar el predictor Spark (streaming)

Este job ahora escribe en Mongo y además publica cada predicción en Kafka `flight-delay-ml-response`.

Ejecuta con `spark-submit` incluyendo los paquetes para Mongo y para Kafka:

```bash
spark-submit \
  --packages org.mongodb.spark:mongo-spark-connector_2.12:10.4.1,org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.3 \
  --class "es.upm.dit.ging.predictor.MakePrediction" \
  target/scala-2.12/flight_prediction_2.12-0.1.jar
```

8) Iniciar la aplicación Flask (con Socket.IO)

Asegúrate de que el entorno Python tiene `flask-socketio` y `eventlet` instalados (paso 1). Luego:

```bash
cd /home/ibdn/practica_creativa
source env/bin/activate
export PROJECT_HOME=/home/ibdn/practica_creativa
python3 resources/web/predict_flask.py
```

El servidor escucha por defecto en `0.0.0.0:5001`.

Notas:
- `socketio.run(...)` detectará y usará `eventlet` si está instalado; si usas otro async worker (gevent, threading), puedes adaptar la instalación.
- El módulo Flask inicia un hilo demonio con un `KafkaConsumer` que escucha `flight-delay-ml-response` y hace `socketio.emit('prediction', message, room=UUID)`.

9) Probar la interfaz Web

Abre:

```
http://localhost:5001/flights/delays/predict_kafka
```

- Rellena el formulario y pulsa Submit.
- El navegador hará POST (igual que antes), recibirá `{status: 'OK', id: '<UUID>'}`.
- El JS cliente se conectará vía Socket.IO y se unirá a la sala con ese `UUID`.
- Cuando el job Spark publique la predicción en `flight-delay-ml-response` (y el consumidor de Flask la reciba), Flask reemitirá por Socket.IO la predicción solo a la sala correspondiente; el cliente mostrará la predicción sin polling.

10) Comprobación en MongoDB (sigue guardando ahí)

Si quieres confirmar que Spark sigue guardando resultados en MongoDB:

```bash
docker exec -it mongo bash
mongosh
use agile_data_science
db.flight_delay_ml_response.find().pretty()
```

11) Notas útiles / troubleshooting

- Si el cliente no recibe el evento `prediction`:
  - Verifica logs del job Spark: debe escribir en el topic `flight-delay-ml-response` y/o mostrar registros de publicación Kafka.
  - Verifica que el consumidor Kafka en Flask está arrancado (mira la salida al iniciar `predict_flask.py` para mensajes de error al crear `KafkaConsumer`).
  - Asegúrate de que `socket.io` cliente carga `/socket.io/socket.io.js`. `Flask-SocketIO` lo sirve automáticamente cuando se usa `socketio.run()`.
- Si tienes problemas con WebSockets en el entorno, prueba a forzar el transporte a polling temporalmente desde cliente con `io({transports: ['polling']})` para diagnosticar.
- Si deseas que Flask también escriba la predicción en Mongo (además de Spark), el consumer en `predict_flask.py` puede insertar/upsert en la colección; actualmente dejamos la persistencia en Spark por simplicidad.

12) Archivos importantes modificados

- `flight_prediction/src/main/scala/es/upm/dit/ging/predictor/MakePrediction.scala` — ahora publica a Kafka topic `flight-delay-ml-response` además de escribir a Mongo.
- `resources/web/predict_flask.py` — añadido `Flask-SocketIO` y consumer Kafka en background; usa `socketio.run(...)`.
- `resources/web/templates/flight_delays_predict_kafka.html` — ahora incluye el cliente Socket.IO y el nuevo JS.
- `resources/web/static/flight_delay_predict_socket.js` — nuevo JS que sustituye al polling por socket.
- `requirements.txt` — se añadió `flask-socketio` y `eventlet`.

¿Quieres que también:
- haga que Flask almacene la respuesta en Mongo al recibirla del topic (upsert)?
- prepare un pequeño script de prueba que publique un mensaje de ejemplo en `flight-delay-ml-response` para verificar el flujo SocketIO sin ejecutar el job Spark?

---

Archivo creado: `SOCKET_INSTRUCTIONS.md`

He terminado esta entrega; dime si quieres que ejecute alguna prueba automática o añada el script de prueba Kafka mencionado.
