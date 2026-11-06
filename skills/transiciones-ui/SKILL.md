---
name: transiciones-ui
description: "Invoca esta skill al definir o revisar animaciones de una interfaz. Convierte entradas, salidas, cambios de estado y gestos en una especificación de movimiento verificable."
---

Define una especificación de movimiento para el flujo solicitado usando estos criterios como puntos de partida, no como valores universales.

1. Identifica los elementos, sus estados inicial y final, el disparador de cada transición y su propósito. Si faltan, pide el flujo o componente y el comportamiento esperado. Pregunta por el framework únicamente si se requiere implementación.
2. Para entradas, usa desaceleración al final (ease-out). Como referencias iniciales, prueba desplegables de 150–250 ms y popovers que comiencen a escala 0,95. Para movimientos de elementos ya visibles, considera aceleración y desaceleración (ease-in-out).
3. Mantén la relación espacial con el disparador: abre desde su ubicación y cierra hacia ella. Prueba salidas aproximadamente un 20 % más cortas que las entradas. Si la entrada dura 200 ms, la salida de referencia será de 160 ms.
4. Coordina conjuntos y cambios de estado: prueba desfases de 30 ms entre filas y solapa la llegada del estado nuevo con la salida del anterior. Usa máscaras cuando ayuden a revelar contenido o a delimitar cambios de color.
5. Añade respuesta localizada cuando aporte información: escala de botón 0,97 mientras se presiona y un pulso breve para confirmar éxito. Considera arcos para desplazamientos de objetos y fundidos cruzados para cambios de icono; escala y desenfoque son opciones que deben evaluarse por legibilidad.
6. Verifica la implementación antes de proponer APIs. Si el entorno no permite máscaras, desenfoque o transiciones compartidas, conserva el cambio de estado con un fundido simple o una actualización inmediata. No supongas que un identificador de layout existe en todos los frameworks.
7. Entrega una tabla con elemento, disparador, estados, duración, curva, origen/destino, desfase y alternativa simplificada. Señala qué valores proceden de estas referencias y cuáles se ajustaron al caso.
8. Incluye criterios de aceptación observables: relación espacial con el disparador, tiempos y desfases especificados, continuidad entre estados y legibilidad. Como salvaguarda adicional, contempla movimiento reducido y comprueba que la información de éxito siga siendo perceptible sin animación. Si solo produces una especificación, deja explícito que falta validarla en la interfaz real.
