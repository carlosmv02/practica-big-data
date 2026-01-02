# Funcionamiento del Sistema de Predicciones con WebSocket

## Descripción General

Este documento explica el funcionamiento completo del sistema de predicción de retrasos de vuelos, enfocándose en cómo se implementó la comunicación en tiempo real mediante WebSocket (Socket.IO) para eliminar el polling tradicional.

## Arquitectura del Sistema

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│  Navegador  │─────▶│   Flask     │─────▶│    Kafka    │─────▶│    Spark    │
│  (Cliente)  │      │  (Servidor) │      │   (Broker)  │      │ Streaming   │
└─────────────┘      └─────────────┘      └─────────────┘      └─────────────┘
       ▲                    │                     ▲                     │
       │                    ▼                     │                     ▼
       │             ┌─────────────┐              │              ┌─────────────┐
       │             │   Socket.IO │              │              │   MongoDB   │
       │             │   Consumer  │              │              │             │
       │             └─────────────┘              │              └─────────────┘
       │                    │                     │                     │
       └────────────────────┴─────────────────────┴─────────────────────┘
                    (Respuesta en tiempo real)
```

## Componentes del Sistema

### 1. Cliente Web (Navegador)

**Archivo**: `resources/web/static/flight_delay_predict_socket.js`

**Responsabilidades**:
- Capturar el formulario de predicción del usuario
- Enviar petición POST a Flask con los datos del vuelo
- Establecer conexión WebSocket con el servidor Flask
- Unirse a una "sala" privada identificada por UUID
- Escuchar eventos de predicción y mostrar resultados

**Flujo de ejecución**:

1. **Envío del formulario**:
```javascript
// El usuario rellena el formulario y pulsa Submit
$.post(url, $("#flight_delay_classification").serialize())
```

2. **Recepción del UUID**:
```javascript
// Flask responde con: {status: "OK", id: "uuid-aquí"}
var response = JSON.parse(data);
```

3. **Conexión Socket.IO**:
```javascript
// Crear conexión WebSocket
var socket = io({
    reconnection: true,
    transports: ['websocket', 'polling']
});
```

4. **Unirse a sala privada**:
```javascript
// Cuando se conecta, se une a su sala UUID
socket.on('connect', function() {
    socket.emit('join', {uuid: response.id});
});
```

5. **Escuchar predicción**:
```javascript
// Espera el evento 'prediction' con el resultado
socket.on('prediction', function(msg) {
    if(msg.UUID == response.id) {
        renderPage(msg);  // Muestra el resultado
        socket.disconnect();
    }
});
```

### 2. Servidor Flask

**Archivo**: `resources/web/predict_flask.py`

**Responsabilidades**:
- Recibir peticiones HTTP del cliente
- Publicar peticiones en Kafka topic `flight-delay-ml-request`
- Consumir respuestas de Kafka topic `flight-delay-ml-response`
- Gestionar conexiones Socket.IO y salas por UUID
- Emitir predicciones a los clientes correspondientes

**Componentes clave**:

#### A. Endpoint de predicción
```python
@app.route("/flights/delays/predict/classify_realtime", methods=['POST'])
def classify_flight_delays_realtime():
    # 1. Procesar datos del formulario
    # 2. Calcular distancia y características derivadas
    # 3. Generar UUID único para esta petición
    unique_id = str(uuid.uuid4())
    prediction_features['UUID'] = unique_id
    
    # 4. Publicar en Kafka para que Spark lo procese
    message_bytes = json.dumps(prediction_features).encode()
    producer.send(PREDICTION_TOPIC, message_bytes)
    
    # 5. Devolver UUID al cliente
    return json_util.dumps({"status": "OK", "id": unique_id})
```

#### B. Handler Socket.IO para unirse a sala
```python
@socketio.on('join')
def on_join(data):
    uuid = data.get('uuid')
    if uuid:
        join_room(uuid)  # Cliente se une a sala privada
        
        # Si la predicción ya llegó, emitirla inmediatamente
        cached = predictions_cache.get(uuid)
        if cached:
            socketio.emit('prediction', cached, room=uuid)
