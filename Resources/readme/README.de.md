<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="cutaway-protocol-dark.svg">
    <img src="cutaway-protocol-light.svg" alt="CutawayProtocol — The shared language of client and server." width="850">
  </picture>
</p>

[![FlatBuffers](https://img.shields.io/badge/FlatBuffers-schema-blue)](../../schema/cutaway.fbs)
[![License](https://img.shields.io/badge/License-MIT-lightgrey)](../../LICENSE)

[English](../../README.md) | [简体中文](README.zh-Hans.md) | [繁體中文](README.zh-Hant.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Español](README.es.md) | [Français](README.fr.md) | **Deutsch**

*Dies ist eine Übersetzung. Bei Abweichungen gilt die [englische README](../../README.md).*

# Cutaway Protocol

Das Wire-Protokoll zwischen **[CutawayServer](https://github.com/nothingsh/CutawayServer)**, einem iOS-SDK, das in die zu untersuchende App eingebettet wird, und **[Cutaway](https://github.com/nothingsh/Cutaway)**, einer macOS-App. Cutaway verbindet sich per TCP mit dem Server, ruft die Layer-Hierarchie, Screenshots, Attribute und Auto-Layout-Constraints der App ab und kann zur Laufzeit der App Attribute ändern und ihre Trait-Umgebung überschreiben.

Dieses Repository ist die einzige maßgebliche Quelle für dieses Protokoll. Es enthält keinen Swift-Code: Beide Seiten binden einen Tag dieses Repositorys als Git-Submodul ein und generieren ihren Code aus dem Schema.

Die [Cutaway-Website](https://nothingsh.github.io/Cutaway/protocol/) erklärt das Protokoll (auf Englisch): eine [Übersicht](https://nothingsh.github.io/Cutaway/protocol/), [welche Versionen zusammenarbeiten](https://nothingsh.github.io/Cutaway/protocol/versions), [eine Gegenstelle implementieren](https://nothingsh.github.io/Cutaway/protocol/implementing) und die [Spezifikation](https://nothingsh.github.io/Cutaway/protocol/spec), erzeugt aus `PROTOCOL.md` dieses Repositorys.

<a id="contents"></a>
## Inhalt

| Pfad | Beschreibung |
|---|---|
| `PROTOCOL.md` | Die normative Spezifikation. Nummerierte Klauseln (`P-TRANS-01`, `P-FRAME-03`, …) sind Anforderungen; alles andere ist Erläuterung. |
| `schema/cutaway.fbs` | Das [FlatBuffers](https://flatbuffers.dev)-Schema. Die Nutzlast jedes Frames ist ein hier definierter `Frame`. |
| `schema/released/` | Ein Snapshot des Schemas für jede veröffentlichte `MAJOR.MINOR`-Version. Wird nach der Veröffentlichung nie mehr geändert. |
| `fixtures/` | Referenz-Frames zum Testen einer Implementierung. `src/` enthält die JSON-Quellen, `bin/` die kompilierten Puffer und die exakten Bytes auf der Leitung. Siehe `fixtures/README.md`. |
| `scripts/` | `verify.sh` ist die Abnahmeprüfung für dieses Repository. Die übrigen Skripte erzeugen die Fixtures und prüfen die Schema-Evolution. |
| `PROTOCOL_VERSION` | Die aktuelle Protokollversion, `MAJOR.MINOR`. |
| `FLATBUFFERS_VERSION`, `FLATC_SHA256` | Das festgelegte `flatc`-Release und die Prüfsumme seiner macOS-Binärdatei. |

<a id="the-protocol-at-a-glance"></a>
## Das Protokoll im Überblick

- **Transport.** Der Server lauscht per TCP, ausschließlich auf Loopback, und probiert der Reihe nach die Ports 48160 bis 48167. Ein Simulator teilt sich das Loopback-Interface mit dem Mac; ein per USB verbundenes Gerät wird über usbmuxd von macOS erreicht, von dem der Server nichts weiß. Es ist jeweils nur ein Client verbunden.
- **Framing.** Ein Frame besteht aus einer 4-Byte-Länge `N` in Little-Endian, gefolgt von `N` Bytes, die einen gewöhnlichen FlatBuffer mit dem Root-Typ `Frame` und dem File Identifier `CTWY` enthalten. Das ist **nicht** das größenpräfixierte Format von FlatBuffers; die `.stream`-Fixtures zeigen die exakten Bytes. `N` darf 256 MiB nicht überschreiten, und ein Empfänger verifiziert den gesamten Puffer, bevor er irgendein Feld liest.
- **Handshake.** Der erste Frame des Clients ist `Hello`; der Server antwortet immer mit seinem eigenen `Hello`. Die Major-Versionen müssen übereinstimmen, sonst schließen beide Seiten die Verbindung. Unterscheiden sich die Minor-Versionen, arbeiten beide Seiten mit der niedrigeren.
- **Anfragen.** Der Client vergibt eine monoton steigende `request_id`. Gewöhnliche Anfragen (`GetAppIcon`, `GetHierarchy`, `GetSubtree`, `SetAttribute`, seit 1.2 auch `GetEnvironment` und `SetEnvironment`) erhalten genau eine Antwort. `GetLayerDetails` ist ein Stream: null oder mehr `LayerDetailsChunk`-Frames, dann ein `StreamEnd`. `Cancel` beendet einen Stream vorzeitig und hat keine eigene Antwort. Der Server bearbeitet Anfragen der Reihe nach.
- **Ereignisse.** Der Server sendet `AppStateChanged` mit `request_id` 0 nach dem Handshake und immer dann, wenn sich der Aktivitätszustand der App ändert.
- **Fehler.** `Error` trägt einen stabilen `ErrorCode` und eine menschenlesbare Meldung. Clients verzweigen anhand des Codes, niemals anhand des Textes.

Jede der obigen Regeln ist eine Klausel in `PROTOCOL.md`; diese Liste dient nur der Orientierung.

<a id="versioning-and-evolution"></a>
## Versionierung und Evolution

Die Protokollversion ist `MAJOR.MINOR` in `PROTOCOL_VERSION`; Releases werden als `vMAJOR.MINOR.PATCH` getaggt. Das Schema entwickelt sich ausschließlich durch Anhängen weiter: Felder am Ende von Tabellen, Member am Ende von Enums und Unions. Structs, der File Identifier und der Root-Typ ändern sich nie. Alles andere erfordert eine neue Major-Version. Ein `PATCH`-Release ändert Formulierungen oder Fixtures, ohne das Schema anzutasten. Während eine Minor-Version in Entwicklung ist, wird sie als `vMAJOR.MINOR.0-dev.N` getaggt; diese Tags dienen nur der Entwicklung, eine ausgelieferte Gegenstelle pinnt einen Release-Tag. Die vollständigen Regeln sind die `P-EVO`-Klauseln in `PROTOCOL.md`.

Das Protokoll ist **bei 1.0 eingefroren**. Ab jetzt wächst das Schema nur noch durch Anhängen, in Minor-Versionen. 1.0 war gegenüber 0.5 eine neue Major-Version: Eine 0.x-Gegenstelle und eine 1.x-Gegenstelle scheitern absichtlich am Handshake.

<a id="implementing-a-peer"></a>
## Eine Gegenstelle implementieren

1. Lesen Sie `PROTOCOL.md` vollständig durch. Die Klauseln sind kurz und verweisen aufeinander.
2. Generieren Sie Code aus `schema/cutaway.fbs` mit dem festgelegten `flatc` (siehe `FLATBUFFERS_VERSION`). `scripts/get-flatc.sh` lädt genau dieses Release nach `.tools/` herunter.
3. Testen Sie gegen `fixtures/bin/`. Jede `.bin`-Datei ist ein Puffer zum Testen der Dekodierung; jede `.stream`-Datei ist eine Richtung eines vollständigen Szenarios zum Testen des Framings. Beachten Sie, dass `flatc` Felder weglässt, die ihrem Standardwert entsprechen; ein Decoder liest sie daher als 0, false oder das erste Member des Enums zurück.
4. Erhöhen Sie das Tabellenlimit des FlatBuffers-Verifiers, falls Ihre Laufzeitumgebung eines hat: Das Protokoll erlaubt Frames mit weit mehr Tabellen, als die meisten Standardwerte zulassen (`P-FRAME-06`).

<a id="verifying-this-repository"></a>
## Dieses Repository verifizieren

```bash
scripts/verify.sh
```

Das Skript lädt das festgelegte `flatc` herunter, kompiliert das Schema, erzeugt alle Fixtures neu und vergleicht das Ergebnis mit `fixtures/bin/`, prüft die Fixtures gegen die Klauseln, die das Schema nicht ausdrücken kann, und prüft, ob das aktuelle Schema eine zulässige Weiterentwicklung des neuesten veröffentlichten Snapshots ist. Es benötigt `bash`, `curl` und `python3` und läuft nur unter macOS: Die Fixture-Prüfungen dekomprimieren Bilder mit `compression_tool`, und `get-flatc.sh` lädt den macOS-Build von `flatc` herunter.

Nach Änderungen an `fixtures/src/` oder am Schema:

```bash
scripts/build-fixtures.sh fixtures/bin
```

<a id="license"></a>
## Lizenz

MIT. Siehe `LICENSE`.
