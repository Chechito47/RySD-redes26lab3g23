## Decisiones de diseño

### Inicialización de `cwnd`

Se inicializó `cwnd = 1.0` en `TransportTx::initialize()`. Esto imita el arranque concervador de TCP (*slow start*): El transmisor comienza permitiendo un unico paquete en vuelo y crece a partitr del primer ACK recibido. La alternativa de iniciar con un valor alto generaría una ráfaga inicial que podría saturar los buffers antes de que llegue cualquier feedback, particularmente peligroso para `gi = 0.1s` donde la tasa de generación ya supera la capacidad del enlace.

`rwnd`se iniciaizo en `10`como estimación optimista del espacio disponible en el receptor hasta recibir el primer ACK real. `inFlight` se inicializó en `0`.

---

### Crecimiento de `cwnd` sin congestión

Cuando llega un ACK sin señal ECN, se aplica:
 
```cpp
cwnd += 1.0 / cwnd;
```

Esto replica el comportamiento de TCP en fase *congestion avoidance*: el crecimiento es inversamente proporcional al valor actual de `cwnd`. Para `cwnd` cercano a 1 el crecimiento es casi lineal; para valores grandes se vuelve muy lento y gradual.

**¿Qué se simplificó con respecto a TCP?:** TCP real arranca con una fase *slow start* exponencial  (`cwnd` se duplica por RTT) hasta alcanzar un umbral (*ssthresh*), y recién ahí pasa a *congestion avoidance* lineal. En nuestra implementación no existe esa fase exponencial ni el umbral: el crecimiento es siempre con `1/cwnd` desde el inicio. Esto hace que la ventana tarde más en crecer desde el arranque, pero evita la ráfaga que generaría el slow start exponencial en una red con buffers chicos.

---

### Reducción de `cwnd` ante congestión

Cuando llega un ACK con `ecn = true`, se aplica reducción multiplicativa:
 
```cpp
cwnd = std::max(1.0, cwnd / 2.0);
```

El piso en `1.0` garantiza que siempre se pueda enviar al menos un paquete, evitando que la ventana colapse a cero y deje la conexión en *deadlock*. La reducción a la mirad es el AIMD clásico.

**Qué se simplificó respecto a TCP:** TCP real distingue dos tipos de pérdida: por timeout (reducción a 1 y vuelta a slow start) y por triple ACK duplicado (fast retransmit, reducción a la mitad). En nuestra implementación solo existe ECN como señal de congestión y siempre se aplica la misma reducción (`/ 2.0`). No hay timeout ni retransmisión.

---

### Fuentes de la señal ECN

La señal ECN puede originarse en dos lugares:
 
*1. Cola intermedia (`Queue.cc`):* cuando el buffer de `Network.queue` supera el 80% de ocupación, se marca `ecn = true` directamente en el paquete de datos antes de reenviarlo:
 
```cpp
bool ecn = (lenBefore >= (int)(bufferSize * 0.8));
pkt->addPar("ecn") = ecn;  // o par("ecn") si ya existe
```

*2. Receptor (`TransportRx.cc`):* cuando el `rxBuffer` supera el 80% de ocupación, se marca `ecn = true` en el ACK generado. Además, si el paquete de datos ya traía `ecn = true` desde la queue intermedia, `TransportRx` propaga esa señal al ACK:
 
```cpp
bool ecn = (rxBuffer.getLength() >= (int)(bufferSize * ECN_THRESHOLD));
if (msg->hasPar("ecn") && msg->par("ecn").boolValue()) {
    ecn = true;
}
```

Esto significa que `TransportTx` puede recibir ECN tanto por saturación de la red intermedia como por saturación del receptor, y en ambos casos reduce `cwnd`. Esta doble fuente cubre los dos casos de estudio: Caso 1 (cuello en el receptor) y Caso 2 (cuello en la red).
 
El umbral del 80% se eligió para dar aviso anticipado: si se esperara al 100%, los ACKs con ECN llegarían demasiado tarde y habría descartes antes de que el transmisor reduzca `cwnd`.
 
---
 
### ACK por paquete
 
Se implementó **ACK por paquete**: `TransportRx` genera un ACK de 20 bytes por cada paquete de datos recibido. Esto maximiza la frecuencia de feedback y permite que `TransportTx` ajuste `cwnd` e `inFlight` con la mayor granularidad posible.
 