```

#### C. Consumidor Kafka en background
```python
def consume_prediction_results():
    """Thread separado que consume predicciones de Kafka"""
    consumer = KafkaConsumer(
        'flight-delay-ml-response',
        bootstrap_servers=['localhost:9092'],
        group_id='flask-prediction-consumer',
        value_deserializer=lambda m: json.loads(m.decode('utf-8'))
    )
    
    for message in consumer:
        message_object = message.value
        uuid = message_object.get('UUID')
        
        if uuid:
            # Guardar en caché local
            predictions_cache[uuid] = message_object
            
            # Emitir por Socket.IO a la sala correspondiente
            socketio.emit('prediction', message_object, room=uuid)
```

**Estructuras de datos**:
- `predictions_cache`: Diccionario {UUID: predicción} para almacenar resultados
- `prediction_events`: Diccionario de eventos de threading (para sincronización)

#### D. Endpoint de respuesta (fallback)
```python
@app.route("/flights/delays/predict/classify_realtime/response/<unique_id>")
def classify_flight_delays_realtime_response(unique_id):
    # Revisar caché primero
    cached = predictions_cache.get(unique_id)
    if cached:
        return json_util.dumps({"status": "OK", "prediction": cached})
    
    # Fallback: consultar MongoDB
    prediction = client.agile_data_science.flight_delay_ml_response.find_one(
        {"UUID": unique_id}
    )
    
    response = {"status": "WAIT", "id": unique_id}
    if prediction:
        response["status"] = "OK"
        response["prediction"] = prediction
    
    return json_util.dumps(response)
```

### 3. Kafka

**Topics utilizados**:

#### A. `flight-delay-ml-request`
- **Productor**: Flask (servidor web)
- **Consumidor**: Spark Streaming
- **Contenido**: Datos del vuelo + UUID
```json
{
  "UUID": "da6647c4-b8d1-4d17-bc28-6f7ad819393d",
  "Origin": "ATL",
  "Dest": "SFO",
  "Carrier": "AA",
  "FlightDate": "2016-12-25",
  "DepDelay": 5.0,
  "Distance": 2139.0,
  "DayOfMonth": 25,
  "DayOfWeek": 6,
  "DayOfYear": 360,
  "Timestamp": "2026-01-02T11:05:43.860+01:00"
}
```

#### B. `flight-delay-ml-response`
- **Productor**: Spark Streaming
- **Consumidor**: Flask (consumer en background)
- **Contenido**: Predicción + datos originales
```json
{
  "UUID": "da6647c4-b8d1-4d17-bc28-6f7ad819393d",
  "Origin": "ATL",
  "Dest": "SFO",
  "Carrier": "AA",
  "Route": "ATL-SFO",
  "Prediction": 2.0,
  "...": "otros campos..."
}
```

### 4. Spark Streaming

**Archivo**: `flight_prediction/src/main/scala/es/upm/dit/ging/predictor/MakePrediction.scala`

**Responsabilidades**:
- Consumir peticiones de `flight-delay-ml-request`
- Aplicar transformaciones y modelo de ML
- Guardar predicción en MongoDB
- Publicar predicción en `flight-delay-ml-response`

**Flujo de procesamiento**:

1. **Consumir de Kafka**:
```scala
val df = spark
  .readStream
  .format("kafka")
  .option("kafka.bootstrap.servers", "localhost:9092")
  .option("subscribe", "flight-delay-ml-request")
  .load()
```

2. **Parsear JSON y aplicar transformaciones**:
```scala
// Deserializar JSON
val flightNestedDf = flightJsonDf.select(from_json($"value", flightSchema).as("flight"))

// Crear columna Route
val predictionRequestsWithRoute = flightFlattenedDf.withColumn("Route",
  concat(flightFlattenedDf("Origin"), lit('-'), flightFlattenedDf("Dest"))
)

// Aplicar StringIndexers
for (column <- columns) {
  df = stringIndexerModels(column).transform(df)
}

