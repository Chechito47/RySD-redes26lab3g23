/*
  Este modulo se encarga de recibir los paquetes del Generator y guardarlos en un buffer intero
  - Envia paquetes solo si inFlight < min(rwnd, cwnd)
  - Cuando llega un ACK por toOut$i: actualizar rwnd, decrementar inFlight, ajustar cwnd
  - Manejar el canal ocupado con un self-message
*/

#ifndef TRANSPORTTX
#define TRANSPORTTX

#include <string.h>
#include <omnetpp.h>
#include <iostream>

using namespace omnetpp;

// Tipos de paquetes
enum PacketKind {
    DATA = 1,
    ACK = 2,
    WINDOW_UPDATE = 3
};

class TransportTx : public cSimpleModule {
private:
    // buffer interno de transmision
    cQueue txBuffer; // Paquetes que llegaron del Generator pero aun no se enviaron
    int bufferSize; // Capacidad maxima del buffer

    // Variables tcp
    double cwnd;  // Ventana de congestion (La maneja TransportTx)
    int rwnd;     // Ventana de recepcion  (la anuncia TransportRx en cada ACK)
    int inFlight; // Paquetes enviados y aun no reconocidos

    // Timers internos
    cMessage *sendEvent; // Se dispara cuando el canal queda libre para enviar

    // Estadisticas
    cOutVector bufferSizeVec;
    cOutVector cwndVec;
    cOutVector inFlightVec;
    long droppedPackets;

    // Stability
    cStdDev effectiveWindowStats;

public:
    TransportTx();
    virtual ~TransportTx();

protected:
    virtual void initialize();
    virtual void finish();
    virtual void handleMessage(cMessage *msg);

private:
    void trySend();
};

Define_Module(TransportTx);

TransportTx::TransportTx() {
    sendEvent = nullptr;
}

TransportTx::~TransportTx() {
    cancelAndDelete(sendEvent);
}

void TransportTx::initialize() {
    //std::cout << "TransportTx::initialize() llamado. inFlight=" << inFlight << " cwnd=" << cwnd << " rwnd=" << rwnd << std::endl;

    txBuffer.setName("txBuffer");
    bufferSize = par("bufferSize");
    droppedPackets = 0;

    // Valores iniciales 
    cwnd = 1.0; // Slow start
    rwnd = 10;  // Asumo que el receptor tiene espacio hasta recibir el primer ACK
    inFlight = 0; //Comienzo sin paquetes en viaje

    // timer interno para serializar envios
    sendEvent = new cMessage("sendEvent");

    // vectores de estadisticas
    bufferSizeVec.setName("bufferSize");
    cwndVec.setName("cwnd");
    inFlightVec.setName("inFlight");

    // Stability
    effectiveWindowStats.setName("effectiveWindowStats");
}

void TransportTx::finish() {
    // recordScalar guarda metricas de los modulos 
    recordScalar("Dropped packets (TransportTx)", droppedPackets);
    recordScalar("Final cwnd", cwnd);
    recordScalar("stability (stddev effWin)", effectiveWindowStats.getStddev());
}

void TransportTx::handleMessage(cMessage *msg) {
    //std::cout << "TIEMPO " << simTime() << " handleMessage() llamado, kind=" << msg->getKind() << std::endl;

    // Caso 1: lleog un ACK / WINDOW_UPDATE desde TransportRx
    // Entra por toOut$i (el lado $i del gate inout)
    if (msg->getKind() == ACK || msg->getKind() == WINDOW_UPDATE) {
        
        // Actualizar ventana de recepcion anuciada por el receptor
        if (msg->hasPar("rwnd")) {
            rwnd = (int) msg->par("rwnd").longValue();
        }

        // Si es un ACK => un paquete fue entregado
        if (msg->getKind() == ACK){
            inFlight--;
            if (inFlight < 0) inFlight = 0; 
        }

        // Actualizar cwnd segun señal de congestion
        bool ecn = msg->hasPar("ecn") && msg->par("ecn").boolValue();
        if (ecn) {
            // Detecta congestion => reduccion multiplicativa
            cwnd = std::max(1.0, cwnd / 2.0);
        } else if (msg->getKind() == ACK) {
            // Sin congestion => crecimiento aditivo
            cwnd += 1.0 / cwnd;
        }

        cwndVec.record(cwnd);
        inFlightVec.record(inFlight);

        double eff = std::min((double)rwnd, cwnd);
        effectiveWindowStats.collect(eff);

        //std::cout << "TIEMPO " << simTime() << " Llegó ACK. inFlight antes=" << inFlight << " cwnd antes=" << cwnd << std::endl;

        delete msg;

        // Intento enviar paquetes con ventana actualizada
        trySend();
        return;
    } 

    // Caso 2: El canal quedo libre
    if (msg == sendEvent) {
        trySend();
        return;
    }

    // Caso 3: llego un paquete de datos desde el generator
    if(txBuffer.getLength() >= bufferSize) {
        // Buffer lleno => descarto
        droppedPackets++;
        delete msg;
        return;
    }

    txBuffer.insert(msg);
    bufferSizeVec.record(txBuffer.getLength());

    trySend();
}

void TransportTx::trySend() {
    // Enviamos paquetes mientras la ventana efectiva lo permita y haya datos
    while (inFlight < (int)std::min((double)rwnd, cwnd) && !txBuffer.isEmpty()) {
 
        // Verificar si el canal de salida está ocupado
        cChannel *ch = gate("toOut$o")->findTransmissionChannel();
        if (ch && ch->isBusy()) {
            // Programar reintento cuando el canal quede libre
            if (!sendEvent->isScheduled()) {
                scheduleAt(ch->getTransmissionFinishTime(), sendEvent);
            }
            return;
        }
 
        // Sacar el paquete del buffer y enviarlo
        cPacket *pkt = check_and_cast<cPacket *>(txBuffer.pop());
        pkt->setKind(DATA);
        //std::cout << "TIEMPO " << simTime() << " Enviando paquete. inFlight=" << inFlight << " cwnd=" << cwnd << " rwnd=" << rwnd << std::endl;
        send(pkt, "toOut$o");
 
        inFlight++;
        bufferSizeVec.record(txBuffer.getLength());
        inFlightVec.record(inFlight);
    }
}
 
#endif