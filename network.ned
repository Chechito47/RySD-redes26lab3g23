simple Generator
{
    parameters:
        double generationInterval @mutable;
        int packetByteSize;
        @display("i=block/source");
    gates:
        output out;
}

simple Queue
{
    parameters:
        int bufferSize;
        @display("i=block/queue;q=buffer");
    gates:
        input in;
        output out;
}

simple Sink
{
    parameters:
        @display("i=block/sink");
    gates:
        input in;
}

simple TransportTx
{
    parameters:
        int bufferSize;
    gates:
        input toApp; //Recibe paquetes del generator
        inout toOut; //Manda datos al queue y recibe datos del feedbackQueue(ACKs)
}

simple TransportRx
{
    parameters:
        int bufferSize;
    gates:
        output toApp; //Manda datos al sink
        inout toOut;  //Recibe datos del queue y manda datos por el feedbackQueue(ACKs)
}

module NodeTx
{
    gates:
        inout out; //Ahora tambien recibe ACKs (out es solo el nombre)
    submodules:
        gen: Generator {
            @display("p=70,50");
        }
        transport: TransportTx { //Reemplaza al txBuffer
            @display("p=70,140");
        }
    connections:
        gen.out --> transport.toApp; //generator le pasa paquetes a TransportTx
        transport.toOut <--> out;    //TransportTx recibe feedbackQueue y manda datos al queue
}

module NodeRx
{
    parameters:
        double rxToSinkDatarate @unit(bps) = default(1Mbps);
    gates:
        inout in; //Ahora recibe datos del queue y manda datos por el feedbackQueue(ACKs)
    submodules:
        transport: TransportRx { //Reemplaza al rxBuffer
            @display("p=70,50");
        }
        sink: Sink {
            @display("p=70,140");
        }
    connections:
        in <--> transport.toOut; //TransportRx manda feedbackQueue y recibe queues
        transport.toApp --> sink.in; //TransportRx manda datos al sink
}

network Network
{
    parameters:
        double txToQueueDatarate @unit(bps) = default(1Mbps);
        double queueToRxDatarate @unit(bps) = default(1Mbps);
        double feedbackDatarate @unit(bps) = default(1Mbps);
        double linkDelay @unit(s) = default(100us);
        @display("bgl=2");
    submodules:
        nodeTx: NodeTx {
            @display("p=50,100");
        }
        queue: Queue {
            @display("p=150,100");
        }
        feedbackQueue: Queue {
            @display("p=150,200");
        }
        nodeRx: NodeRx {
            @display("p=250,100");
        }
    connections:
        nodeTx.out$o --> { datarate = parent.txToQueueDatarate; delay = parent.linkDelay; } --> queue.in;
        queue.out --> { datarate = parent.queueToRxDatarate; delay = parent.linkDelay; } --> nodeRx.in$i;
        nodeRx.in$o --> { datarate = parent.feedbackDatarate; delay = parent.linkDelay; } --> feedbackQueue.in;
        //in es solo el nombre de la puerta del modulo, no tiene que ver con si es entrada o salida
        //salen por out, por eso el $o
        feedbackQueue.out --> { datarate = parent.feedbackDatarate; delay = parent.linkDelay; } --> nodeTx.out$i;
}