// Vectorizar features
val vectorizedFeatures = vectorAssembler.transform(df)
```

3. **Aplicar modelo de predicción**:
```scala
val predictions = rfc.transform(finalVectorizedFeatures)
val finalPredictions = predictions.drop("Features_vec").drop("indices")
  .drop("values").drop("rawPrediction").drop("probability")
```

4. **Guardar en MongoDB**:
```scala
val dataStreamWriter = finalPredictions
  .writeStream
  .format("mongodb")
  .option("spark.mongodb.connection.uri", "mongodb://127.0.0.1:27017")
  .option("spark.mongodb.database", "agile_data_science")
  .option("spark.mongodb.collection", "flight_delay_ml_response")
  .option("checkpointLocation", "/tmp/spark_checkpoint_mongo")
  .outputMode("append")
  .start()
```

5. **Publicar en Kafka**:
```scala
// Serializar toda la fila como JSON
val kafkaOutput = finalPredictions.selectExpr("to_json(struct(*)) AS value")

val kafkaWriter = kafkaOutput.writeStream
  .format("kafka")
  .option("kafka.bootstrap.servers", "localhost:9092")
  .option("topic", "flight-delay-ml-response")
  .option("checkpointLocation", "/tmp/spark_checkpoint_kafka")
  .outputMode("append")
  .start()
```

### 5. MongoDB

**Colección**: `agile_data_science.flight_delay_ml_response`

**Propósito**:
- Persistencia de todas las predicciones
- Fallback si Socket.IO falla
- Histórico de predicciones para análisis

## Funcionamiento del Socket (WebSocket)

### ¿Qué es Socket.IO?

Socket.IO es una librería que permite comunicación bidireccional en tiempo real entre cliente y servidor. Funciona sobre WebSocket pero con fallback automático a long-polling si WebSocket no está disponible.

### Ventajas sobre Polling tradicional

**Antes (Polling)**:
```javascript
// Cliente pregunta cada segundo: "¿ya está listo?"
setInterval(function() {
    $.get('/response/' + uuid, function(data) {
        if(data.status == "OK") {
            // Mostrar resultado
        }
    });
}, 1000);  // Cada 1 segundo
```

**Problemas del polling**:
- ❌ Múltiples peticiones HTTP innecesarias
- ❌ Latencia de hasta 1 segundo
- ❌ Carga en servidor y red
- ❌ No escalable

**Ahora (WebSocket)**:
```javascript
// Cliente espera pasivamente, servidor notifica cuando está listo
socket.on('prediction', function(msg) {
    // Mostrar resultado inmediatamente
});
```

**Ventajas del WebSocket**:
- ✅ Una sola conexión persistente
- ✅ Notificación instantánea (latencia < 50ms)
- ✅ Menos carga en servidor y red
- ✅ Escalable a miles de clientes

### Concepto de "Salas" (Rooms)

Socket.IO implementa el patrón de **salas privadas**:

```
┌─────────────────────────────────────────┐
│           Servidor Flask                │
│                                         │
│  Sala UUID-1     Sala UUID-2           │
│  ┌─────────┐     ┌─────────┐           │
│  │Cliente A│     │Cliente B│           │
│  └─────────┘     └─────────┘           │
│       ▲               ▲                 │
│       │               │                 │
│  emit(room=UUID-1)  emit(room=UUID-2)  │
└───────┼───────────────┼─────────────────┘
        │               │
        ▼               ▼
   Solo ve su      Solo ve su
   predicción      predicción
