/*
  Este modulo se encarga de recibir paquetes de datos por toOut$i
  - Por cada paquete recibido, mandar un ACK con rwnd (espacio libre) y ecn (si la feedbackQueue esta congestionada)
  - Manejar el canal de feedback ocupado con una cola interna
*/

#ifndef TRANSPORTRX
#define TRANSPORTRX

#include <string.h>
#include <omnetpp.h>

// Umbral de ocupación del buffer para marcar congestión (ecn)
// Si el buffer supera este porcentaje de ocupación, se marca ecn=true en el ACK
#define ECN_THRESHOLD 0.8


using namespace omnetpp;

// Tipos de paquetes
enum PacketKind {
    DATA_RX = 1,
    ACK_RX = 2,
    WINDOW_UPDATE = 3
};

class TransportRx : public cSimpleModule {
private:
    // buffer interno de recepcion (feedback)
    cQueue rxBuffer; // Paquetes que llegaron por toOut$i pero aun no se han procesado
    int bufferSize; // Capacidad maxima del buffer

    // Cola interna de ACKs pendientes para enviar
    cQueue feedbackQueue;

    // Self message para serializar el envio de ACKs
    cMessage *sendFeedbackEvent;

    // Self message para enviar datos al sink
    cMessage *sendToSinkEvent;

    // Estadisticas
    cOutVector bufferSizeVec;
    cOutVector packetDropVec;
    long droppedPackets;

public:
    TransportRx();
    virtual ~TransportRx();

protected:
    virtual void initialize();
    virtual void finish();
    virtual void handleMessage(cMessage *msg);

private:
    // Genera y encola un ACK con el estado actual del buffer 
    void generateAck(bool ecn);

    // Intenta enviar el proximo ACK si el canal de feedback esta libre
    void trySendFeedback();

    // Intenta enviar el siguiente paquete al Sink
    void trySendToSink();
};

Define_Module(TransportRx);

TransportRx::TransportRx() {
    sendFeedbackEvent = nullptr;
    sendToSinkEvent = nullptr;
}

TransportRx::~TransportRx() {
    cancelAndDelete(sendFeedbackEvent);
    cancelAndDelete(sendToSinkEvent);
}

void TransportRx::initialize() {
    rxBuffer.setName("rxBuffer");
    bufferSize = par("bufferSize");
    droppedPackets = 0;

    sendFeedbackEvent = new cMessage("sendFeedbackEvent");
    sendToSinkEvent = new cMessage("sendToSinkEvent");

    bufferSizeVec.setName("bufferSize");
    packetDropVec.setName("packetDrops");
}

void TransportRx::finish() {
    recordScalar("Dropped packets (TransportRx)", droppedPackets);
}

void TransportRx::handleMessage(cMessage *msg) {

    // Caso 1: Timer para enviar ACK al trasnmisor
    if (msg == sendFeedbackEvent) {
        trySendFeedback();
        return;
    }

    // Caso 2: Timer enviar datos al Sink
    if (msg == sendToSinkEvent) {
        trySendToSink();
        return;
    }

    // Caso 3: llego un paquete de datos desde el transmisor por toOut$i
    if (msg->getKind() == DATA_RX || msg->getKind() == 0) {
        if (rxBuffer.getLength() >= bufferSize) {
            droppedPackets++;
            packetDropVec.record(droppedPackets);
            delete msg;
            generateAck(false);
            return;
        }

        // Guardar el paquete en el buffer de recepcion
        rxBuffer.insert(msg);
        bufferSizeVec.record(rxBuffer.getLength());

        // Calcular si hay congestion (buffer supera el umbral ECN)
        bool ecn = (rxBuffer.getLength() >= (int)(bufferSize * ECN_THRESHOLD));
        // Propagamos ECN si venia marcado en el paquete
        if (msg->hasPar("ecn") && msg->par("ecn").boolValue()) {
            ecn = true;
        }

        // Generar ACK informando espacio libre y señal ECN
        generateAck(ecn);

        // Intentar enviar datos al sink
        trySendToSink();
        return;
    }
}

void TransportRx::generateAck(bool ecn) {
    // Calcular espacio libre en el buffer (rwnd)
    int freeSlots = bufferSize - rxBuffer.getLength();
 
    // Crear paquete de ACK
    cPacket *ack = new cPacket("ack");
    ack->setByteLength(20);  // ACKs son pequeños
    ack->setKind(ACK_RX);
    ack->addPar("rwnd") = freeSlots;
    ack->addPar("ecn")  = ecn;
 
    // Encolar el ACK en la cola de feedback
    feedbackQueue.insert(ack);
 
    // Intentar enviar si el canal está libre
    trySendFeedback();
}
 
void TransportRx::trySendFeedback() {
    if (feedbackQueue.isEmpty()) return;
 
    // Verificar si el canal de feedback está ocupado
    cChannel *ch = gate("toOut$o")->findTransmissionChannel();
    if (ch && ch->isBusy()) {
        // Esperar a que el canal quede libre
        if (!sendFeedbackEvent->isScheduled()) {
            scheduleAt(ch->getTransmissionFinishTime(), sendFeedbackEvent);
        }
        return;
    }
 
    // Enviar el próximo ACK
    cPacket *ack = check_and_cast<cPacket *>(feedbackQueue.pop());
    send(ack, "toOut$o");
 
    // Si quedan más ACKs, programar el siguiente envío
    if (!feedbackQueue.isEmpty()) {
        cChannel *chNext = gate("toOut$o")->findTransmissionChannel();
        simtime_t when = simTime();
        if (chNext && chNext->isBusy()) {
            when = chNext->getTransmissionFinishTime();
        }
        if (!sendFeedbackEvent->isScheduled()) {
            scheduleAt(when, sendFeedbackEvent);
        }
    }
}
 
void TransportRx::trySendToSink() {
    if (rxBuffer.isEmpty()) return;
 
    // Verificar si el canal hacia el Sink está ocupado
    cChannel *ch = gate("toApp")->findTransmissionChannel();
    if (ch && ch->isBusy()) {
        if (!sendToSinkEvent->isScheduled()) {
            scheduleAt(ch->getTransmissionFinishTime(), sendToSinkEvent);
        }
        return;
    }
 
    // Enviar el siguiente paquete al Sink
    cPacket *pkt = check_and_cast<cPacket *>(rxBuffer.pop());
    send(pkt, "toApp");
    bufferSizeVec.record(rxBuffer.getLength());

    // Si el buffer estaba lleno (rwnd era 0) y ahora tiene espacio, notificar al transmisor
    int freeSlots = bufferSize - rxBuffer.getLength();
    if (freeSlots > 0 && (bufferSize - (rxBuffer.getLength() + 1)) == 0) {
        // Habia 0 slots libres antes, ahora hay 1 → mandar WINDOW_UPDATE
        cPacket *wu = new cPacket("windowUpdate");
        wu->setByteLength(20);
        wu->setKind(WINDOW_UPDATE);
        wu->addPar("rwnd") = freeSlots;
        wu->addPar("ecn") = false;
        feedbackQueue.insert(wu);
        trySendFeedback();
    }
 
    // Si quedan más paquetes, programar el siguiente envío
    if (!rxBuffer.isEmpty()) {
        cChannel *chNext = gate("toApp")->findTransmissionChannel();
        simtime_t when = simTime();
        if (chNext && chNext->isBusy()) {
            when = chNext->getTransmissionFinishTime();
        }
        if (!sendToSinkEvent->isScheduled()) {
            scheduleAt(when, sendToSinkEvent);
        }
    }
}
 
#endif
