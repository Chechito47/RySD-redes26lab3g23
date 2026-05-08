simple Generator
{
    parameters:
        double generationInterval @mutable; // sec
        int packetByteSize; // bytes
        @display("i=block/source");
    gates:
        output out;
}

simple Queue
{
    parameters:
        int bufferSize; // Para limitar la capacidad
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

module NodeTx
{
    gates:
        output out;
    submodules:
        gen: Generator {
            @display("p=70,50");
        }
        txBuffer: Queue {
            @display("p=70,140");
        }
    connections:
        gen.out --> txBuffer.in;
        txBuffer.out --> out;
}

module NodeRx
{
    parameters:
        double rxToSinkDatarate @unit(bps) = default(1Mbps);
    gates:
        input in;
    submodules:
        rxBuffer: Queue {
            @display("p=70,50");
        }
        sink: Sink {
            @display("p=70,140");
        }
    connections:
        in --> rxBuffer.in;
        rxBuffer.out --> { datarate = rxToSinkDatarate; } --> sink.in;
}

network Network
{
    parameters:
        double txToQueueDatarate @unit(bps) = default(1Mbps);
        double queueToRxDatarate @unit(bps) = default(1Mbps);
        double linkDelay @unit(s) = default(100us);
        @display("bgl=2");
        
    submodules:
        nodeTx: NodeTx {
            @display("p=50,100");
        }
        queue: Queue {
            @display("p=150,100");
        }
        nodeRx: NodeRx {
            @display("p=250,100");
        }
        
    connections:
        nodeTx.out --> { datarate = txToQueueDatarate; delay = linkDelay; } --> queue.in;
        queue.out --> { datarate = queueToRxDatarate; delay = linkDelay; } --> nodeRx.in;
}