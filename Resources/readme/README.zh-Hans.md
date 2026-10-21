<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="cutaway-protocol-dark.svg">
    <img src="cutaway-protocol-light.svg" alt="CutawayProtocol — The shared language of client and server." width="850">
  </picture>
</p>

[![FlatBuffers](https://img.shields.io/badge/FlatBuffers-schema-blue)](../../schema/cutaway.fbs)
[![License](https://img.shields.io/badge/License-MIT-lightgrey)](../../LICENSE)

[English](../../README.md) | **简体中文** | [繁體中文](README.zh-Hant.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Español](README.es.md) | [Français](README.fr.md) | [Deutsch](README.de.md)

*本文为译文；如与[英文 README](../../README.md) 有出入，以英文版为准。*

# Cutaway Protocol

**[CutawayServer](https://github.com/nothingsh/CutawayServer)** 与 **[Cutaway](https://github.com/nothingsh/Cutaway)** 之间的通信协议。CutawayServer 是嵌入在被检查 App 中的 iOS SDK，Cutaway 是一款 macOS App。Cutaway 通过 TCP 连接到服务端，获取 App 的图层层级、截图、属性和 Auto Layout 约束，并能在 App 运行时修改属性、改写 App 的特征环境。

本仓库是该协议唯一的权威来源。它不包含任何 Swift 代码：两端都以 git submodule 的方式钉住本仓库的某个 tag，并从 schema 生成各自的代码。

[Cutaway 网站](https://nothingsh.github.io/Cutaway/zh-Hans/protocol/)有协议的指南：[概览](https://nothingsh.github.io/Cutaway/zh-Hans/protocol/)、[版本与兼容](https://nothingsh.github.io/Cutaway/zh-Hans/protocol/versions)、[实现一端](https://nothingsh.github.io/Cutaway/zh-Hans/protocol/implementing)，以及由本仓库的 `PROTOCOL.md` 生成的[规范](https://nothingsh.github.io/Cutaway/zh-Hans/protocol/spec)。

<a id="contents"></a>
## 内容

| 路径 | 说明 |
|---|---|
| `PROTOCOL.md` | 规范性的协议文档。带编号的条款（`P-TRANS-01`、`P-FRAME-03`……）是要求，其余内容都是说明。 |
| `schema/cutaway.fbs` | [FlatBuffers](https://flatbuffers.dev) schema。每一帧的载荷都是此处定义的 `Frame`。 |
| `schema/released/` | 每个已发布的 `MAJOR.MINOR` 对应的 schema 快照。发布后不再修改。 |
| `fixtures/` | 用于测试实现的基准帧。`src/` 存放 JSON 源文件，`bin/` 存放编译后的缓冲区以及线路上的确切字节。参见 `fixtures/README.md`。 |
| `scripts/` | `verify.sh` 是本仓库的验收关卡。其余脚本用于构建夹具和检查 schema 演进。 |
| `PROTOCOL_VERSION` | 当前的协议版本，格式为 `MAJOR.MINOR`。 |
| `FLATBUFFERS_VERSION`、`FLATC_SHA256` | 钉住的 `flatc` 版本及其 macOS 二进制文件的校验和。 |

<a id="the-protocol-at-a-glance"></a>
## 协议概览

- **传输。** 服务端在 TCP 上监听，仅限回环地址，按顺序尝试 48160 到 48167 端口。模拟器与 Mac 共享回环地址；通过 USB 连接的设备经由 macOS 的 usbmuxd 访问，服务端对此毫不知情。同一时间只接受一个客户端。
- **分帧。** 一帧由 4 字节小端序长度 `N` 和随后的 `N` 个字节组成，这 `N` 个字节是一个普通的 FlatBuffer，根类型为 `Frame`，文件标识符为 `CTWY`。这**不是** FlatBuffers 的带长度前缀格式；`.stream` 夹具展示了确切的字节。`N` 不得超过 256 MiB，接收方在读取任何字段之前须先校验整个缓冲区。
- **握手。** 客户端发送的第一帧是 `Hello`；服务端总是以自己的 `Hello` 作答。主版本号必须一致，否则双方都会关闭连接。次版本号不同时，双方按较低的那个版本工作。
- **请求。** 客户端分配单调递增的 `request_id`。普通请求（`GetAppIcon`、`GetHierarchy`、`GetSubtree`、`SetAttribute`，以及 1.2 起的 `GetEnvironment` 和 `SetEnvironment`）恰好得到一个响应。`GetLayerDetails` 是一个流：零个或多个 `LayerDetailsChunk` 帧，随后是一个 `StreamEnd`。`Cancel` 会提前结束一个流，它本身没有响应。服务端按顺序处理请求。
- **事件。** 握手完成后，以及 App 的活跃状态每次变化时，服务端都会发送 `request_id` 为 0 的 `AppStateChanged`。
- **错误。** `Error` 携带一个稳定的 `ErrorCode` 和一条供人阅读的消息。客户端根据错误码分支处理，绝不依据文本。

以上每条规则都对应 `PROTOCOL.md` 中的一个条款；此列表仅供快速了解。

<a id="versioning-and-evolution"></a>
## 版本与演进

协议版本是 `PROTOCOL_VERSION` 中的 `MAJOR.MINOR`；发布版本打 `vMAJOR.MINOR.PATCH` 形式的 tag。schema 只通过追加来演进：在 table 末尾添加字段，在 enum 和 union 末尾添加成员。struct、文件标识符和根类型永不改变。除此之外的任何改动都要升主版本号。`PATCH` 版本只修改措辞或夹具，不触及 schema。次版本开发期间打 `vMAJOR.MINOR.0-dev.N` 形式的 tag；这些 tag 仅供开发，发布的对端钉正式版本的 tag。完整规则见 `PROTOCOL.md` 中的 `P-EVO` 条款。

协议已**冻结为 1.0**。此后 schema 只通过追加演进，升次版本号。1.0 相对 0.5 是一次主版本升级：0.x 的对端与 1.x 的对端按设计会握手失败。

<a id="implementing-a-peer"></a>
## 实现一个对端

1. 从头到尾阅读 `PROTOCOL.md`。条款都很简短，并且相互引用。
2. 使用钉住的 `flatc`（见 `FLATBUFFERS_VERSION`）从 `schema/cutaway.fbs` 生成代码。`scripts/get-flatc.sh` 会将该确切版本下载到 `.tools/`。
3. 用 `fixtures/bin/` 进行测试。每个 `.bin` 是一个缓冲区，用于测试解码；每个 `.stream` 是一个完整场景中的一个方向，用于测试分帧。注意 `flatc` 会省略等于默认值的字段，因此解码器读回的值将是 0、false 或枚举的第一个成员。
4. 如果你的运行时对 FlatBuffers 校验器设有 table 数量上限，请调高它：协议允许的帧所含 table 数量远超大多数默认值（`P-FRAME-06`）。

<a id="verifying-this-repository"></a>
## 验证本仓库

```bash
scripts/verify.sh
```

它会下载钉住的 `flatc`，编译 schema，重新构建每个夹具并将结果与 `fixtures/bin/` 比对，依据 schema 无法表达的条款检查夹具，并检查当前 schema 相对于最新发布快照是否属于允许的演进。它需要 `bash`、`curl` 和 `python3`，并且只能在 macOS 上运行：夹具检查使用 `compression_tool` 解压图像，而 `get-flatc.sh` 下载的是 macOS 版的 `flatc`。

修改 `fixtures/src/` 或 schema 之后：

```bash
scripts/build-fixtures.sh fixtures/bin
```

<a id="license"></a>
## 许可证

MIT。参见 `LICENSE`。
