#ifndef QUEUE
#define QUEUE

#include <string.h>
#include <omnetpp.h>

using namespace omnetpp; //Permite usar las clases de OMNeT++ sin escribir omnetpp:: adelante.

class Queue: public cSimpleModule { //Queue hereda de cSimpleModule, que es la clase base de OMNeT++ para modulos simples
private:
    cQueue buffer;              //Cola donde se guardan los paquetes mientras esperan ser enviados
    cMessage *endServiceEvent;  //Mensaje interno(timer) que representa fin de servicio
    simtime_t serviceTime;      //Tiempo que tarda en transmitirse un paquete
    int bufferSize;             //Tamaño maximo de la cola
    long droppedPackets;        //Contador de paquetes descartados por buffer lleno
    cOutVector bufferSizeVector;//Ocupacion del buffer a lo largo del tiempo
    cOutVector packetDropVector;//Descartes acumulados a lo largo del tiempo
public:
    Queue();          //Constructor: se llama automaticamente al crear el objeto
    virtual ~Queue(); //Destructor: se llama automaticamente al destruir el objeto
protected:
    //Funciones virtuales: dice usen estas y no las de cSimpleModule
    virtual void initialize(); //OMNeT++ la llama al arrancar la simulacion
    virtual void finish();     //OMNeT++ la llama al terminar la simulacion
    virtual void handleMessage(cMessage *msg); //OMNeT++ la llama cada vez que llega un mensaje
};

//Macro de OMNeT++ que registra esta clase como un modulo valido
//sin esto no se puede instanciar la clase
Define_Module(Queue);

Queue::Queue() {
    endServiceEvent = NULL; //Inicializo el puntero en null
}

Queue::~Queue() {
    cancelAndDelete(endServiceEvent); //Cancela el evento si esta pendiente
}

void Queue::initialize() {
    buffer.setName("buffer");
    endServiceEvent = new cMessage("endService"); //Crea un timer interno

    bufferSize = par("bufferSize"); //Lee el tamaño maximo del buffer desde omnetpp.ini
    droppedPackets = 0; //Inicializa el contador de paquetes descartados

    bufferSizeVector.setName("bufferSize"); //Nombre para los graficos
    packetDropVector.setName("packetDrops"); //Nombre para los graficos
}

void Queue::finish() {
    //Registramos el total de paquetes descartados
    recordScalar("Dropped packets", droppedPackets);
}

void Queue::handleMessage(cMessage *msg) {

    //Si el mensaje es el endServiceEvent(timer) termine de transmitir
    if (msg == endServiceEvent) {
        //Si hay paquetes esperando
        if (!buffer.isEmpty()) {
            //Casteo seguro de OMNeT++
            cPacket *pkt = check_and_cast<cPacket *>(buffer.pop());

            // Marcar ECN si el buffer supera el 80%
            bool ecn = (buffer.getLength() >= (int)(bufferSize * 0.8));
            if (!pkt->hasPar("ecn")) {
                pkt->addPar("ecn") = ecn;
            } else {
                pkt->par("ecn") = ecn;
}
            //Busco el canal de salida para calcular cuanto tarda en transmitir este paquete
            cChannel *channel = gate("out")->findTransmissionChannel();
            //Si hay canal calculo la duracion según tamaño del paquete, sino 0
            simtime_t serviceTime = channel ? channel->calculateDuration(pkt) : SIMTIME_ZERO;

            //Envio el paquete al siguiente modulo
            send(pkt, "out");
            bufferSizeVector.record(buffer.getLength());

            //Programo el timer para el proximo paquete 
            scheduleAt(simTime() + serviceTime, endServiceEvent);
        }
        return;
    } else { //Si el mensaje es un paquete de datos(llega de afuera)
        //Verifico si el buffer esta lleno antes de encolar
        if (buffer.getLength() >= bufferSize) {
            droppedPackets++; //Incremento el contador de descartes
            packetDropVector.record(droppedPackets); //Registro el nuevo total de descartes
            delete msg;
            return;
        }

        //Encolo el paquete
        buffer.insert(msg);
        bufferSizeVector.record(buffer.getLength());

        //Si el server esta libre arranco ahora mismo
        if (!endServiceEvent->isScheduled()) {
            scheduleAt(simTime(), endServiceEvent); //Significa ahora mismo
        }
    }
}

#endif /* QUEUE */
