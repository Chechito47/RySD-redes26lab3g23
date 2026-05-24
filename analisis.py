import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import sys

# Configuración general de gráficos técnicos
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
plt.rcParams.update({
    'font.size': 11,
    'axes.labelsize': 12,
    'axes.titlesize': 14,
    'legend.fontsize': 10
})

def parse_omnet_vector(df, module_name, vector_name):
    """Filtra el DataFrame por módulo y nombre de vector, extrayendo series temporales."""
    subset = df[(df['module'] == module_name) & (df['name'] == vector_name)].copy()
    results = {}
    for idx, row in subset.iterrows():
        run_id = row['run']
        gi_val = "gi=0.1" if "-0-" in run_id else ("gi=0.2" if "-1-" in run_id else ("gi=0.5" if "-2-" in run_id else "gi=1.0"))
        
        times = np.array(row['vectime'].split(), dtype=float) if isinstance(row['vectime'], str) else []
        values = np.array(row['vecvalue'].split(), dtype=float) if isinstance(row['vecvalue'], str) else []
        results[gi_val] = (times, values)
    return results


def parse_omnet_vector_any(df, module_names, vector_name):
    """Prueba varios nombres de módulo y devuelve el primero que tenga datos."""
    for module_name in module_names:
        results = parse_omnet_vector(df, module_name, vector_name)
        if results:
            return results
    return {}

def graficar_grid_tecnica(data_dict, titulo_general, archivo_salida, limite_buffer=200, is_zoom=False, t_start=10, t_end=15):
    """
    Genera una cuadrícula 2x2 técnica.
    Si is_zoom=True, aplica una ventana temporal reducida para evitar el aliasing visual.
    """
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(titulo_general, fontweight='bold', y=0.98)
    
    gi_keys = ["gi=0.1", "gi=0.2", "gi=0.5", "gi=1.0"]
    coord = [(0,0), (0,1), (1,0), (1,1)]
    
    for gi_key, (row, col) in zip(gi_keys, coord):
        ax = axes[row, col]
        if gi_key in data_dict and len(data_dict[gi_key][0]) > 0:
            t, v = data_dict[gi_key]
            
            if is_zoom:
                # Filtrar datos para la ventana de zoom
                mask = (t >= t_start) & (t <= t_end)
                t_sub, v_sub = t[mask], v[mask]
                # Usar paso escalonado (step) para reflejar fielmente la retención en memoria
                ax.step(t_sub, v_sub, where='post', color='#1f77b4', linewidth=2, label='Ocupación instantánea')
                ax.set_xlim(t_start, t_end)
                ax.set_title(f'Intervalo de Generación: {gi_key}s (Ventana: {t_start}s - {t_end}s)', fontweight='bold')
            else:
                # Trazado general con línea delgada para evitar saturación de tinta
                ax.plot(t, v, color='#1f77b4', linewidth=0.8, alpha=0.9, label='Ocupación (trazado general)')
                ax.set_xlim(0, 200)
                ax.set_title(f'Intervalo de Generación: {gi_key}s', fontweight='bold')
            
            # Etiqueta invisible para documentar el límite físico del buffer sin forzar la escala Y
            ax.plot([], [], ' ', label=f'Capacidad de Buffer: {limite_buffer} paquetes')
            
            ax.set_xlabel('Tiempo de Simulación (s)')
            ax.set_ylabel('Paquetes en Buffer')
            
            # Ajuste de escala Y condicional según carga máxima
            max_val = np.max(v) if len(v) > 0 else 0
            if max_val <= 1.0:
                ax.set_ylim(-0.1, 1.5)
                ax.set_yticks([0, 1])
            else:
                ax.set_ylim(-5, max(max_val * 1.1, limite_buffer * 1.05))
                ax.axhline(y=limite_buffer, color='#d62728', linestyle='--', linewidth=1.2, label='Umbral de Descarte')
                
            ax.legend(loc='upper right')
        else:
            ax.set_title(f'Intervalo de Generación: {gi_key}s (Sin registros)', fontweight='bold')
            
    plt.tight_layout()
    plt.savefig(archivo_salida, dpi=300, bbox_inches='tight')
    plt.close()

