<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="cutaway-protocol-dark.svg">
    <img src="cutaway-protocol-light.svg" alt="CutawayProtocol — The shared language of client and server." width="850">
  </picture>
</p>

[![FlatBuffers](https://img.shields.io/badge/FlatBuffers-schema-blue)](../../schema/cutaway.fbs)
[![License](https://img.shields.io/badge/License-MIT-lightgrey)](../../LICENSE)

[English](../../README.md) | [简体中文](README.zh-Hans.md) | [繁體中文](README.zh-Hant.md) | [日本語](README.ja.md) | **한국어** | [Español](README.es.md) | [Français](README.fr.md) | [Deutsch](README.de.md)

*이 문서는 번역본입니다. 내용이 서로 다를 경우 [영어 README](../../README.md)가 우선합니다.*

# Cutaway Protocol

검사 대상 앱에 내장되는 iOS SDK인 **[CutawayServer](https://github.com/nothingsh/CutawayServer)**와 macOS 앱인 **[Cutaway](https://github.com/nothingsh/Cutaway)** 사이의 통신 프로토콜입니다. Cutaway는 TCP로 서버에 접속하여 앱의 레이어 계층 구조, 스크린샷, 속성, Auto Layout 제약 조건을 가져오며, 앱이 실행되는 동안 속성을 수정하거나 앱의 트레이트 환경을 재정의할 수도 있습니다.

이 저장소는 해당 프로토콜의 유일한 기준(single source of truth)입니다. Swift 코드는 포함하지 않습니다. 양쪽 모두 이 저장소의 태그를 git submodule로 고정하고 schema에서 각자의 코드를 생성합니다.

[Cutaway 웹사이트](https://nothingsh.github.io/Cutaway/protocol/)에 프로토콜 가이드(영어)가 있습니다. [개요](https://nothingsh.github.io/Cutaway/protocol/), [함께 동작하는 릴리스](https://nothingsh.github.io/Cutaway/protocol/versions), [피어 구현하기](https://nothingsh.github.io/Cutaway/protocol/implementing), 그리고 이 저장소의 `PROTOCOL.md`로 만든 [명세](https://nothingsh.github.io/Cutaway/protocol/spec)입니다.

<a id="contents"></a>
## 구성

| 경로 | 내용 |
|---|---|
| `PROTOCOL.md` | 규범적인 사양입니다. 번호가 붙은 조항(`P-TRANS-01`, `P-FRAME-03`, …)은 요구 사항이며, 그 외의 내용은 모두 설명입니다. |
| `schema/cutaway.fbs` | [FlatBuffers](https://flatbuffers.dev) schema입니다. 모든 프레임의 페이로드는 여기에 정의된 `Frame`입니다. |
| `schema/released/` | 릴리스된 각 `MAJOR.MINOR`의 schema 스냅샷입니다. 릴리스 후에는 절대 수정하지 않습니다. |
| `fixtures/` | 구현을 테스트하기 위한 기준 프레임입니다. `src/`에는 JSON 소스가, `bin/`에는 컴파일된 버퍼와 회선상의 정확한 바이트가 들어 있습니다. `fixtures/README.md`를 참고하세요. |
| `scripts/` | `verify.sh`는 이 저장소의 승인 관문입니다. 나머지 스크립트는 픽스처를 빌드하고 schema의 진화를 검사합니다. |
| `PROTOCOL_VERSION` | 현재 프로토콜 버전(`MAJOR.MINOR`)입니다. |
| `FLATBUFFERS_VERSION`, `FLATC_SHA256` | 고정된 `flatc` 릴리스와 그 macOS 바이너리의 체크섬입니다. |

<a id="the-protocol-at-a-glance"></a>
## 프로토콜 한눈에 보기

- **전송.** 서버는 루프백 전용으로 TCP에서 수신 대기하며, 포트 48160부터 48167까지 순서대로 시도합니다. 시뮬레이터는 Mac의 루프백을 공유하고, USB로 연결된 기기는 macOS의 usbmuxd를 통해 접근하는데, 서버는 이에 대해 전혀 알지 못합니다. 한 번에 하나의 클라이언트만 연결할 수 있습니다.
- **프레이밍.** 프레임은 4바이트 리틀 엔디언 길이 `N`과 그 뒤를 잇는 `N`바이트로 구성되며, 이 `N`바이트에는 루트 타입이 `Frame`이고 파일 식별자가 `CTWY`인 일반 FlatBuffer 하나가 담깁니다. 이는 FlatBuffers의 size-prefixed 형식이 **아닙니다**. 정확한 바이트는 `.stream` 픽스처에서 확인할 수 있습니다. `N`은 256 MiB를 초과할 수 없으며, 수신 측은 어떤 필드든 읽기 전에 버퍼 전체를 검증합니다.
- **핸드셰이크.** 클라이언트의 첫 프레임은 `Hello`이며, 서버는 항상 자신의 `Hello`로 응답합니다. 메이저 버전이 일치해야 하며, 일치하지 않으면 양쪽 모두 연결을 닫습니다. 마이너 버전이 다르면 양쪽 모두 더 낮은 버전으로 동작합니다.
- **요청.** 클라이언트는 단조 증가하는 `request_id`를 할당합니다. 일반 요청(`GetAppIcon`, `GetHierarchy`, `GetSubtree`, `SetAttribute`, 1.2부터 `GetEnvironment`와 `SetEnvironment`)은 정확히 하나의 응답을 받습니다. `GetLayerDetails`는 스트림으로, 0개 이상의 `LayerDetailsChunk` 프레임 뒤에 `StreamEnd` 하나가 옵니다. `Cancel`은 스트림을 조기에 종료하며 그 자체에 대한 응답은 없습니다. 서버는 요청을 순서대로 처리합니다.
- **이벤트.** 서버는 핸드셰이크 직후와 앱의 활성 상태가 바뀔 때마다 `request_id` 0으로 `AppStateChanged`를 보냅니다.
- **오류.** `Error`는 안정적인 `ErrorCode`와 사람이 읽을 수 있는 메시지를 담습니다. 클라이언트는 텍스트가 아니라 반드시 코드를 기준으로 분기해야 합니다.

위의 모든 규칙은 `PROTOCOL.md`의 조항으로 정의되어 있으며, 이 목록은 개요일 뿐입니다.

<a id="versioning-and-evolution"></a>
## 버전 관리와 진화

프로토콜 버전은 `PROTOCOL_VERSION`에 기록된 `MAJOR.MINOR`이며, 릴리스에는 `vMAJOR.MINOR.PATCH` 태그를 붙입니다. schema는 추가만으로 진화합니다. 즉, 테이블의 끝에 필드를, enum과 union의 끝에 멤버를 추가하는 것만 허용됩니다. struct, 파일 식별자, 루트 타입은 절대 바뀌지 않습니다. 그 밖의 모든 변경은 메이저 버전을 올려야 합니다. `PATCH` 릴리스는 schema를 건드리지 않고 문구나 픽스처만 변경합니다. 개발 중인 마이너 버전에는 `vMAJOR.MINOR.0-dev.N` 태그를 붙입니다. 이 태그는 개발용일 뿐이며, 배포하는 피어는 정식 릴리스 태그에 고정합니다. 전체 규칙은 `PROTOCOL.md`의 `P-EVO` 조항에 있습니다.

프로토콜은 **1.0으로 동결되었습니다**. 이제 스키마는 마이너 버전에서 추가하는 방식으로만 확장됩니다. 1.0은 0.5에서 메이저 버전을 올린 것이므로, 0.x 피어와 1.x 피어는 설계상 핸드셰이크에 실패합니다.

<a id="implementing-a-peer"></a>
## 피어 구현하기

1. `PROTOCOL.md`를 처음부터 끝까지 읽으세요. 조항은 짧고 서로 상호 참조되어 있습니다.
2. 고정된 `flatc`(`FLATBUFFERS_VERSION` 참고)로 `schema/cutaway.fbs`에서 코드를 생성하세요. `scripts/get-flatc.sh`가 정확히 그 릴리스를 `.tools/`에 내려받습니다.
3. `fixtures/bin/`으로 테스트하세요. 각 `.bin`은 디코딩 테스트용 버퍼 하나이고, 각 `.stream`은 프레이밍 테스트용으로 전체 시나리오의 한 방향을 담고 있습니다. `flatc`는 기본값과 같은 필드를 생략하므로, 디코더는 이를 0, false 또는 enum의 첫 번째 멤버로 읽는다는 점에 유의하세요.
4. 런타임에 FlatBuffers verifier의 테이블 수 제한이 있다면 그 값을 올리세요. 이 프로토콜은 대부분의 기본값보다 훨씬 많은 테이블을 가진 프레임을 허용합니다(`P-FRAME-06`).

<a id="verifying-this-repository"></a>
## 이 저장소 검증하기

```bash
scripts/verify.sh
```

이 스크립트는 고정된 `flatc`를 내려받아 schema를 컴파일하고, 모든 픽스처를 다시 빌드하여 그 결과를 `fixtures/bin/`과 비교하며, schema로 표현할 수 없는 조항에 대해 픽스처를 검사하고, 현재 schema가 최신 릴리스 스냅샷에서 허용되는 진화인지 확인합니다. `bash`, `curl`, `python3`이 필요하며 macOS에서만 실행됩니다. 픽스처 검사가 `compression_tool`로 이미지의 압축을 해제하고, `get-flatc.sh`가 macOS용 `flatc` 빌드를 내려받기 때문입니다.

`fixtures/src/`나 schema를 수정한 후에는 다음을 실행하세요.

```bash
scripts/build-fixtures.sh fixtures/bin
```

<a id="license"></a>
## 라이선스

MIT. `LICENSE`를 참고하세요.
