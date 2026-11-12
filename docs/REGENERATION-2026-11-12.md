# Regeneración y contraste de siete borradores — 12 de noviembre de 2026

## Qué se cambió

El generador ahora construye primero un mapa de la tesis, el formato y cada enseñanza del video, con evidencia de audio o visual. A partir de ese mapa redacta la skill. Una revisión separada comprueba que la skill conserve las enseñanzas, su orden, sus ejemplos y sus límites, e identifica adaptaciones editoriales. Si encuentra una pérdida material, el sistema corrige una vez y vuelve a revisar. Un resultado pendiente no actualiza el PR anterior.

Los siete PR abiertos se regeneraron desde sus transcripciones y frames locales; el PR #1 también obtuvo frames por primera vez. Las versiones anteriores quedaron en `.local-state/jobs/ID/history/`, que no se publica. Cada PR continúa **abierto como borrador**. `pass` significa que el revisor automático declaró cobertura de todas las enseñanzas del mapa; todavía corresponde revisión humana antes de fusionar.

| PR | Antes | Ahora | Correspondencia declarada | Mejora principal |
| --- | --- | --- | --- | --- |
| [#1](https://github.com/ETfromthemoon/reel-skill-factory/pull/1) | Transiciones de UI: selección de reglas basada en audio; 9 citas | 20 ajustes de microinteracciones; 25 citas y 37 frames | 20/20, `pass` | Recupera la lista completa, incluidos rebote, seguimiento durante arrastre, estiramiento del pomo y detalles que el audio anterior dejaba ambiguos. |
| [#3](https://github.com/ETfromthemoon/reel-skill-factory/pull/3) | Regla general de fotografía y acción; 8 citas | Cuatro comparaciones distintas; 9 citas | 4/4, `pass` | Separa reserva, producto, suscripción y perfil, con las transformaciones particulares de cada uno. |
| [#4](https://github.com/ETfromthemoon/reel-skill-factory/pull/4) | Gancho con mecanismo concreto; 10 citas | Reescritura sucesiva del mismo ejemplo; 18 citas | 5/5, `pass` | Conserva las cinco revisiones y deja abierta la elección del concepto psicológico; no trata su eficacia como demostrada. |
| [#5](https://github.com/ETfromthemoon/reel-skill-factory/pull/5) | Catálogo combinado con un proceso de elección; 23 citas | Catálogo de 22 tratamientos en el orden del Reel; 23 citas | 22/22, `pass` | Da protagonismo a lo que realmente muestra el video y etiqueta la selección y la prueba de legibilidad como adaptaciones. |
| [#6](https://github.com/ETfromthemoon/reel-skill-factory/pull/6) | Diagnóstico general del abandono; 9 citas | Cuatro motivos separados; 14 citas | 4/4, `pass` | Mantiene confusión, falta de motivo para seguir, esfuerzo y familiaridad como preguntas diagnósticas, sin afirmar causalidad medida. |
| [#7](https://github.com/ETfromthemoon/reel-skill-factory/pull/7) | Checklist de interfaz en tres pasadas; 23 citas | 20 ajustes independientes con sus ejemplos; 34 citas | 20/20, `pass` | Recupera el carácter de lista de 20 del video; distingue lo visible de carga y movimiento que un frame fijo no prueba. |
| [#10](https://github.com/ETfromthemoon/reel-skill-factory/pull/10) | Plantilla de ocho piezas; 11 citas | Ocho piezas con mapa y revisión; 19 citas | 8/8, `pass` | Precisa el orden y los ejemplos, y marca como editorial dónde resolver los bucles y cómo revisar un borrador. |

## Criterio del contraste

Para cada caso se compararon el `result.json` anterior conservado en `history/` y el nuevo `result.json`, además de la fuente publicada en el mismo PR. Se revisaron tesis, número y orden de enseñanzas, citas, decisiones editoriales y veredicto automático. El aumento de longitud o de citas es descriptivo: no demuestra por sí solo mayor utilidad.

## Límites y revisión pendiente

- El control estructural verifica IDs y marcas de tiempo, no la verdad semántica de cada afirmación. La revisión semántica la hace otro pase del modelo y puede equivocarse.
- Los frames son muestras estáticas. No certifican la duración, las curvas de animación, los clics ni las respuestas reales de usuarios. Esto es especialmente relevante para los PR #1 y #7.
- En #3, #4, #5, #6 y #7 hay pasajes de transcripción inciertos; las imágenes aclaran parte del contenido, pero no sustituyen la pista sonora original.
- Las reglas añadidas para poder aplicar una enseñanza a un trabajo nuevo se identifican como adaptaciones editoriales en la fuente de cada PR. La revisión humana debe comprobar que no alteren la intención del creador ni presenten promesas sin sustento.
- Ninguno de estos PR se fusionó en `main`; las skills siguen siendo borradores para revisión.
