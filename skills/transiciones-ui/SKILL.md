---
name: transiciones-ui
description: "Invoca esta skill al diseñar o revisar animaciones de menús, botones, listas, pestañas, elementos arrastrables y transiciones entre estados. Diagnostica cada interacción con un catálogo de 20 comparaciones de antes y después."
---

## Identifica la interacción

**Adaptación editorial.** Pide una captura, una grabación o una descripción reproducible del comportamiento actual si falta. Identifica el componente, el disparador, los estados inicial y final y, si te piden implementar, el stack disponible. Recorre el catálogo en orden y aplica los ajustes que correspondan al comportamiento observado. Usa los valores de los ejemplos como puntos de partida.

## Catálogo de ajustes

1. **Entradas con `ease-out`.** Antes, el menú Options entra con `ease-in` en 250 ms. Después, entra con `ease-out` y conserva los 250 ms.
2. **Desplegables de 150–250 ms.** Antes, el menú Options tarda 600 ms. Después, la demostración usa 200 ms.
3. **Aparición escalonada de filas.** Antes, Overview, Activity, Members y Settings aparecen con 200 ms entre filas. Después, usa 30 ms entre inicios consecutivos. En la captura comparativa, el primer panel todavía muestra solo Overview y el segundo ya muestra las cuatro filas.
4. **Escala al presionar.** Antes, Save changes carece de respuesta visual al presionar. Después, reduce el botón a `scale(0.97)` al presionar y recupera su tamaño al soltar. El ejemplo rotula 150 ms para el cambio de escala.
5. **Estiramiento del pomo en movimiento.** Antes, el pomo conserva un círculo rígido. Después, estíralo un 12 % en la dirección del desplazamiento y compensa el eje perpendicular para conservar el área. **Adaptación editorial.** Puedes usar factores `1.12` y `1 / 1.12` durante el movimiento y volver a escala normal al detenerse.
6. **Reposo escalonado de detalles secundarios.** Antes, la tarjeta New message y su insignia se detienen juntas. Después, haz que la insignia termine de asentarse 50 ms después de la tarjeta. Aquí se escalona el final del movimiento. L3 escalona la aparición de filas.
7. **Trayectorias en arco.** Antes, la ficha File viaja de From a To en línea recta. Después, conserva los extremos y recorre un arco. El ejemplo lo rotula como de 32 px y deja abierta la geometría exacta.
8. **Un pulso al confirmar éxito.** Antes, el botón pasa de Save a Saved y solo cambia la etiqueta. Después, conserva Saved y acompaña la confirmación con un único pulso.
9. **Desplazamientos en pantalla con `ease-in-out`.** Antes, el control Move se desplaza de forma lineal en 300 ms. Después, usa `ease-in-out` con el mismo recorrido y duración.
10. **Escala inicial del popover.** Antes, el menú Options abre de `scale(0)` a `scale(1)`. Después, abre de `scale(0.95)` a `scale(1)`.
11. **Entrada anclada al activador.** Antes, Options abre con `transform-origin: center`. Después, sitúa el origen cerca del control que abre el menú. En esa disposición es `top right`.
12. **Salida hacia el activador.** Antes, el menú se desvanece con origen central. Después, dirige el cierre hacia el control activador, que en el ejemplo muestra Close.
13. **Transiciones habituales sin rebote.** Antes, la tarjeta Project settings oscila por subamortiguación. Después, haz que alcance su posición final sin sobrepasarla.
14. **Seguimiento directo durante el agarre.** Antes, la interpolación deja el pomo del deslizador rezagado respecto al puntero. Después, actualiza su posición directamente con el puntero mientras se mantiene agarrado, dentro del recorrido normal.
15. **Salidas aproximadamente un 20 % más cortas.** Antes, el menú usa 250 ms tanto al abrir como al cerrar. Después, conserva los 250 ms de entrada y reduce la salida a 200 ms.
16. **Solapamiento entre estados.** Antes, el botón pasa de Save a un instante sin texto y luego a Saved. Después, empieza a mostrar Saved mientras sale Save.
17. **Recortes para revelar contenido y máscaras para el color.** Antes, el ejemplo de Notes y Files desvanece el contenido de Project brief y funde el texto de las pestañas. Después, revela el contenido con un recorte y usa una máscara sobre el texto para que el color cambie conforme avanza la transición.
18. **Fundido entre iconos con escala y desenfoque.** Antes, el icono de copiar se sustituye de golpe por una marca de verificación. Después, funde ambos iconos mediante opacidad y acompaña el intercambio con cambios de escala y desenfoque.
19. **Cesión elástica al rebasar un límite de arrastre.** Antes, el elemento se detiene en seco en la línea Limit. Después, permite que la sobrepase con desplazamiento adicional atenuado a medida que el puntero se aleja. Aplica esa atenuación fuera del límite y conserva el seguimiento directo de L14 dentro del recorrido.
20. **Identificador de layout compartido.** Antes, Project brief se reemplaza por una tarjeta separada. Después, asigna el mismo identificador de layout a las representaciones compacta y expandida para que la transición muestre cómo se expande el mismo objeto. Confirma cómo vincula ambas representaciones el stack elegido antes de proponer una API concreta.

## Verifica la salida

**Adaptación editorial.** Reproduce el antes y el después con el mismo disparador. Revisa el inicio, un punto intermedio y el final. Según los ajustes aplicados, comprueba los tiempos relativos, el origen junto al activador, el asentamiento sin rebote, la confirmación con un solo pulso, el solapamiento sin un intervalo vacío o la relación entre puntero y elemento dentro y fuera de los límites. Para un elemento compartido, comprueba que se perciba la continuidad entre sus dos estados. Entrega el diagnóstico, los ajustes aplicados o propuestos y las comprobaciones que queden pendientes.