```

**Funcionamiento**:
1. Cliente hace POST y recibe `UUID-123`
2. Cliente hace `socket.emit('join', {uuid: 'UUID-123'})`
3. Servidor ejecuta `join_room('UUID-123')` para ese cliente
4. Cuando llega la predicción con `UUID-123`, servidor hace:
   ```python
   socketio.emit('prediction', data, room='UUID-123')
   ```
5. **Solo el cliente en esa sala recibe el mensaje**

## Flujo Completo de una Predicción

### Paso a Paso

```
Tiempo  Cliente              Flask               Kafka               Spark               MongoDB
  │
  1     [Submit form]
  │         │
  2         │─────POST────────▶
  │         │                  │
  3         │                  │──publish─────▶
  │         │                  │               (request)
  4         │◀────UUID────────│
  │         │                  │
  5     [Connect Socket.IO]    │
  │         │                  │
  6     [emit: join(UUID)]     │
  │         │                  │
  7         │──join room(UUID)─│
  │         │                  │
  8         │                  │                   │────consume────▶
  │         │                  │                   │
  9         │                  │                   │──transform──▶
  │         │                  │                   │
 10         │                  │                   │──predict────▶
  │         │                  │                   │
 11         │                  │                   │──save───────────────────────▶
  │         │                  │                   │                        [insert doc]
 12         │                  │                   │──publish────▶
  │         │                  │                                (response)
 13         │                  │◀───consume──────│
  │         │                  │                  │
 14         │                  │──cache[UUID]────│
  │         │                  │                  │
 15         │                  │──emit(room)─────│
  │         │                  │                  │
 16     [on: prediction]◀──────│
  │         │                  │
 17     [Show result]
  │         │
 18     [disconnect]
```

### Descripción de cada paso

1. **Usuario envía formulario** con datos del vuelo
2. **Flask recibe POST** en `/flights/delays/predict/classify_realtime`
3. **Flask publica en Kafka** topic `flight-delay-ml-request` con UUID único
4. **Flask devuelve UUID** al cliente: `{status: "OK", id: "UUID-123"}`
5. **Cliente conecta Socket.IO** al servidor Flask
6. **Cliente emite evento 'join'** con su UUID
7. **Flask une cliente a sala privada** `room=UUID-123`
8. **Spark consume mensaje** de Kafka `flight-delay-ml-request`
9. **Spark aplica transformaciones** (indexers, vectorizers)
10. **Spark ejecuta predicción** usando RandomForest
11. **Spark guarda en MongoDB** colección `flight_delay_ml_response`
12. **Spark publica resultado** en Kafka `flight-delay-ml-response`
13. **Consumer de Flask recibe** mensaje de Kafka
14. **Flask almacena en caché** local: `predictions_cache[UUID] = data`
15. **Flask emite por Socket.IO** solo a sala `room=UUID-123`
16. **Cliente recibe evento 'prediction'** con los datos
17. **Cliente muestra resultado** en pantalla
18. **Cliente desconecta Socket.IO**

## Código Relevante

### Cliente (JavaScript)

**Conexión y Join**:
```javascript
var socket = io({
    reconnection: true,
    reconnectionDelay: 1000,
    transports: ['websocket', 'polling']
});

socket.on('connect', function() {
    console.log("[Socket] Connected to server");
    socket.emit('join', {uuid: response.id});
});

socket.on('prediction', function(msg) {
    if(msg && msg.UUID && msg.UUID == response.id) {
        renderPage(msg);
        socket.disconnect();
    }
});
```

### Servidor (Python)

**Inicialización Socket.IO**:
```python
from flask_socketio import SocketIO, join_room

socketio = SocketIO(app, cors_allowed_origins='*')
predictions_cache = {}
```

**Handler de join**:
```python
@socketio.on('join')
def on_join(data):
    uuid = data.get('uuid')
    if uuid:
        join_room(uuid)
        # Emit inmediato si ya está en caché
        cached = predictions_cache.get(uuid)
        if cached:
            socketio.emit('prediction', cached, room=uuid)
```

**Consumer Kafka**:
```python
def consume_prediction_results():
    consumer = KafkaConsumer(
        'flight-delay-ml-response',
        bootstrap_servers=['localhost:9092'],
        group_id='flask-prediction-consumer',
        value_deserializer=lambda m: json.loads(m.decode('utf-8'))
    )
    
    for message in consumer:
        message_object = message.value
        uuid = message_object.get('UUID')
        
        if uuid:
            predictions_cache[uuid] = message_object
            socketio.emit('prediction', message_object, room=uuid)

