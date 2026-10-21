<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="cutaway-protocol-dark.svg">
    <img src="cutaway-protocol-light.svg" alt="CutawayProtocol — The shared language of client and server." width="850">
  </picture>
</p>

[![FlatBuffers](https://img.shields.io/badge/FlatBuffers-schema-blue)](../../schema/cutaway.fbs)
[![License](https://img.shields.io/badge/License-MIT-lightgrey)](../../LICENSE)

[English](../../README.md) | [简体中文](README.zh-Hans.md) | [繁體中文](README.zh-Hant.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Español](README.es.md) | **Français** | [Deutsch](README.de.md)

*Ce document est une traduction. En cas de divergence, le [README en anglais](../../README.md) fait foi.*

# Cutaway Protocol

Le protocole réseau entre **[CutawayServer](https://github.com/nothingsh/CutawayServer)**, un SDK iOS intégré à l'application inspectée, et **[Cutaway](https://github.com/nothingsh/Cutaway)**, une application macOS. Cutaway se connecte au serveur via TCP et récupère la hiérarchie des calques de l'application, des captures d'écran, les attributs et les contraintes Auto Layout ; il peut aussi modifier les attributs et remplacer l'environnement de traits de l'application pendant son exécution.

Ce dépôt est l'unique source de référence de ce protocole. Il ne contient aucun code Swift : les deux extrémités épinglent un tag de ce dépôt sous forme de sous-module git et génèrent leur code à partir du schéma.

Le [site web de Cutaway](https://nothingsh.github.io/Cutaway/protocol/) propose un guide du protocole (en anglais) : une [vue d'ensemble](https://nothingsh.github.io/Cutaway/protocol/), [quelles versions fonctionnent ensemble](https://nothingsh.github.io/Cutaway/protocol/versions), [implémenter un pair](https://nothingsh.github.io/Cutaway/protocol/implementing) et la [spécification](https://nothingsh.github.io/Cutaway/protocol/spec), générée à partir du `PROTOCOL.md` de ce dépôt.

<a id="contents"></a>
## Contenu

| Chemin | Description |
|---|---|
| `PROTOCOL.md` | La spécification normative. Les clauses numérotées (`P-TRANS-01`, `P-FRAME-03`, …) sont des exigences ; tout le reste est explicatif. |
| `schema/cutaway.fbs` | Le schéma [FlatBuffers](https://flatbuffers.dev). La charge utile de chaque trame est une `Frame` définie ici. |
| `schema/released/` | Un instantané du schéma pour chaque `MAJOR.MINOR` publiée. Jamais modifié après publication. |
| `fixtures/` | Des trames de référence pour tester une implémentation. `src/` contient les sources JSON, `bin/` les tampons compilés et les octets exacts transmis sur le réseau. Voir `fixtures/README.md`. |
| `scripts/` | `verify.sh` est le contrôle d'acceptation de ce dépôt. Les autres scripts construisent les fixtures et vérifient l'évolution du schéma. |
| `PROTOCOL_VERSION` | La version actuelle du protocole, `MAJOR.MINOR`. |
| `FLATBUFFERS_VERSION`, `FLATC_SHA256` | La version épinglée de `flatc` et la somme de contrôle de son binaire macOS. |

<a id="the-protocol-at-a-glance"></a>
## Le protocole en bref

- **Transport.** Le serveur écoute en TCP, uniquement sur l'interface de bouclage, en essayant les ports 48160 à 48167 dans l'ordre. Un simulateur partage l'interface de bouclage du Mac ; un appareil connecté en USB est joint via usbmuxd de macOS, dont le serveur ignore tout. Un seul client à la fois.
- **Tramage.** Une trame est une longueur `N` sur 4 octets en little-endian, suivie de `N` octets contenant un FlatBuffer ordinaire de type racine `Frame` et d'identifiant de fichier `CTWY`. Ce n'est **pas** le format préfixé par la taille de FlatBuffers ; les fixtures `.stream` montrent les octets exacts. `N` ne peut pas dépasser 256 MiB, et un récepteur vérifie l'intégralité du tampon avant de lire le moindre champ.
- **Poignée de main.** La première trame du client est `Hello` ; le serveur répond toujours par son propre `Hello`. Les versions majeures doivent correspondre, sinon les deux côtés ferment la connexion. Lorsque les versions mineures diffèrent, les deux côtés fonctionnent avec la plus basse.
- **Requêtes.** Le client attribue un `request_id` croissant de manière monotone. Les requêtes ordinaires (`GetAppIcon`, `GetHierarchy`, `GetSubtree`, `SetAttribute` et, depuis 1.2, `GetEnvironment` et `SetEnvironment`) reçoivent exactement une réponse. `GetLayerDetails` est un flux : zéro ou plusieurs trames `LayerDetailsChunk`, puis un `StreamEnd`. `Cancel` termine un flux prématurément et n'a pas de réponse propre. Le serveur traite les requêtes dans l'ordre.
- **Événements.** Le serveur envoie `AppStateChanged` avec un `request_id` à 0 après la poignée de main et à chaque changement de l'état actif de l'application.
- **Erreurs.** `Error` porte un `ErrorCode` stable et un message lisible par un humain. Les clients se fondent sur le code, jamais sur le texte.

Chaque règle ci-dessus correspond à une clause de `PROTOCOL.md` ; cette liste ne sert qu'à s'orienter.

<a id="versioning-and-evolution"></a>
## Versionnage et évolution

La version du protocole est `MAJOR.MINOR` dans `PROTOCOL_VERSION` ; les publications sont étiquetées `vMAJOR.MINOR.PATCH`. Le schéma évolue uniquement par ajout : des champs en fin de table, des membres en fin d'énumération et d'union. Les structs, l'identifiant de fichier et le type racine ne changent jamais. Toute autre modification entraîne un changement de version majeure. Une publication `PATCH` modifie la formulation ou les fixtures sans toucher au schéma. Pendant son développement, une version mineure est étiquetée `vMAJOR.MINOR.0-dev.N` ; ces étiquettes servent uniquement au développement, et un pair publié fixe une étiquette de publication. Les règles complètes sont les clauses `P-EVO` de `PROTOCOL.md`.

Le protocole est **figé en 1.0**. Désormais, le schéma n'évolue que par ajout, dans des versions mineures. La 1.0 est un changement de version majeure par rapport à la 0.5 : un pair 0.x et un pair 1.x échouent à la poignée de main, et c'est voulu.

<a id="implementing-a-peer"></a>
## Implémenter un pair

1. Lisez `PROTOCOL.md` intégralement. Les clauses sont courtes et se renvoient les unes aux autres.
2. Générez le code à partir de `schema/cutaway.fbs` avec le `flatc` épinglé (voir `FLATBUFFERS_VERSION`). `scripts/get-flatc.sh` télécharge exactement cette version dans `.tools/`.
3. Testez avec `fixtures/bin/`. Chaque `.bin` est un tampon unique pour tester le décodage ; chaque `.stream` est une direction d'un scénario complet pour tester le tramage. N'oubliez pas que `flatc` omet les champs égaux à leur valeur par défaut : un décodeur les relit donc comme 0, false ou le premier membre de l'énumération.
4. Relevez la limite de tables du vérificateur FlatBuffers si votre runtime en impose une : le protocole autorise des trames comportant bien plus de tables que la plupart des valeurs par défaut (`P-FRAME-06`).

<a id="verifying-this-repository"></a>
## Vérifier ce dépôt

```bash
scripts/verify.sh
```

Il télécharge le `flatc` épinglé, compile le schéma, reconstruit chaque fixture et compare le résultat avec `fixtures/bin/`, vérifie les fixtures au regard des clauses que le schéma ne peut pas exprimer, et contrôle que le schéma actuel est une évolution autorisée du dernier instantané publié. Il nécessite `bash`, `curl` et `python3`, et ne fonctionne que sous macOS : les vérifications des fixtures décompressent les images avec `compression_tool`, et `get-flatc.sh` télécharge la version macOS de `flatc`.

Après avoir modifié `fixtures/src/` ou le schéma :

```bash
scripts/build-fixtures.sh fixtures/bin
```

<a id="license"></a>
## Licence

MIT. Voir `LICENSE`.