**Trade-off:** en escenarios de alta tasa esto genera bastante tráfico de control en el canal de feedback. Para este laboratorio el overhead es bajo: los paquetes de datos son de 12.500 bytes y los ACKs de 20 bytes, una relación de 625:1. En redes reales esto justifica el uso de *delayed ACK* o ACK acumulativo.
 
---
 
### No se implementa retransmisión
 
Si un paquete se pierde en la `queue` intermedia (descartado por buffer lleno), no se retransmite. El mecanismo de ventana regula el envío para *evitar* que los buffers se llenen, pero no recupera pérdidas ya ocurridas.
 
**Consecuencia medible:** si hay descartes antes de que el feedback llegue al transmisor, esos paquetes se pierden definitivamente. Esto se puede observar en `packetDrops` de `Network.queue` y `TransportRx`. El `Sink` registra solo los paquetes que efectivamente llegan, por lo que el goodput medido refleja esas pérdidas.
 
---
 
### Mecanismo anti-deadlock: WINDOW_UPDATE
 
Existe un caso límite: si `rwnd` llega a 0, `TransportTx` deja de enviar completamente. Si `TransportRx` no genera tráfico nuevo, nunca llega otro ACK y la conexión queda paralizada (*deadlock* de ventana cero).
 
Para evitarlo, `TransportRx` detecta el momento en que el buffer pasa de completamente lleno a tener al menos un slot libre, y envía un `WINDOW_UPDATE` explícito:
 
```cpp
// En trySendToSink(), luego de enviar al Sink:
int freeSlots = bufferSize - rxBuffer.getLength();
if (freeSlots > 0 && (bufferSize - (rxBuffer.getLength() + 1)) == 0) {
    // Habia 0 slots libres antes, ahora hay 1 → mandar WINDOW_UPDATE
    wu->setKind(WINDOW_UPDATE);
    wu->addPar("rwnd") = freeSlots;
}
```
 
`TransportTx` procesa el `WINDOW_UPDATE` igual que un ACK en cuanto a actualizar `rwnd`, pero sin decrementar `inFlight` ni modificar `cwnd`.
 
---
 
### Serialización de envíos con canal ocupado
 
Tanto `TransportTx` como `TransportRx` usan self-messages para no enviar por un canal ocupado. Antes de cada `send()` se consulta el canal:
 
```cpp
cChannel *ch = gate("toOut$o")->findTransmissionChannel();
if (ch && ch->isBusy()) {
    scheduleAt(ch->getTransmissionFinishTime(), sendEvent);
    return;
}
```
 
Esto es obligatorio en OMNeT++: un `send()` sobre un canal en transmisión aborta la simulación. El self-message actúa como cola de un elemento: cuando el canal queda libre, se reintenta el envío.
 
---


### Métricas registradas
 
| Vector / Escalar | Módulo | Descripción |
|---|---|---|
| `bufferSize` (vec) | `TransportTx` | Ocupación del buffer de transmisión a lo largo del tiempo |
| `cwnd` (vec) | `TransportTx` | Evolución de la ventana de congestión |
| `inFlight` (vec) | `TransportTx` | Paquetes en vuelo en cada instante |
| `Final cwnd` (scalar) | `TransportTx` | Valor de `cwnd` al finalizar la simulación |
| `stability (stddev effWin)` (scalar) | `TransportTx` | Desvío estándar de `effectiveWindow = min(rwnd, cwnd)` a lo largo de la simulación |
| `Dropped packets (TransportTx)` (scalar) | `TransportTx` | Total de paquetes descartados por buffer de TX lleno |
| `bufferSize` (vec) | `TransportRx` | Ocupación del buffer de recepción |
| `packetDrops` (vec) | `TransportRx` | Descartes acumulados en el receptor |
| `Dropped packets (TransportRx)` (scalar) | `TransportRx` | Total de descartes en el receptor |
| `bufferSize` (vec) | `Network.queue` | Ocupación de la cola intermedia |
| `packetDrops` (vec) | `Network.queue` | Descartes acumulados en la red |
| `Delay` (vec) | `Sink` | Demora extremo a extremo por paquete |
| `Goodput (pkt/s)` (scalar) | `Sink` | Paquetes entregados por segundo sobre 200s de simulación |
 
La evolución de `cwnd` es la métrica más útil para verificar el funcionamiento del protocolo: debe verse crecer gradualmente con cada ACK sin ECN y caer a la mitad ante cada ACK con ECN. El `stddev` de `effectiveWindow` cuantifica la estabilidad del mecanismo: un valor bajo indica que la ventana converge a un régimen estacionario; un valor alto indica oscilaciones fuertes.