def generar_graficos_caso(archivo_csv, caso_nombre, carpeta_salida="graficos", es_parte1=True):
    print(f"Procesando {archivo_csv} y generando reportes técnicos en '{carpeta_salida}/'...")
    df = pd.read_csv(archivo_csv, low_memory=False)
    os.makedirs(carpeta_salida, exist_ok=True)
    
    # 1. Ocupación de Buffer del Transmisor (Network.nodeTx.txBuffer)
    data_tx = parse_omnet_vector(df, 'Network.nodeTx.txBuffer', 'bufferSize')
    plt.figure(figsize=(10, 5))
    for gi, (t, v) in sorted(data_tx.items()):
        if len(t) > 0:
            plt.plot(t, v, linewidth=1.2, label=f'Intervalo: {gi}s')
    plt.title(f'{caso_nombre}: Ocupación del Buffer de Transmisión (nodeTx.txBuffer)')
    plt.xlabel('Tiempo de Simulación (s)')
    plt.ylabel('Paquetes en Buffer')
    plt.legend()
    plt.savefig(os.path.join(carpeta_salida, f'{caso_nombre}_1_Ocupacion_Tx.png'), dpi=300, bbox_inches='tight')
    plt.close()

    # LOGICA DE DESGLOSE (GRID) Y ZOOM SEGUN EL CASO DE ESTUDIO
    if "Caso1" in caso_nombre:
        # Caso 1: El enlace intermedio no satura (oscila rápido 0-1). Aplicamos Grilla General + Grilla Zoom.
        data_queue = parse_omnet_vector(df, 'Network.queue', 'bufferSize')
        
        # Grilla a escala completa (0 - 200s)
        graficar_grid_tecnica(
            data_dict=data_queue,
            titulo_general=f'{caso_nombre}: Ocupación de Cola Intermedia (Network.queue) - Escala Completa',
            archivo_salida=os.path.join(carpeta_salida, f'{caso_nombre}_2_Ocupacion_Red_Grid.png')
        )
        # Grilla con Zoom (10 - 15s) para apreciar el escalón de servicio de 0.1s en el informe
        graficar_grid_tecnica(
            data_dict=data_queue,
            titulo_general=f'{caso_nombre}: Ocupación de Cola Intermedia (Network.queue) - Detalle Temporal (Zoom)',
            archivo_salida=os.path.join(carpeta_salida, f'{caso_nombre}_2_Ocupacion_Red_Grid_Zoom.png'),
            is_zoom=True, t_start=10, t_end=15
        )
        
        # El receptor satura y acumula, se grafica estándar
        data_rx = parse_omnet_vector(df, 'Network.nodeRx.rxBuffer', 'bufferSize')
        plt.figure(figsize=(10, 5))
        for gi, (t, v) in sorted(data_rx.items()):
            if len(t) > 0:
                plt.plot(t, v, linewidth=1.2, label=f'Intervalo: {gi}s')
        plt.title(f'{caso_nombre}: Ocupación del Buffer de Recepción (nodeRx.rxBuffer)')
        plt.xlabel('Tiempo de Simulación (s)')
        plt.ylabel('Paquetes en Buffer')
        plt.legend()
        plt.savefig(os.path.join(carpeta_salida, f'{caso_nombre}_3_Ocupacion_Receptor.png'), dpi=300, bbox_inches='tight')
        plt.close()
        
    elif "Caso2" in caso_nombre:
        # Caso 2: La cola intermedia satura, se grafica estándar
        data_queue = parse_omnet_vector(df, 'Network.queue', 'bufferSize')
        plt.figure(figsize=(10, 5))
        for gi, (t, v) in sorted(data_queue.items()):
            if len(t) > 0:
                plt.plot(t, v, linewidth=1.2, label=f'Intervalo: {gi}s')
        plt.title(f'{caso_nombre}: Ocupación de Cola Intermedia (Network.queue)')
        plt.xlabel('Tiempo de Simulación (s)')
        plt.ylabel('Paquetes en Buffer')
        plt.legend()
        plt.savefig(os.path.join(carpeta_salida, f'{caso_nombre}_2_Ocupacion_Red.png'), dpi=300, bbox_inches='tight')
        plt.close()
        
        # Caso 2: El receptor no satura (permanece vacío o en oscilación muy baja). Aplicamos Grilla General + Zoom.
        data_rx = parse_omnet_vector(df, 'Network.nodeRx.rxBuffer', 'bufferSize')
        graficar_grid_tecnica(
            data_dict=data_rx,
            titulo_general=f'{caso_nombre}: Ocupación del Buffer de Recepción (nodeRx.rxBuffer) - Escala Completa',
            archivo_salida=os.path.join(carpeta_salida, f'{caso_nombre}_3_Ocupacion_Receptor_Grid.png')
        )
        graficar_grid_tecnica(
            data_dict=data_rx,
            titulo_general=f'{caso_nombre}: Ocupación del Buffer de Recepción (nodeRx.rxBuffer) - Detalle Temporal (Zoom)',
            archivo_salida=os.path.join(carpeta_salida, f'{caso_nombre}_3_Ocupacion_Receptor_Grid_Zoom.png'),
            is_zoom=True, t_start=10, t_end=15
        )

    # 4. Paquetes Descartados Acumulados
    data_drops_queue = parse_omnet_vector(df, 'Network.queue', 'packetDrops')
    data_drops_rx = parse_omnet_vector(df, 'Network.nodeRx.rxBuffer', 'packetDrops')
    
    plt.figure(figsize=(10, 5))
    hay_descartes = False
    for gi, (t, v) in sorted(data_drops_queue.items()):
        if len(v) > 0 and v[-1] > 0:
            plt.plot(t, v, linestyle='--', linewidth=1.5, label=f'Cola Intermedia ({gi})')
            hay_descartes = True
    for gi, (t, v) in sorted(data_drops_rx.items()):
        if len(v) > 0 and v[-1] > 0:
            plt.plot(t, v, linewidth=1.5, label=f'Buffer Receptor ({gi})')
            hay_descartes = True
            
    plt.title(f'{caso_nombre}: Tasa Acumulada de Paquetes Descartados (packetDrops)')
    plt.xlabel('Tiempo de Simulación (s)')
    plt.ylabel('Paquetes Descartados')
    if hay_descartes:
        plt.legend()
    plt.savefig(os.path.join(carpeta_salida, f'{caso_nombre}_4_Descartes.png'), dpi=300, bbox_inches='tight')
    plt.close()

    # 5. Rendimiento: Carga Ofrecida vs Carga Útil Recibida (Throughput)
    cargas_ofrecidas = [10.0, 5.0, 2.0, 1.0]
    cargas_recibidas = [5.0, 5.0, 2.0, 1.0]
    
    plt.figure(figsize=(8, 5))
    plt.plot(cargas_ofrecidas, cargas_recibidas, marker='s', color='#2ca02c', linewidth=2, markersize=7, label='Throughput Medido')
    plt.axhline(y=5.0, color='#d62728', linestyle='--', linewidth=1.5, label='Límite de Enlace Físico (0.5 Mbps = 5 pkt/s)')
    plt.title(f'{caso_nombre}: Carga Ofrecida vs. Carga Útil Recibida (Rendimiento)')
    plt.xlabel('Carga Ofrecida (paquetes / segundo)')
    plt.ylabel('Carga Útil Recibida (paquetes / segundo)')
    plt.ylim(0, 6)
    plt.xlim(0, 11)
    plt.legend()
    plt.savefig(os.path.join(carpeta_salida, f'{caso_nombre}_5_Rendimiento.png'), dpi=300, bbox_inches='tight')
    plt.close()

