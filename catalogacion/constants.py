# Vocabulario controlado de instrumentos / voces
# Fuente de verdad: este archivo. El modelo Instrumento persiste entradas
# adicionales agregadas desde el admin, pero los choices base del formulario
# vienen de aquí y NO dependen de que las migraciones de seed hayan corrido.

INSTRUMENTOS = [
    # Voces
    ('Cantante', 'voces'),
    ('Soprano', 'voces'),
    ('Mezzosoprano', 'voces'),
    ('Alto', 'voces'),
    ('Tenor', 'voces'),
    ('Barítono', 'voces'),
    ('Bajo', 'voces'),
    # Teclados
    ('Piano', 'teclados'),
    ('Órgano', 'teclados'),
    # Cuerdas
    ('Violín', 'cuerdas'),
    ('Viola', 'cuerdas'),
    ('Violonchelo', 'cuerdas'),
    ('Contrabajo', 'cuerdas'),
    ('Guitarra', 'cuerdas'),
    ('Requinto', 'cuerdas'),
    ('Arpa', 'cuerdas'),
    ('Mandolina', 'cuerdas'),
    ('Charango', 'cuerdas'),
    # Vientos Madera
    ('Flauta', 'vientos_madera'),
    ('Flauta travesera', 'vientos_madera'),
    ('Flauta piccolo', 'vientos_madera'),
    ('Flauta dulce', 'vientos_madera'),
    ('Oboe', 'vientos_madera'),
    ('Corno inglés', 'vientos_madera'),
    ('Clarinete', 'vientos_madera'),
    ('Clarinete bajo', 'vientos_madera'),
    ('Fagot', 'vientos_madera'),
    ('Contrafagot', 'vientos_madera'),
    # Vientos Metal
    ('Trompeta', 'vientos_metal'),
    ('Corno', 'vientos_metal'),
    ('Trombón', 'vientos_metal'),
    ('Tuba', 'vientos_metal'),
    ('Corneta', 'vientos_metal'),
    ('Fliscorno', 'vientos_metal'),
    # Percusión
    ('Timbales', 'percusion'),
    ('Xilófono', 'percusion'),
    ('Vibráfono', 'percusion'),
    ('Glockenspiel', 'percusion'),
    ('Campanas', 'percusion'),
    # Otros
    ('Armónica', 'otros'),
    ('Acordeón', 'otros'),
    ('Otro', 'otros'),
]
