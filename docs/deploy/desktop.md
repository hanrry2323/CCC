# CCC Desktop 客户端（Tauri）

> 产品主 UI 面。网页 Hub 为过渡。服务端见 [`topology.md`](topology.md)。

## 连接服务端

默认指向 Mac2017 Hub：

```text
http://192.168.3.116:7777
```

覆盖：

```bash
export CCC_SERVER=http://192.168.3.116:7777
```

[`src-tauri/tauri.conf.json`](../../src-tauri/tauri.conf.json) 的 `devPath` / CSP `connect-src` 已对齐该地址。

## 构建（M1 客户端机）

```bash
cd /path/to/CCC
# 需 Rust + Tauri CLI
cargo tauri build
```

壳只做展示与多会话 UI；**Engine / 中转 / 工作区在 Server**。

## 多会话（方向）

Session 一等公民、后台流不随 tab 卸载、双 pane 起步——在桌面壳迭代，不再往网页 Hub 堆多路补丁。
