---
name: pulir-interfaces-ia
description: "Invoca esta skill al revisar una interfaz generada con IA que necesita una jerarquía más clara, componentes coherentes o mejor respuesta a las acciones del usuario. Aplica 20 criterios para diagnosticar, corregir y verificar el diseño."
---

# Pulir interfaces generadas con IA

## Preparar la revisión

Parte de una captura, un prototipo o una interfaz navegable. Identifica su audiencia, la tarea principal, la función que conviene destacar y la acción que debe resultar más visible. Pregunta solo por los datos imprescindibles que el material no permita deducir. Si existe un sistema de diseño, úsalo como referencia. Registra una vista inicial para comparar los cambios.

## Revisar y corregir

Marca cada criterio como aplicable, no aplicable o pendiente de verificar. Prioriza los hallazgos que dificulten entender el producto, reconocer la acción principal, leer el contenido o saber qué ocurrió después de interactuar. Si el encargo autoriza cambios, aplica la corrección más pequeña que resuelva cada hallazgo prioritario.

### Contenido y jerarquía

1. Retira insignias de relleno. Conserva las que comuniquen un estado o una novedad relevante para la tarea.
2. Elimina rótulos que repitan un encabezado o contenido evidente. Conserva las etiquetas que identifican campos o controles.
3. Quita cursivas arbitrarias de los titulares. Conserva el énfasis cuando cambie la lectura o exprese un significado.
4. Reserva la tipografía monoespaciada para contenido que la justifique, como código o comandos mostrados en pantalla. Mantén la tipografía del titular coherente.
5. Reutiliza los componentes y valores del sistema de diseño para unificar controles equivalentes y mantener visibles sus distintas prioridades.
6. Muestra el producto en uso mediante una vista representativa o una secuencia breve de entrada y resultado. Usa datos aprobados o de ejemplo.
7. Da más espacio y peso visual a la función principal cuando compita con funciones secundarias de igual tamaño.
8. Acerca los elementos relacionados y deja más separación entre grupos. Revisa si el espaciado permite prescindir de divisiones puramente decorativas.
9. Sustituye titulares vagos por una descripción concreta de lo que el producto entrega. Por ejemplo, «Respuestas con citas de artículos científicos» describe un resultado reconocible.
10. Da prioridad visual a la llamada a la acción principal y usa un texto que anticipe qué ocurrirá al activarla.

### Consistencia y legibilidad

11. Usa un color de acento para un papel definido, como señalar la acción principal. Conserva otra señal cuando el color comunique un estado.
12. Unifica familia, tamaño óptico y grosor de trazo de iconos equivalentes.
13. Retira bordes brillantes, sombras u otros adornos que compitan con el contenido o la acción. Conserva los indicadores funcionales de foco, selección y estado.
14. Para esquinas circulares anidadas con separación uniforme, calcula el radio interior restando al radio exterior la distancia real entre ambos contornos. Usa cero si la resta es negativa y revisa la forma renderizada. Con una separación de 8 px y un radio exterior de 20 px, el radio interior es de 12 px.
15. Mejora el contraste del texto con su fondo real. Comprueba el contraste con el criterio de accesibilidad aplicable, incluidos los textos secundarios que el usuario necesita leer.
16. Ajusta el ancho o la composición de los titulares para mantener juntas las frases y evitar palabras aisladas. Comprueba los saltos en anchos estrechos y amplios.
17. Revisa la alineación óptica de formas asimétricas. Por ejemplo, ajusta el triángulo de reproducción dentro del círculo hasta que se perciba centrado.
18. Usa cifras tabulares cuando los números cambien o se comparen en columnas. Comprueba que la fuente las admita y que valores con igual cantidad de dígitos no desplacen el contenido vecino.

### Estados y respuesta

19. Muestra un estado de carga mientras esperas datos o una acción asíncrona. Comprueba la transición al resultado y la salida si la operación falla.
20. Usa animación breve para comunicar un cambio útil, como confirmar que se añadió un artículo. Verifica que la confirmación también se entienda con movimiento reducido o sin animación.

## Verificar y entregar

Compara antes y después en las mismas vistas y estados. Comprueba que se distingan la función y la acción principales, que el texto sea legible y que los controles conserven su comportamiento. Si tienes acceso a una interfaz navegable, prueba los estados asíncronos con una espera perceptible. Con capturas, limita la verificación a lo visible y anota las interacciones pendientes. Entrega los hallazgos priorizados, las correcciones aplicadas o propuestas y la evidencia disponible para revisión humana.
