# Análisis de origen

Fuente: https://www.instagram.com/reel/DfXKRDQRBS_/

### Método
El video ofrece criterios reutilizables para especificar movimiento en interfaces: curvas según el tipo de transición, tiempos relativos, continuidad espacial, coordinación de estados y respuesta a acciones. Sirve a agentes que diseñan o revisan interacciones. Los valores numéricos son recomendaciones del creador, no estándares ni garantías de usabilidad.

### Evidencia
La transcripción contiene reglas independientes y suficientemente concretas para construir una skill. Las instrucciones transforman esas reglas en decisiones y una tabla verificable, sin atribuir contenido visual al video. El ejemplo de salida de 160 ms se calcula a partir de la proporción indicada; no es un ejemplo narrado.

### Viabilidad técnica
No se mencionan plataformas, herramientas ni comandos concretos. La skill produce una especificación independiente del framework, por lo que no requiere comprobar una API esencial ni se aportan fuentes técnicas externas. La reutilización de un identificador de layout mencionada en [00:50] queda sin verificar: depende de un entorno no identificado y no se presenta como capacidad universal. Antes de implementar deben verificarse las APIs del entorno elegido; si faltan efectos, el flujo puede degradarse a un fundido simple o una actualización inmediata. Movimiento reducido y legibilidad se añaden como salvaguardas editoriales, no como afirmaciones del video.

### Vacíos
Se omiten las frases de [00:31] sobre «spring balance» y de [00:34] sobre «handheld animation» por su significado incierto. También se omiten como reglas operativas el estiramiento de knobs y el desfase al asentarse detalles de [00:10], cuyo contexto es insuficiente. Estos vacíos no impiden aplicar el método principal. No se especifican curvas numéricas, amplitud del pulso ni parámetros de desenfoque; deben definirse y validarse por caso.

## Evidencia de la transcripción

- [00:00] — Recomienda ease-out para entradas y duraciones de 150–250 ms para desplegables.
- [00:05] — Propone desfases de 30 ms entre filas y escala 0,97 para botones presionados.
- [00:14] — Sugiere trayectorias en arco y un pulso para confirmar éxito.
- [00:19] — Propone ease-in-out para movimientos en pantalla y escala inicial 0,95 para popovers.
- [00:24] — Sitúa el origen de la transición de entrada en el disparador.
- [00:28] — Dirige la transición de salida hacia el disparador.
- [00:34] — Recomienda salidas aproximadamente un 20 % más cortas que las entradas.
- [00:40] — Propone solapar la entrada del nuevo estado con la salida del anterior y usar máscaras para revelados y cambios de color.
- [00:50] — Menciona reutilizar un identificador de layout entre objetos compartidos, sin identificar el framework necesario.

## Revisión

Borrador generado automáticamente. Verifica fidelidad, vigencia técnica y derechos antes de fusionar.
