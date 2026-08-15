# 交付报告 · <项目或方案名>

> 项目：<prefix> · 编号：<prefix>-delivery-<NNN> · 方案：<prefix>-plan-<NNN> · 作者：<作者>
> 交付日期：YYYY-MM-DD · 软件版本：vX.Y.Z · 对应 Git Tag：<tag-name>

---

## 1. 交付目标与背景

<简述本次交付的核心目标、交付范围以及解决的痛点/业务背景。>

## 2. 交付物清单（Delivery Checklist）

交付前必须逐项核对并勾选以下交付物，严禁遗漏：

- [ ] **交付报告**：本交付报告已完成并归档至 `docs/projects/<prefix>/deliveries/` 目录下。
- [ ] **CHANGELOG**：业务仓 `CHANGELOG.md` 或项目文档中已追加本次版本的变更日志。
- [ ] **RELEASE**：发布文档/版本归档已建立（如 `docs/releases/` 或 GitHub Release 页面）。
- [ ] **Git Tag**：代码已打上语义化版本 Tag，并已 push 至远程仓库。
- [ ] **可复跑安装验证**：已提供清晰、确定性的安装与运行验证脚本或命令，确保可一键/一步复跑。

## 3. 方案与卡状态对齐（Gate Checklist）

方案级交付门禁（Delivery Gate）的核心硬性要求：

- [ ] **方案状态置为「已完成」**：对应的方案文件 `docs/projects/<prefix>/plans/<NNN>-*.md` 头部的 `状态：` 字段已修改为 `已完成`。
- [ ] **方案验收标准全勾**：方案文件中的所有验收标准（`- [ ]`）均已由验收席确认并通过，并全部置为 `- [x]`。
- [ ] **关联任务卡全关闭**：本方案下拆分的所有任务卡（docs/dispatch/ 目录下对应卡）在看板上均已处于 `已关闭` 状态。
- [ ] **项目档案近况同步**：`docs/projects/<prefix>/README.md` 的 `线路 / 近况` 章节已同步更新，反映最新交付状态。
- [ ] **全局线路图挂账同步**：`docs/roadmap.md` 中对应项目的「业务线路」已同步更新，推进到最新里程碑，并对下一阶段工作进行挂账。

## 4. 版本与发布信息

- **软件版本**：`vX.Y.Z`（遵循语义化版本规范，例如 `v1.0.0`）
- **代码提交**：`commit <commit-hash>`
- **发布渠道/部署机**：<如生产机 IP、Docker Registry 镜像地址或内置分发路径>

## 5. 可复跑安装与部署验证

### 5.1 环境要求
<运行或安装所需的基础环境，例如 Python 3.12+, Node.js 20+, Rust 1.78+ 等>

### 5.2 安装步骤
```bash
# 示例：克隆与安装依赖
git clone <repository-url>
cd <repository-dir>
git checkout <tag-name>
# 运行安装/编译命令
npm install
```

### 5.3 运行验证
```bash
# 运行验证命令，例如单测或健康检查脚本
pytest server/tests
# 或执行特定的测试探针
./scripts/health-check.sh
```

## 6. 备注与遗留问题

<记录任何已知的非阻碍性遗留问题（如果有，挂账到下一期方案）、后续运维注意事项或扩展建议。>
