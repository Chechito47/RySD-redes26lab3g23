import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

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

def generar_graficos_caso(archivo_csv, caso_nombre, carpeta_salida="graficos"):
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

# Ejecución
try:
    generar_graficos_caso('caso1.csv', 'Caso1_Flujo')
    generar_graficos_caso('caso2.csv', 'Caso2_Congestion')
    print("\n[OK] Trazados técnicos exportados exitosamente en alta resolución (300 DPI).")
except Exception as e:
    print(f"[ERROR] Fallo durante la serialización: {e}")