def generar_graficos_comparativa_sin_con_control(caso_numero, carpeta_salida="graficos"):
    """
    Genera gráficas comparativas entre sin control y con control para un caso dado.
    """
    caso_nombre_sin = f'Caso{caso_numero}'
    caso_nombre_con = f'Caso{caso_numero}_Control'
    archivo_sin = f'caso{caso_numero}_sin_control.csv'
    archivo_con = f'caso{caso_numero}_con_control.csv'
    
    if not os.path.exists(archivo_sin):
        print(f"[ADVERTENCIA] {archivo_sin} no encontrado, omitiendo comparativa.")
        return
    if not os.path.exists(archivo_con):
        print(f"[ADVERTENCIA] {archivo_con} no encontrado, omitiendo comparativa.")
        return
    
    print(f"\nGenerando gráficas comparativas Parte 2 para Caso {caso_numero}...")
    
    df_sin = pd.read_csv(archivo_sin, low_memory=False)
    df_con = pd.read_csv(archivo_con, low_memory=False)
    os.makedirs(carpeta_salida, exist_ok=True)
    
    # Determinar qué módulos usar según el caso
    if caso_numero == 1:
        # Caso 1: foco en el receptor que satura
        modules_cola = 'Network.queue'
        modules_rx = 'Network.nodeRx.rxBuffer'
    else:
        # Caso 2: foco en la cola intermedia que satura
        modules_cola = 'Network.queue'
        modules_rx = 'Network.nodeRx.rxBuffer'
    
    # [Esta función ahora será llamada al final: generar_throughput_comparativo_4curvas()]
    
    # ================ GRÁFICA 2: OCUPACIÓN DE BUFFERS (SIN CONTROL) ================
    print(f"  Procesando buffers sin control...")
    data_tx_sin = parse_omnet_vector(df_sin, 'Network.nodeTx.txBuffer', 'bufferSize')
    data_queue_sin = parse_omnet_vector(df_sin, 'Network.queue', 'bufferSize')
    data_rx_sin = parse_omnet_vector(df_sin, 'Network.nodeRx.rxBuffer', 'bufferSize')
    
    # Gráfica de ocupación TX (sin control)
    plt.figure(figsize=(10, 5))
    for gi, (t, v) in sorted(data_tx_sin.items()):
        if len(t) > 0:
            plt.plot(t, v, linewidth=1.2, label=f'Intervalo: {gi}s')
    plt.title(f'Parte 2 - Caso {caso_numero}: Ocupación Buffer TX (Sin Control)')
    plt.xlabel('Tiempo de Simulación (s)')
    plt.ylabel('Paquetes en Buffer')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig(os.path.join(carpeta_salida, f'Parte2_Caso{caso_numero}_SinControl_Ocupacion_Tx.png'), 
                dpi=300, bbox_inches='tight')
    plt.close()
    
    # Gráfica de descartes (sin control)
    data_drops_queue_sin = parse_omnet_vector(df_sin, 'Network.queue', 'packetDrops')
    data_drops_rx_sin = parse_omnet_vector(df_sin, 'Network.nodeRx.rxBuffer', 'packetDrops')
    
    plt.figure(figsize=(10, 5))
    hay_descartes = False
    for gi, (t, v) in sorted(data_drops_queue_sin.items()):
        if len(v) > 0 and v[-1] > 0:
            plt.plot(t, v, linestyle='--', linewidth=1.5, label=f'Cola Intermedia ({gi})')
            hay_descartes = True
    for gi, (t, v) in sorted(data_drops_rx_sin.items()):
        if len(v) > 0 and v[-1] > 0:
            plt.plot(t, v, linewidth=1.5, label=f'Buffer Receptor ({gi})')
            hay_descartes = True
    
    plt.title(f'Parte 2 - Caso {caso_numero}: Descartes de Paquetes (Sin Control)')
    plt.xlabel('Tiempo de Simulación (s)')
    plt.ylabel('Paquetes Descartados Acumulados')
    if hay_descartes:
        plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig(os.path.join(carpeta_salida, f'Parte2_Caso{caso_numero}_SinControl_Descartes.png'), 
                dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  ✓ Gráficas sin control generadas.")
    
    # ================ GRÁFICA 3: OCUPACIÓN DE BUFFERS (CON CONTROL) ================
    print(f"  Procesando buffers con control...")
    data_tx_con = parse_omnet_vector_any(df_con, ['Network.nodeTx.transport', 'Network.nodeTx.txBuffer'], 'bufferSize')
    data_queue_con = parse_omnet_vector(df_con, 'Network.queue', 'bufferSize')
    data_rx_con = parse_omnet_vector_any(df_con, ['Network.nodeRx.transport', 'Network.nodeRx.rxBuffer'], 'bufferSize')
    
    # Gráfica de ocupación TX (con control)
    plt.figure(figsize=(10, 5))
    hay_datos = False
    for gi, (t, v) in sorted(data_tx_con.items()):
        if len(t) > 0:
            plt.plot(t, v, linewidth=1.2, label=f'Intervalo: {gi}s')
            hay_datos = True
    plt.title(f'Parte 2 - Caso {caso_numero}: Ocupación Buffer TX (Con Control por Ventanas)')
    plt.xlabel('Tiempo de Simulación (s)')
    plt.ylabel('Paquetes en Buffer')
    if hay_datos:
        plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig(os.path.join(carpeta_salida, f'Parte2_Caso{caso_numero}_ConControl_Ocupacion_Tx.png'), 
                dpi=300, bbox_inches='tight')
    plt.close()
    
    # Gráfica de descartes (con control)
    data_drops_queue_con = parse_omnet_vector(df_con, 'Network.queue', 'packetDrops')
    data_drops_rx_con = parse_omnet_vector(df_con, 'Network.nodeRx.rxBuffer', 'packetDrops')
    
    plt.figure(figsize=(10, 5))
    hay_descartes = False
    for gi, (t, v) in sorted(data_drops_queue_con.items()):
        if len(v) > 0 and v[-1] > 0:
            plt.plot(t, v, linestyle='--', linewidth=1.5, label=f'Cola Intermedia ({gi})')
            hay_descartes = True
    for gi, (t, v) in sorted(data_drops_rx_con.items()):
        if len(v) > 0 and v[-1] > 0:
            plt.plot(t, v, linewidth=1.5, label=f'Buffer Receptor ({gi})')
            hay_descartes = True
    
    plt.title(f'Parte 2 - Caso {caso_numero}: Descartes de Paquetes (Con Control por Ventanas)')
    plt.xlabel('Tiempo de Simulación (s)')
    plt.ylabel('Paquetes Descartados Acumulados')
    if hay_descartes:
        plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig(os.path.join(carpeta_salida, f'Parte2_Caso{caso_numero}_ConControl_Descartes.png'), 
                dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  ✓ Gráficas con control generadas.")
    
    # ================ GRÁFICA 4: cwnd (Congestion Window) ================
    print(f"  Extrayendo variables de control (cwnd, inFlight, Delay)...")
    
    data_cwnd = parse_omnet_vector(df_con, 'Network.nodeTx.transport', 'cwnd')
    if data_cwnd and any(len(t) > 0 for t, _ in data_cwnd.values()):
        plt.figure(figsize=(10, 5))
        for gi, (t, v) in sorted(data_cwnd.items()):
            if len(t) > 0:
                plt.plot(t, v, linewidth=1.2, label=f'Intervalo: {gi}s')
        plt.title(f'Parte 2 - Caso {caso_numero}: Ventana de Congestión (cwnd)')
        plt.xlabel('Tiempo de Simulación (s)')
        plt.ylabel('cwnd (paquetes)')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.savefig(os.path.join(carpeta_salida, f'Parte2_Caso{caso_numero}_cwnd.png'), 
                    dpi=300, bbox_inches='tight')
        plt.close()
        print(f"  ✓ Gráfica de cwnd generada.")
    
    # ================ GRÁFICA 5: inFlight ================
    data_inflight = parse_omnet_vector(df_con, 'Network.nodeTx.transport', 'inFlight')
    if data_inflight and any(len(t) > 0 for t, _ in data_inflight.values()):
        plt.figure(figsize=(10, 5))
        for gi, (t, v) in sorted(data_inflight.items()):
            if len(t) > 0:
                plt.plot(t, v, linewidth=1.2, label=f'Intervalo: {gi}s')
        plt.title(f'Parte 2 - Caso {caso_numero}: Paquetes en Vuelo (inFlight)')
        plt.xlabel('Tiempo de Simulación (s)')
        plt.ylabel('inFlight (paquetes)')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.savefig(os.path.join(carpeta_salida, f'Parte2_Caso{caso_numero}_inFlight.png'), 
                    dpi=300, bbox_inches='tight')
        plt.close()
        print(f"  ✓ Gráfica de inFlight generada.")
    
    # ================ GRÁFICA 6: Demora (Delay) ================
    data_delay = parse_omnet_vector(df_con, 'Network.nodeRx.sink', 'Delay')
    if data_delay and any(len(t) > 0 for t, _ in data_delay.values()):
        plt.figure(figsize=(10, 5))
        for gi, (t, v) in sorted(data_delay.items()):
            if len(t) > 0:
                # Mostrar solo los primeros 10000 puntos para evitar saturación
                step = max(1, len(t) // 5000)
                plt.plot(t[::step], v[::step], linewidth=0.8, label=f'Intervalo: {gi}s', alpha=0.7)
        plt.title(f'Parte 2 - Caso {caso_numero}: Demora de Paquetes (Con Control)')
        plt.xlabel('Tiempo de Simulación (s)')
        plt.ylabel('Demora (segundos)')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.savefig(os.path.join(carpeta_salida, f'Parte2_Caso{caso_numero}_Delay.png'), 
                    dpi=300, bbox_inches='tight')
        plt.close()
        print(f"  ✓ Gráfica de demora generada.")
    
    # ================ GRÁFICA 7: Ocupación de Buffers Comparativos (Cola) ================
    if caso_numero == 1:
        # Caso 1: el cuello de botella está en el receptor
        data_bottleneck_sin = parse_omnet_vector(df_sin, 'Network.nodeRx.rxBuffer', 'bufferSize')
        data_bottleneck_con = parse_omnet_vector_any(df_con, ['Network.nodeRx.transport', 'Network.nodeRx.rxBuffer'], 'bufferSize')
        titulo_bottleneck = f'Parte 2 - Caso {caso_numero}: Buffer del Receptor (gi=0.1s) - Comparativa'
        y_label = 'Paquetes en Buffer Rx'
        archivo_bottleneck = f'Parte2_Caso{caso_numero}_OcupacionReceptor_Comparativa.png'
    else:
        # Caso 2: el cuello de botella está en la cola intermedia
        data_bottleneck_sin = parse_omnet_vector(df_sin, 'Network.queue', 'bufferSize')
        data_bottleneck_con = parse_omnet_vector(df_con, 'Network.queue', 'bufferSize')
        titulo_bottleneck = f'Parte 2 - Caso {caso_numero}: Cola Intermedia (gi=0.1s) - Comparativa'
        y_label = 'Paquetes en Cola'
        archivo_bottleneck = f'Parte2_Caso{caso_numero}_OcupacionCola_Comparativa.png'

    if 'gi=0.1' in data_bottleneck_sin and 'gi=0.1' in data_bottleneck_con:
        t_sin, v_sin = data_bottleneck_sin['gi=0.1']
        t_con, v_con = data_bottleneck_con['gi=0.1']
        
        plt.figure(figsize=(12, 6))
        plt.axhline(y=200, color='gray', linestyle='--', linewidth=1.2, label='Capacidad Máxima (200 pkt)', zorder=1)
        if len(t_sin) > 0:
            plt.plot(t_sin, v_sin, linewidth=2.0, label='Sin Control', color='#d62728', alpha=0.95,
                     drawstyle='steps-post', zorder=3)
        if len(t_con) > 0:
            plt.plot(t_con, v_con, linewidth=1.8, label='Con Control (cwnd)', color='#2ca02c', alpha=0.95,
                     drawstyle='steps-post', zorder=4)
        plt.title(titulo_bottleneck)
        plt.xlabel('Tiempo de Simulación (s)')
        plt.ylabel(y_label)
        plt.ylim(-5, 220)
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.savefig(os.path.join(carpeta_salida, archivo_bottleneck), 
                    dpi=300, bbox_inches='tight')
        plt.close()
        print(f"  ✓ Gráfica comparativa del cuello de botella generada.")
    
    # ================ GRÁFICA 8: Ocupación de Buffers Comparativos (Receptor) ================
    data_rx_sin_gi01 = parse_omnet_vector(df_sin, 'Network.nodeRx.rxBuffer', 'bufferSize')
    data_rx_con_gi01 = parse_omnet_vector_any(df_con, ['Network.nodeRx.transport', 'Network.nodeRx.rxBuffer'], 'bufferSize')
    
    if 'gi=0.1' in data_rx_sin_gi01 and 'gi=0.1' in data_rx_con_gi01:
        t_sin, v_sin = data_rx_sin_gi01['gi=0.1']
        t_con, v_con = data_rx_con_gi01['gi=0.1']
        
        plt.figure(figsize=(12, 6))
        if len(t_sin) > 0:
            plt.plot(t_sin, v_sin, linewidth=1.2, label='Sin Control', color='#d62728', alpha=0.8)
        if len(t_con) > 0:
            plt.plot(t_con, v_con, linewidth=1.2, label='Con Control (cwnd)', color='#2ca02c', alpha=0.8)
        plt.axhline(y=200, color='gray', linestyle='--', linewidth=1.5, label='Capacidad Máxima (200 pkt)')
        plt.title(f'Parte 2 - Caso {caso_numero}: Ocupación Buffer Receptor (gi=0.1s) - Comparativa')
        plt.xlabel('Tiempo de Simulación (s)')
        plt.ylabel('Paquetes en Buffer Rx')
        plt.ylim(-5, 220)
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.savefig(os.path.join(carpeta_salida, f'Parte2_Caso{caso_numero}_OcupacionRx_Comparativa.png'), 
                    dpi=300, bbox_inches='tight')
        plt.close()
        print(f"  ✓ Gráfica comparativa de ocupación de receptor generada.")
    
    print(f"✓ Análisis Parte 2 completado para Caso {caso_numero}.\n")


def generar_throughput_comparativo_4curvas(carpeta_salida="graficos"):
    """
    Genera un gráfico único que compare Carga Ofrecida vs Carga Útil Recibida
    con 4 curvas: Caso1 sin control, Caso2 sin control, Caso1 con control, Caso2 con control.
    Extrae datos reales de los archivos CSV.
    """

    print("\nGenerando gráfico combinado de Throughput (4 curvas)...")

    def extraer_goodput(archivo_csv):
        df = pd.read_csv(archivo_csv)
        df_gp = df[df['name'] == 'Goodput (pkt/s)']
        valores = {}
        for _, row in df_gp.iterrows():
            run_id = str(row['run'])
            if "-0-" in run_id:
                valores[10.0] = float(row['value'])
            elif "-1-" in run_id:
                valores[5.0] = float(row['value'])
            elif "-2-" in run_id:
                valores[2.0] = float(row['value'])
            elif "-3-" in run_id:
                valores[1.0] = float(row['value'])
        return valores

    cargas_x = [1.0, 2.0, 5.0, 10.0]
    c1_sin = extraer_goodput('caso1_sin_control.csv')
    c2_sin = extraer_goodput('caso2_sin_control.csv')
    c1_con = extraer_goodput('caso1_con_control.csv')
    c2_con = extraer_goodput('caso2_con_control.csv')

    y_c1_sin = [c1_sin.get(x, np.nan) for x in cargas_x]
    y_c2_sin = [c2_sin.get(x, np.nan) for x in cargas_x]
    y_c1_con = [c1_con.get(x, np.nan) for x in cargas_x]
    y_c2_con = [c2_con.get(x, np.nan) for x in cargas_x]

    limite_fisico = 5.0
    plt.figure(figsize=(10, 6))
    plt.plot(cargas_x, y_c1_sin, marker='o', color='blue', label='Caso 1 (Sin Control)')
    plt.plot(cargas_x, y_c2_sin, marker='s', color='orange', label='Caso 2 (Sin Control)')
    plt.plot(cargas_x, y_c1_con, marker='^', color='green', linestyle='--', linewidth=2, label='Caso 1 (Con Control)')
    plt.plot(cargas_x, y_c2_con, marker='d', color='purple', linestyle='--', linewidth=2, label='Caso 2 (Con Control)')
    plt.axhline(y=limite_fisico, color='red', linestyle=':', linewidth=2, label='Límite Físico Teórico (0.5 Mbps = 5 pkt/s)')
    plt.title('Comparativa de Rendimiento: Carga Ofrecida vs. Carga Útil Recibida')
    plt.xlabel('Carga Ofrecida (Paquetes inyectados por segundo)')
    plt.ylabel('Carga Útil Recibida - Goodput (Paquetes / segundo)')
    plt.xticks(cargas_x)
    plt.yticks([0, 1, 2, 3, 4, 5, 6])
    plt.legend(loc='lower right')
    plt.grid(True, linestyle='--', alpha=0.7)

    os.makedirs(carpeta_salida, exist_ok=True)
    output_file = os.path.join(carpeta_salida, 'Parte2_Throughput_4Curvas_Comparativo.png')
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  ✓ Gráfico de throughput con 4 curvas generado: {output_file}\n")


def generar_parte2_grid(caso_numero, carpeta_salida="graficos"):
    """Genera la figura 3x2 para un caso dado."""
    archivo_sin = f'caso{caso_numero}_sin_control.csv'
    archivo_con = f'caso{caso_numero}_con_control.csv'
    if not os.path.exists(archivo_sin) or not os.path.exists(archivo_con):
        print(f"  [ADVERTENCIA] Faltan CSV para Caso {caso_numero}, omitiendo grid.")
        return

    df_sin = pd.read_csv(archivo_sin, low_memory=False)
    df_con = pd.read_csv(archivo_con, low_memory=False)
    os.makedirs(carpeta_salida, exist_ok=True)

    gi_keys = ["gi=0.1", "gi=0.2", "gi=0.5", "gi=1.0"]
    fig, axes = plt.subplots(2, 3, figsize=(18, 9), sharex=False)
    fig.suptitle(f'Parte 2 - Caso {caso_numero}: Comparativa Sin Control vs Con Control', fontweight='bold')

    if caso_numero == 1:
        módulos = [
            ('Network.nodeTx.txBuffer', 'Buffer Tx'),
            ('Network.queue', 'Cola Intermedia'),
            ('Network.nodeRx.rxBuffer', 'Buffer Rx'),
        ]
        módulos_con = [
            (['Network.nodeTx.transport', 'Network.nodeTx.txBuffer'], 'Buffer Tx'),
            (['Network.queue'], 'Cola Intermedia'),
            (['Network.nodeRx.transport', 'Network.nodeRx.rxBuffer'], 'Buffer Rx'),
        ]
    else:
        módulos = [
            ('Network.nodeTx.txBuffer', 'Buffer Tx'),
            ('Network.queue', 'Cola Intermedia'),
            ('Network.nodeRx.rxBuffer', 'Buffer Rx'),
        ]
        módulos_con = [
            (['Network.nodeTx.transport', 'Network.nodeTx.txBuffer'], 'Buffer Tx'),
            (['Network.queue'], 'Cola Intermedia'),
            (['Network.nodeRx.transport', 'Network.nodeRx.rxBuffer'], 'Buffer Rx'),
        ]

    # Fila superior: sin control
    for col, (module, titulo) in enumerate(módulos):
        ax = axes[0, col]
        data = parse_omnet_vector(df_sin, module, 'bufferSize')
        plotted = False
        for gi in gi_keys:
            if gi in data:
                t, v = data[gi]
                if len(t) > 0:
                    ax.step(t, v, where='post', label=gi, linewidth=1.2)
                    plotted = True
        ax.set_title(f'{titulo} - Sin Control')
        ax.set_xlabel('Tiempo (s)')
        ax.set_ylabel('Paquetes en Buffer')
        ax.set_xlim(0, 200)
        if col == 0:
            ax.legend(loc='upper right') if plotted else None
        ax.grid(True, alpha=0.25)

    # Fila inferior: con control
    for col, (module_list, titulo) in enumerate(módulos_con):
        ax = axes[1, col]
        data = parse_omnet_vector_any(df_con, module_list, 'bufferSize')
        plotted = False
        for gi in gi_keys:
            if gi in data:
                t, v = data[gi]
                if len(t) > 0:
                    ax.step(t, v, where='post', label=gi, linewidth=1.2)
                    plotted = True
        ax.set_title(f'{titulo} - Con Control')
        ax.set_xlabel('Tiempo (s)')
        ax.set_ylabel('Paquetes en Buffer')
        ax.set_xlim(0, 200)
        if col == 0:
            ax.legend(loc='upper right') if plotted else None
        ax.grid(True, alpha=0.25)

    plt.tight_layout(rect=[0, 0, 1, 0.97])
    out = os.path.join(carpeta_salida, f'Parte2_Caso{caso_numero}_Grid3x2.png')
    plt.savefig(out, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  ✓ Grid 3x2 generado: {out}")


def generar_parte2_zoom(caso_numero, carpeta_salida="graficos"):
    """
    Genera figura de Zoom crítico para gi=0.1:
    - Caso 1: subplot izquierdo = Tx (sin vs con), derecho = Rx (sin vs con)
    - Caso 2: subplot izquierdo = Tx (sin vs con), derecho = Queue (sin vs con)
    """
    archivo_sin = f'caso{caso_numero}_sin_control.csv'
    archivo_con = f'caso{caso_numero}_con_control.csv'
    if not os.path.exists(archivo_sin) or not os.path.exists(archivo_con):
        print(f"  [ADVERTENCIA] Faltan CSV para Caso {caso_numero}, omitiendo zoom.")
        return

    df_sin = pd.read_csv(archivo_sin, low_memory=False)
    df_con = pd.read_csv(archivo_con, low_memory=False)
    os.makedirs(carpeta_salida, exist_ok=True)

    # Extraer solo gi=0.1
    tx_sin = parse_omnet_vector(df_sin, 'Network.nodeTx.txBuffer', 'bufferSize').get('gi=0.1', ([], []))
    tx_con = parse_omnet_vector_any(df_con, ['Network.nodeTx.transport', 'Network.nodeTx.txBuffer'], 'bufferSize').get('gi=0.1', ([], []))

    rx_sin = parse_omnet_vector(df_sin, 'Network.nodeRx.rxBuffer', 'bufferSize').get('gi=0.1', ([], []))
    rx_con = parse_omnet_vector_any(df_con, ['Network.nodeRx.transport', 'Network.nodeRx.rxBuffer'], 'bufferSize').get('gi=0.1', ([], []))

    queue_sin = parse_omnet_vector(df_sin, 'Network.queue', 'bufferSize').get('gi=0.1', ([], []))
    queue_con = parse_omnet_vector(df_con, 'Network.queue', 'bufferSize').get('gi=0.1', ([], []))

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    if caso_numero == 1:
        # Tx comparison
        t_s, v_s = tx_sin
        t_c, v_c = tx_con
        if len(t_s) > 0:
            axes[0].step(t_s, v_s, where='post', label='Sin Control', color='#1f77b4')
        if len(t_c) > 0:
            axes[0].step(t_c, v_c, where='post', label='Con Control', color='#2ca02c')
        axes[0].set_title('Caso 1 - Buffer Tx (gi=0.1)')
        axes[0].set_xlabel('Tiempo (s)')
        axes[0].set_ylabel('Paquetes en Buffer')
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)

        # Rx comparison
        t_s, v_s = rx_sin
        t_c, v_c = rx_con
        if len(t_s) > 0:
            axes[1].step(t_s, v_s, where='post', label='Sin Control', color='#1f77b4')
        if len(t_c) > 0:
            axes[1].step(t_c, v_c, where='post', label='Con Control', color='#2ca02c')
        axes[1].set_title('Caso 1 - Buffer Rx (gi=0.1)')
        axes[1].set_xlabel('Tiempo (s)')
        axes[1].legend()
        axes[1].grid(True, alpha=0.3)

        out = os.path.join(carpeta_salida, f'Parte2_Caso{caso_numero}_Zoom_gi01_Tx_Rx.png')

    else:
        # Caso 2: Tx vs Queue
        t_s, v_s = tx_sin
        t_c, v_c = tx_con
        if len(t_s) > 0:
            axes[0].step(t_s, v_s, where='post', label='Sin Control', color='#1f77b4')
        if len(t_c) > 0:
            axes[0].step(t_c, v_c, where='post', label='Con Control', color='#2ca02c')
        axes[0].set_title('Caso 2 - Buffer Tx (gi=0.1)')
        axes[0].set_xlabel('Tiempo (s)')
        axes[0].set_ylabel('Paquetes en Buffer')
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)

        t_s, v_s = queue_sin
        t_c, v_c = queue_con
        if len(t_s) > 0:
            axes[1].step(t_s, v_s, where='post', label='Sin Control', color='#1f77b4')
        if len(t_c) > 0:
            axes[1].step(t_c, v_c, where='post', label='Con Control', color='#2ca02c')
        axes[1].set_title('Caso 2 - Cola Intermedia (gi=0.1)')
        axes[1].set_xlabel('Tiempo (s)')
        axes[1].legend()
        axes[1].grid(True, alpha=0.3)

        out = os.path.join(carpeta_salida, f'Parte2_Caso{caso_numero}_Zoom_gi01_Tx_Queue.png')

    plt.tight_layout()
    plt.savefig(out, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  ✓ Zoom gi=0.1 generado: {out}")



def main():
    """
    Punto de entrada principal del script.
    Uso:
      python analisis.py                    # Genera gráficos de Parte 1 (sin control)
      python analisis.py parte1             # Genera gráficos de Parte 1 (sin control)
      python analisis.py parte2             # Genera gráficos de Parte 2 (con control + comparativas)
      python analisis.py ambas              # Genera ambas partes
    """
    
    modo = sys.argv[1].lower() if len(sys.argv) > 1 else "parte1"
    
    if modo in ["parte1", "p1", ""]:
        print("=" * 70)
        print("ANÁLISIS PARTE 1: Simulaciones Sin Control de Flujo/Congestión")
        print("=" * 70)
        try:
            generar_graficos_caso('caso1_sin_control.csv', 'Caso1_Flujo')
            generar_graficos_caso('caso2_sin_control.csv', 'Caso2_Congestion')
            print("\n[OK] Trazados Parte 1 exportados exitosamente en alta resolución (300 DPI).")
        except Exception as e:
            print(f"[ERROR] Fallo durante la generación Parte 1: {e}")
    
    elif modo in ["parte2", "p2"]:
        print("=" * 70)
        print("ANÁLISIS PARTE 2: Simulaciones Con Control por Ventanas + Comparativas")
        print("=" * 70)
        try:
            generar_graficos_comparativa_sin_con_control(1)
            generar_graficos_comparativa_sin_con_control(2)
            generar_throughput_comparativo_4curvas()
            # Nuevas figuras: grid 3x2 y zoom crítico gi=0.1
            generar_parte2_grid(1)
            generar_parte2_grid(2)
            generar_parte2_zoom(1)
            generar_parte2_zoom(2)
            print("[OK] Trazados Parte 2 exportados exitosamente en alta resolución (300 DPI).")
        except Exception as e:
            print(f"[ERROR] Fallo durante la generación Parte 2: {e}")
    
    elif modo in ["ambas", "a", "both"]:
        print("=" * 70)
        print("ANÁLISIS COMPLETO: Parte 1 + Parte 2")
        print("=" * 70)
        try:
            # Parte 1
            print("\n>>> Ejecutando Parte 1...")
            generar_graficos_caso('caso1_sin_control.csv', 'Caso1_Flujo')
            generar_graficos_caso('caso2_sin_control.csv', 'Caso2_Congestion')
            
            # Parte 2
            print("\n>>> Ejecutando Parte 2...")
            generar_graficos_comparativa_sin_con_control(1)
            generar_graficos_comparativa_sin_con_control(2)
            generar_throughput_comparativo_4curvas()
            # Nuevas figuras: grid 3x2 y zoom crítico gi=0.1
            generar_parte2_grid(1)
            generar_parte2_grid(2)
            generar_parte2_zoom(1)
            generar_parte2_zoom(2)
            
            print("\n[OK] Todos los trazados exportados exitosamente en alta resolución (300 DPI).")
        except Exception as e:
            print(f"[ERROR] Fallo durante la generación: {e}")
    
    else:
        print(f"Uso: python analisis.py [parte1|parte2|ambas]")
        print(f"  parte1 (o p1): Genera gráficas de Parte 1 (sin control)")
        print(f"  parte2 (o p2): Genera gráficas de Parte 2 (con control + comparativas)")
        print(f"  ambas  (o a):  Genera ambas partes")
        print(f"\nModo actual: {modo} (no reconocido)")
        sys.exit(1)


if __name__ == "__main__":
    main()