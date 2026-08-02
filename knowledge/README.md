# CCC 知识库

> CCC 自建知识库。M4 移交后，CCC 所有决策/教训只写本库，不写外脑（qx-map / hp-kb）。
> 初始化日期：2026-08-02 · 关联：INT-120（CCC 重构）· P5 知识移植

## 结构

```
knowledge/
├── README.md                        # 本文件——用法 + 维护规则
├── domains/                         # 分域知识（可检索源）
│   ├── nodes-paths/                 #   节点/路径域
│   │   └── seed.md                  #     机器、IP、SSH、服务
│   ├── projects/                    #   项目元数据域
│   │   └── seed.md                  #     项目位置、性质、访问方式
│   ├── decisions/                   #   决策域
│   │   └── seed.md                  #     关键决策摘要
│   └── lessons/                     #   教训域
│       └── seed.md                  #     教训 + 红线
├── seed/                            # T9 原始种子包（参考快照）
│   ├── 00-README.md
│   ├── 01-nodes-paths.json
│   ├── 02-project-metadata.json
│   ├── 03-key-decisions.json
│   └── 04-lessons.json
└── ccc-kb-search.sh                 # 基础检索脚本（关键词/域）
```

## 维护规则

### 新增知识

1. **决策** → 写入 `knowledge/domains/decisions/`，格式：标题 + 日期 + 摘要 + 状态。
2. **教训** → 写入 `knowledge/domains/lessons/`，格式：编号 + 标题 + 根因 + 修复 + 日期。
3. **节点/路径变更** → 更新 `knowledge/domains/nodes-paths/seed.md`，标注变更日期。
4. **项目元数据变更** → 更新 `knowledge/domains/projects/seed.md`。

### 独立纪律（D3 / D2）

1. CCC 知识库**独立运行**，运行时不再读 qx-map / hp-kb。
2. 新决策/教训**只写本库**，不写外脑（M4 起强制）。
3. 需要外脑信息时 → 从 `knowledge/domains/` 检索，不查 qx-map 原文。
4. 违反独立 = 漂移，验收即打回。

### 检索方式

```bash
# 全文关键词检索
bash knowledge/ccc-kb-search.sh <关键词>

# 指定域检索
bash knowledge/ccc-kb-search.sh <关键词> --domain nodes-paths
bash knowledge/ccc-kb-search.sh <关键词> --domain decisions
bash knowledge/ccc-kb-search.sh <关键词> --domain lessons
bash knowledge/ccc-kb-search.sh <关键词> --domain projects

# 列出指定域所有条目
bash knowledge/ccc-kb-search.sh --list --domain nodes-paths
```

## 来源

T9 种子包来自外脑权威源（qx-map），一次性导入，之后独立维护。