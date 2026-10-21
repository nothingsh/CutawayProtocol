<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="cutaway-protocol-dark.svg">
    <img src="cutaway-protocol-light.svg" alt="CutawayProtocol — The shared language of client and server." width="850">
  </picture>
</p>

[![FlatBuffers](https://img.shields.io/badge/FlatBuffers-schema-blue)](../../schema/cutaway.fbs)
[![License](https://img.shields.io/badge/License-MIT-lightgrey)](../../LICENSE)

[English](../../README.md) | [简体中文](README.zh-Hans.md) | [繁體中文](README.zh-Hant.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | **Español** | [Français](README.fr.md) | [Deutsch](README.de.md)

*Esta es una traducción. En caso de discrepancia, prevalece el [README en inglés](../../README.md).*

# Cutaway Protocol

El protocolo de comunicación entre **[CutawayServer](https://github.com/nothingsh/CutawayServer)**, un SDK de iOS integrado en la app que se inspecciona, y **[Cutaway](https://github.com/nothingsh/Cutaway)**, una app de macOS. Cutaway se conecta al servidor por TCP y obtiene la jerarquía de capas de la app, capturas de pantalla, atributos y restricciones de Auto Layout, y puede modificar atributos y sobrescribir el entorno de rasgos (trait environment) de la app mientras se ejecuta.

Este repositorio es la única fuente de verdad de ese protocolo. No contiene código Swift: ambos extremos fijan una etiqueta de este repositorio como submódulo de git y generan su código a partir del schema.

El [sitio web de Cutaway](https://nothingsh.github.io/Cutaway/protocol/) tiene una guía del protocolo (en inglés): una [introducción](https://nothingsh.github.io/Cutaway/protocol/), [qué versiones funcionan juntas](https://nothingsh.github.io/Cutaway/protocol/versions), [cómo implementar un extremo](https://nothingsh.github.io/Cutaway/protocol/implementing) y la [especificación](https://nothingsh.github.io/Cutaway/protocol/spec), generada a partir del `PROTOCOL.md` de este repositorio.

<a id="contents"></a>
## Contenido

| Ruta | Qué es |
|---|---|
| `PROTOCOL.md` | La especificación normativa. Las cláusulas numeradas (`P-TRANS-01`, `P-FRAME-03`, …) son requisitos; todo lo demás es explicación. |
| `schema/cutaway.fbs` | El schema de [FlatBuffers](https://flatbuffers.dev). La carga útil de cada trama es un `Frame` definido aquí. |
| `schema/released/` | Una instantánea del schema para cada `MAJOR.MINOR` publicado. Nunca se edita tras su publicación. |
| `fixtures/` | Tramas de referencia para probar una implementación. `src/` contiene las fuentes JSON y `bin/`, los búferes compilados y los bytes exactos que viajan por la red. Véase `fixtures/README.md`. |
| `scripts/` | `verify.sh` es el control de aceptación de este repositorio. Los demás scripts generan los fixtures y comprueban la evolución del schema. |
| `PROTOCOL_VERSION` | La versión actual del protocolo, `MAJOR.MINOR`. |
| `FLATBUFFERS_VERSION`, `FLATC_SHA256` | La versión fijada de `flatc` y la suma de comprobación de su binario para macOS. |

<a id="the-protocol-at-a-glance"></a>
## El protocolo de un vistazo

- **Transporte.** El servidor escucha por TCP, solo en loopback, probando los puertos del 48160 al 48167 en orden. Un simulador comparte el loopback del Mac; a un dispositivo conectado por USB se llega a través de usbmuxd de macOS, del que el servidor no sabe nada. Un solo cliente a la vez.
- **Entramado.** Una trama es una longitud `N` de 4 bytes en little-endian seguida de `N` bytes que contienen un FlatBuffer ordinario con tipo raíz `Frame` e identificador de archivo `CTWY`. **No** es el formato con prefijo de tamaño de FlatBuffers; los fixtures `.stream` muestran los bytes exactos. `N` no puede superar 256 MiB, y el receptor verifica el búfer completo antes de leer cualquier campo.
- **Handshake.** La primera trama del cliente es `Hello`; el servidor responde siempre con su propio `Hello`. Las versiones mayores deben coincidir; de lo contrario, ambos lados cierran la conexión. Cuando las versiones menores difieren, ambos lados trabajan con la más baja.
- **Peticiones.** El cliente asigna un `request_id` monótonamente creciente. Las peticiones ordinarias (`GetAppIcon`, `GetHierarchy`, `GetSubtree`, `SetAttribute` y, desde 1.2, `GetEnvironment` y `SetEnvironment`) reciben exactamente una respuesta. `GetLayerDetails` es un flujo: cero o más tramas `LayerDetailsChunk` y, después, un `StreamEnd`. `Cancel` termina un flujo de forma anticipada y no tiene respuesta propia. El servidor atiende las peticiones en orden.
- **Eventos.** El servidor envía `AppStateChanged` con `request_id` 0 después del handshake y cada vez que cambia el estado activo de la app.
- **Errores.** `Error` incluye un `ErrorCode` estable y un mensaje legible por humanos. Los clientes deciden en función del código, nunca del texto.

Cada regla anterior es una cláusula de `PROTOCOL.md`; esta lista solo sirve de orientación.

<a id="versioning-and-evolution"></a>
## Versionado y evolución

La versión del protocolo es `MAJOR.MINOR` en `PROTOCOL_VERSION`; las publicaciones se etiquetan como `vMAJOR.MINOR.PATCH`. El schema evoluciona solo por adición: campos al final de las tablas, miembros al final de los enums y las uniones. Los structs, el identificador de archivo y el tipo raíz nunca cambian. Cualquier otro cambio supone subir la versión mayor. Una publicación `PATCH` cambia la redacción o los fixtures sin tocar el schema. Mientras una versión menor está en desarrollo se etiqueta como `vMAJOR.MINOR.0-dev.N`; esas etiquetas son solo para desarrollo, y un extremo que se publica fija una etiqueta de publicación. Las reglas completas son las cláusulas `P-EVO` de `PROTOCOL.md`.

El protocolo está **congelado en 1.0**. A partir de ahora el esquema solo crece añadiendo, en versiones menores. La 1.0 subió la versión mayor respecto a la 0.5: un extremo 0.x y uno 1.x fallan el handshake por diseño.

<a id="implementing-a-peer"></a>
## Implementar un extremo

1. Leer `PROTOCOL.md` de principio a fin. Las cláusulas son breves y tienen referencias cruzadas.
2. Generar el código a partir de `schema/cutaway.fbs` con el `flatc` fijado (véase `FLATBUFFERS_VERSION`). `scripts/get-flatc.sh` descarga exactamente esa versión en `.tools/`.
3. Probar con `fixtures/bin/`. Cada `.bin` es un búfer para probar la decodificación; cada `.stream` es una dirección de un escenario completo para probar el entramado. Conviene recordar que `flatc` omite los campos iguales a su valor por defecto, de modo que un decodificador los lee como 0, false o el primer miembro del enum.
4. Elevar el límite de tablas del verificador de FlatBuffers si el runtime tiene uno: el protocolo admite tramas con muchas más tablas que la mayoría de los valores por defecto (`P-FRAME-06`).

<a id="verifying-this-repository"></a>
## Verificar este repositorio

```bash
scripts/verify.sh
```

Descarga el `flatc` fijado, compila el schema, regenera todos los fixtures y compara el resultado con `fixtures/bin/`, comprueba los fixtures frente a las cláusulas que el schema no puede expresar y comprueba que el schema actual es una evolución permitida de la última instantánea publicada. Necesita `bash`, `curl` y `python3`, y solo funciona en macOS: las comprobaciones de fixtures descomprimen imágenes con `compression_tool`, y `get-flatc.sh` descarga la compilación de `flatc` para macOS.

Después de editar `fixtures/src/` o el schema:

```bash
scripts/build-fixtures.sh fixtures/bin
```

<a id="license"></a>
## Licencia

MIT. Véase `LICENSE`.
