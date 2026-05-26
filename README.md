# Laboratorio 3 — Transporte · Redes y Sistemas Distribuidos · FaMAF UNC

**Grupo 23** · Álvarez Lis Ailín · Pinilla Lautaro · Sabino Lucas  
Informe académico: [`Informe.md`](Informe.md)  
Decisiones de diseño (Parte 2): [`Decisiones de diseño`](Decisiones%20de%20diseño)

---

## Archivos importantes

| Archivo / Carpeta | Descripción |
|---|---|
| `Informe.md` | Informe académico completo (Partes 1 y 2 + Competición) |
| `omnetpp.ini` | Configuraciones de simulación (`Caso1`, `Caso2`, `Competicion`) |
| `network.ned` | Topología de la red |
| `Generator.cc` / `Queue.cc` / `Sink.cc` | Módulos base (Parte 1) |
| `TransportTx.cc` / `TransportRx.cc` | Módulos con control por ventanas (Parte 2) |
| `analisis.py` | Script de análisis y generación de gráficos |
| `graficos/` | Gráficos generados por `analisis.py` |

---

## Requisitos previos

- OMNeT++ 6.3.0 instalado en `~/omnetpp-6.3.0/`
- Python 3 con `matplotlib` y `pandas`

---

## Compilación

```bash
source ~/omnetpp-6.3.0/setenv
make
```

---

## Ejecución

El repositorio usa tags de Git para separar los dos estados del modelo:

| Tag | Contenido |
|---|---|
| `v0.1-parte1` | Modelo sin control (Parte 1) |
| `v1.0-final` | Modelo con control por ventanas (Parte 2) |

### Parte 1 — Análisis sin control (tag `v0.1-parte1`)

```bash
git checkout v0.1-parte1
source ~/omnetpp-6.3.0/setenv
make

rm -rf results/*
./lab3 -u Cmdenv -c Caso1
./lab3 -u Cmdenv -c Caso2

opp_scavetool export -o caso1_sin_control.csv results/Caso1-*.vec results/Caso1-*.sca
opp_scavetool export -o caso2_sin_control.csv results/Caso2-*.vec results/Caso2-*.sca

python3 analisis.py
```

### Parte 2 — Control por ventanas (tag `v1.0-final`)

```bash
git checkout v1.0-final
source ~/omnetpp-6.3.0/setenv
make

rm -rf results/*
./lab3 -u Cmdenv -c Caso1
./lab3 -u Cmdenv -c Caso2

opp_scavetool export -o caso1_con_control.csv results/Caso1-*.vec results/Caso1-*.sca
opp_scavetool export -o caso2_con_control.csv results/Caso2-*.vec results/Caso2-*.sca

python3 analisis.py parte2
```

### Escenario de Competición (tag `v1.0-final`)

```bash
rm -rf results/*
./lab3 -u Cmdenv -c Competicion
opp_scavetool export -o competicion.csv results/Competicion-*.vec results/Competicion-*.sca
```

Los gráficos generados quedan en `./graficos/`.