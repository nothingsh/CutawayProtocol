<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="cutaway-protocol-dark.svg">
    <img src="cutaway-protocol-light.svg" alt="CutawayProtocol — The shared language of client and server." width="850">
  </picture>
</p>

[![FlatBuffers](https://img.shields.io/badge/FlatBuffers-schema-blue)](../../schema/cutaway.fbs)
[![License](https://img.shields.io/badge/License-MIT-lightgrey)](../../LICENSE)

[English](../../README.md) | [简体中文](README.zh-Hans.md) | **繁體中文** | [日本語](README.ja.md) | [한국어](README.ko.md) | [Español](README.es.md) | [Français](README.fr.md) | [Deutsch](README.de.md)

*本文為譯文；如與[英文 README](../../README.md) 有出入，以英文版為準。*

# Cutaway Protocol

**[CutawayServer](https://github.com/nothingsh/CutawayServer)** 與 **[Cutaway](https://github.com/nothingsh/Cutaway)** 之間的通訊協定。CutawayServer 是內嵌於受檢視 App 中的 iOS SDK，Cutaway 則是一款 macOS App。Cutaway 透過 TCP 連線至伺服器，取得 App 的圖層階層、螢幕截圖、屬性與 Auto Layout 約束，並可在 App 執行期間修改屬性、覆寫 App 的特徵環境。

本儲存庫是該協定的唯一權威來源。其中不含任何 Swift 程式碼：兩端各自以 git submodule 釘選本儲存庫的某個 tag，並從 schema 產生各自的程式碼。

[Cutaway 網站](https://nothingsh.github.io/Cutaway/protocol/)有協定的指南（英文，另有[簡體中文版](https://nothingsh.github.io/Cutaway/zh-Hans/protocol/)）：[概覽](https://nothingsh.github.io/Cutaway/protocol/)、[哪些版本可以搭配使用](https://nothingsh.github.io/Cutaway/protocol/versions)、[實作一端](https://nothingsh.github.io/Cutaway/protocol/implementing)，以及由本儲存庫的 `PROTOCOL.md` 產生的[規格](https://nothingsh.github.io/Cutaway/protocol/spec)。

<a id="contents"></a>
## 內容

| 路徑 | 說明 |
|---|---|
| `PROTOCOL.md` | 規範性的規格文件。帶編號的條款（`P-TRANS-01`、`P-FRAME-03`……）為要求事項，其餘皆為說明。 |
| `schema/cutaway.fbs` | [FlatBuffers](https://flatbuffers.dev) schema。每一幀的載荷都是此處定義的 `Frame`。 |
| `schema/released/` | 每個已發布的 `MAJOR.MINOR` 的 schema 快照。發布後不再修改。 |
| `fixtures/` | 用於測試實作的基準幀。`src/` 存放 JSON 原始檔，`bin/` 存放編譯後的緩衝區以及實際傳輸的位元組。詳見 `fixtures/README.md`。 |
| `scripts/` | `verify.sh` 是本儲存庫的驗收關卡。其他指令稿負責建置夾具並檢查 schema 的演進。 |
| `PROTOCOL_VERSION` | 目前的協定版本，格式為 `MAJOR.MINOR`。 |
| `FLATBUFFERS_VERSION`、`FLATC_SHA256` | 釘選的 `flatc` 版本，以及其 macOS 執行檔的校驗和。 |

<a id="the-protocol-at-a-glance"></a>
## 協定概覽

- **傳輸。** 伺服器僅在 loopback 上監聽 TCP，依序嘗試 48160 至 48167 號連接埠。模擬器與 Mac 共用 loopback；透過 USB 連接的裝置則經由 macOS 的 usbmuxd 存取，伺服器對此毫不知情。同一時間只接受一個用戶端。
- **分幀。** 一幀由 4 位元組的 little-endian 長度 `N` 開頭，後接 `N` 個位元組，內含一個普通的 FlatBuffer，其根型別為 `Frame`、檔案識別碼為 `CTWY`。這**並非** FlatBuffers 的 size-prefixed 格式；`.stream` 夾具展示了確切的位元組。`N` 不得超過 256 MiB，接收端在讀取任何欄位之前須先驗證整個緩衝區。
- **交握。** 用戶端的第一幀為 `Hello`；伺服器一律以自己的 `Hello` 回應。主版本號必須一致，否則雙方皆關閉連線。次版本號不同時，雙方以較低者運作。
- **請求。** 用戶端指派單調遞增的 `request_id`。一般請求（`GetAppIcon`、`GetHierarchy`、`GetSubtree`、`SetAttribute`，以及 1.2 起的 `GetEnvironment` 與 `SetEnvironment`）恰好得到一個回應。`GetLayerDetails` 是串流：零或多個 `LayerDetailsChunk` 幀，最後接一個 `StreamEnd`。`Cancel` 可提前結束串流，本身沒有回應。伺服器依序處理請求。
- **事件。** 伺服器在交握完成後，以及每當 App 的活躍狀態改變時，傳送 `request_id` 為 0 的 `AppStateChanged`。
- **錯誤。** `Error` 帶有穩定的 `ErrorCode` 與一段供人閱讀的訊息。用戶端依錯誤碼分支處理，絕不依訊息文字判斷。

以上每一條規則都是 `PROTOCOL.md` 中的條款；此清單僅供快速了解。

<a id="versioning-and-evolution"></a>
## 版本與演進

協定版本為 `PROTOCOL_VERSION` 中的 `MAJOR.MINOR`；發布版本以 `vMAJOR.MINOR.PATCH` 標記 tag。schema 僅以追加方式演進：欄位加在 table 的末尾，成員加在 enum 與 union 的末尾。struct、檔案識別碼與根型別永不變更。其他任何改動都需升級主版本號。`PATCH` 版本只修改措辭或夾具，不動 schema。次版本開發期間以 `vMAJOR.MINOR.0-dev.N` 標記 tag；這些 tag 僅供開發，發布的對端應釘選正式版本的 tag。完整規則見 `PROTOCOL.md` 中的 `P-EVO` 條款。

本協定已**凍結為 1.0**。此後 schema 只透過追加演進，升次版本號。1.0 相對 0.5 是一次主版本升級：0.x 與 1.x 的對端在設計上就會交握失敗。

<a id="implementing-a-peer"></a>
## 實作對端

1. 從頭到尾讀完 `PROTOCOL.md`。條款都很簡短，且彼此交叉引用。
2. 以釘選的 `flatc`（見 `FLATBUFFERS_VERSION`）從 `schema/cutaway.fbs` 產生程式碼。`scripts/get-flatc.sh` 會將該確切版本下載至 `.tools/`。
3. 以 `fixtures/bin/` 進行測試。每個 `.bin` 是一個用於測試解碼的緩衝區；每個 `.stream` 是完整情境中的單一方向，用於測試分幀。請注意，`flatc` 會省略等於預設值的欄位，因此解碼器讀回的值會是 0、false 或該 enum 的第一個成員。
4. 若你的執行環境對 FlatBuffers 驗證器設有 table 數量上限，請將其調高：本協定允許的幀所含 table 數量遠超過多數預設值（`P-FRAME-06`）。

<a id="verifying-this-repository"></a>
## 驗證本儲存庫

```bash
scripts/verify.sh
```

它會下載釘選的 `flatc`、編譯 schema、重新建置所有夾具並與 `fixtures/bin/` 比對、依 schema 無法表達的條款檢查夾具，並檢查目前的 schema 是否為最新發布快照的合法演進。它需要 `bash`、`curl` 與 `python3`，且僅能在 macOS 上執行：夾具檢查使用 `compression_tool` 解壓縮圖片，而 `get-flatc.sh` 下載的是 macOS 版的 `flatc`。

編輯 `fixtures/src/` 或 schema 之後：

```bash
scripts/build-fixtures.sh fixtures/bin
```

<a id="license"></a>
## 授權

MIT。詳見 `LICENSE`。