# Thread daemon
consumer_thread = threading.Thread(target=consume_prediction_results)
consumer_thread.daemon = True
consumer_thread.start()
```

**Inicio de servidor**:
```python
if __name__ == "__main__":
    socketio.run(app, debug=True, host='0.0.0.0', port=5001)
```

## Verificación del Funcionamiento

### 1. Logs esperados en Flask

```
[Flask] Starting Kafka consumer thread...
[Kafka Consumer] Successfully connected to Kafka broker
(11038) wsgi starting up on http://0.0.0.0:5001
```

Cuando llega una petición:
```
127.0.0.1 - - [02/Jan/2026 11:05:43] "POST /flights/delays/predict/classify_realtime HTTP/1.1" 200
[Kafka Consumer] Received message: {'UUID': '...', 'Prediction': 2.0, ...}
[Kafka Consumer] Emitting to room: da6647c4-b8d1-4d17-bc28-6f7ad819393d
```

### 2. Consola del navegador (F12)

```
[Client] Received response from server: {status: "OK", id: "..."}
[Socket] Connected to server, joining room: ...
[Socket] Received prediction event: {...}
[Client] UUID matches, rendering page
[renderPage] Display message: Slightly Late (0-30 Minute Delay)
```

### 3. Verificar en MongoDB

```bash
docker exec -it mongo bash
mongosh
use agile_data_science
db.flight_delay_ml_response.find().sort({_id:-1}).limit(1).pretty()
```

## Troubleshooting

### Problema: Cliente no se conecta a Socket.IO

**Síntoma**: Error 400 en `/socket.io/socket.io.js`

**Solución**:
- Verificar que `flask-socketio==5.3.5` está instalado
- Verificar que el HTML carga la CDN correcta:
  ```html
  <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
  ```
- Hacer hard refresh (Ctrl+Shift+R)

### Problema: Predicción no llega al cliente

**Síntoma**: Se queda en "Processing..."

**Diagnóstico**:
1. Verificar que Flask recibe el mensaje de Kafka:
   - Buscar `[Kafka Consumer] Received message` en logs
2. Verificar que Flask emite a la sala:
   - Buscar `[Kafka Consumer] Emitting to room` en logs
3. Verificar que el cliente está conectado:
   - Ver en consola del navegador `[Socket] Connected`

**Posibles causas**:
- Spark no publica en Kafka (errores `AdminClient disconnected`)
- UUID no coincide entre petición y respuesta
- Cliente no se unió a la sala antes de que llegara el mensaje (solucionado con caché + emit en join)

### Problema: Múltiples consumidores Kafka

**Síntoma**: Logs muestran "2 members" en el grupo

**Causa**: Flask se reinicia con debug=True y crea 2 procesos

**Solución**: Normal en desarrollo, en producción usar `debug=False`

## Resumen de Mejoras vs Sistema Anterior

| Aspecto | Sistema Anterior (Polling) | Sistema Nuevo (WebSocket) |
|---------|---------------------------|---------------------------|
| **Comunicación** | Cliente pregunta cada 1s | Servidor notifica al instante |
| **Latencia** | 0-1000ms (promedio 500ms) | < 50ms |
| **Peticiones HTTP** | N peticiones hasta recibir | 1 petición inicial + WebSocket |
| **Escalabilidad** | Limitada (carga por polling) | Alta (conexiones persistentes) |
| **UX** | Puede parecer lento | Respuesta inmediata |
| **Complejidad** | Baja | Media (requiere Socket.IO) |
| **Compatibilidad** | Universal | Requiere WebSocket o fallback |

## Conclusión

El sistema implementado elimina completamente el polling mediante Socket.IO, logrando:
- ✅ Comunicación en tiempo real bidireccional
- ✅ Notificaciones instantáneas de predicciones
- ✅ Salas privadas por UUID para múltiples usuarios
- ✅ Persistencia en MongoDB mantenida
- ✅ Arquitectura desacoplada con Kafka
- ✅ Escalable y eficiente
