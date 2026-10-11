# Product Competitive Research Skill

一个帮助你更有条理地比较竞品、研究产品和整理市场信息的 AI Skill。

你只需要说明想比较的产品、服务或研究问题，它会根据你的目标整理研究范围、查找公开资料、比较差异，并形成带有信息来源的分析报告。如果问题还不够明确，它会先询问关键问题，而不是直接生成一份泛泛的报告。

> **什么是 Skill？** Skill 是一组可复用的 AI 工作流程与规则，用来告诉兼容的 AI 助手应该怎样完成某类任务。它不是独立 App，也不是所有 AI 聊天软件都能直接安装的普通提示词。

## 它能帮你做什么？

- 比较不同产品或服务的功能、价格、套餐和使用体验；
- 根据你的研究目标整理合适的比较维度；
- 查找公开资料，尽量读取原始网页并注明来源；
- 区分事实、厂商说法、分析推断和暂时无法确认的信息；
- 把差异整理成清楚的报告，并在证据允许时提出有适用条件的建议。

已经通过真实模型测试的重点是**产品竞品分析**，包括明确维度比较、主动澄清和围绕用户任务的深度分析。Skill 的设计也能支持产品选型及其他公开市场信息整理，但行业规模、市场预测、消费者调查等更广泛场景尚未经过充分验证。

它适合需要比较产品、服务或公开市场信息的人，例如市场研究人员、产品与设计人员、运营和增长团队、创业者、独立开发者、学生，以及希望在选择工具或服务前做功课的普通用户。

## 看一个真实例子

下面来自一次 V1.1 真实运行，内容经过节选，没有改写模型行为。

**用户：**

> 比较微信和小红书。

**Skill 先澄清：**

> 你更想从哪个角度比较微信和小红书：**内容推荐与搜索、社交关系与互动，还是商业推广与获客**？也可以直接说你想用这个比较做什么决策。

**用户补充：**

> 重点比较内容发现和搜索体验，面向内容产品规划。

**真实运行节选：**

> 面向内容产品规划，小红书更值得研究“发现兴趣后，如何继续搜索和比较”；微信更值得研究“如何连接多种内容与服务，承接不同搜索意图”。这是基于公开产品结构的分析，不代表两者搜索效果已有实测排名。

完整过程见[微信与小红书案例](examples/real-world/wechat-vs-xiaohongshu.md)。这是一次真实运行结果，不代表每次运行都会得到完全相同的表现。

## 研究报告长什么样？

下面是“B站与小红书收藏内容复访体验”报告的简短预览。

| 报告部分 | 内容预览 |
| --- | --- |
| 研究目标 | 比较收藏内容、查找已收藏内容，以及后续重新使用内容的体验 |
| 分析框架 | 保存 → 组织 → 找回内容 → 定位有用部分 → 实际使用 |
| 主要发现 | B站更容易接上“继续观看、定位片段、复习知识”；小红书更贴近“归集攻略、现场查阅、共同决策” |
| 设计建议 | 允许用户保存收藏理由、视频时间点、图片页或段落，并提供直接返回该位置的入口 |
| 来源与限制 | 使用公开网页并注明来源；没有登录两款 App 做同版本实测，部分功能来自历史或第三方资料 |

报告不会只罗列功能，而会尽量解释这些设计如何影响用户完成任务。查看[完整案例节选和证据限制](examples/real-world/bilibili-vs-xiaohongshu.md)。

## 如何开始使用？

你需要一个支持 Skills，并且能够访问 GitHub、读取和操作本地文件的 AI Agent。**AI Agent 就是你与 AI 对话、让它使用工具完成任务的软件。**如果需要研究最新公开信息，它还应具备网页搜索和正文读取能力。

### 1. 复制项目地址

打开本项目的 [GitHub 页面](https://github.com/Cineys/Product-Competitive-Research-Skill)，复制仓库地址：

```text
https://github.com/Cineys/Product-Competitive-Research-Skill.git
```

### 2. 让 AI Agent 帮你安装

把仓库地址和下面这段话发送给你的 AI Agent：

```text
请阅读这个 GitHub 项目，帮我安装其中的 Product Competitive Research Skill：
https://github.com/Cineys/Product-Competitive-Research-Skill.git

先检查你是否支持 Skills，并确认安装位置和依赖。安装完成后告诉我如何调用它。如果需要修改本地文件或执行命令，请先说明操作内容。
```

这一步要求 Agent 先检查自身能力，并不保证所有客户端都能自动安装。如果客户端无法访问 GitHub、不能操作文件，或者不支持 Skills，请根据该客户端的官方说明手动安装完整的 `skills/product-competitive-research` 文件夹。

### 3. 开始使用

安装完成后，新建一个会话并尝试：

```text
使用 Product Competitive Research Skill，比较微信和小红书的内容搜索体验。
```

不同客户端可能要求使用各自的调用语法，例如 Codex 的 `$product-competitive-research` 或 Claude Code 的 `/product-competitive-research`。首次使用建议显式指定 Skill，并确认客户端确实识别到它。

> **安全提醒：**安装前确认项目来源；让 Agent 先检查文件和安装要求；执行命令或修改本地文件前，确认它准备进行的操作。自然语言安装不代表应授予 Agent 不受限制的电脑权限。

## 如何向 Skill 提问？

可以直接复制这些例子：

```text
帮我比较微信和小红书的内容搜索体验。

比较 Figma 和 Sketch 的价格及团队协作功能。

研究几款同类产品的主要差异，帮我整理成一份报告。

分析 B站和小红书的收藏管理体验，重点关注用户如何再次找到收藏内容。
```

在 Codex 中，首次使用建议在问题前写：

```text
使用 $product-competitive-research，……
```

在 Claude Code 中使用：

```text
/product-competitive-research ……
```

Skill 也可能根据问题内容自动触发，但不同客户端的识别方式不同。明确写出 Skill 名称最容易确认本次回答确实使用了它。

## Skill、客户端和网页工具的关系

| 项目 | 作用 |
| --- | --- |
| Product Competitive Research Skill | 提供研究步骤、证据规则和报告方式 |
| AI 客户端 | 运行 Skill，并让你与模型对话 |
| 搜索与网页读取工具 | 帮助模型查找和读取公开资料 |
| 模型 | 理解任务、调用工具并生成分析 |

不是所有 AI 聊天软件都能安装 Skill。即使两个客户端都支持 Skill，它们也不一定拥有相同的搜索能力、页面读取工具、脚本权限或自动触发行为。

当前真实模型测试主要在 Codex 环境完成，因此不能把测试结论直接视为 Claude Code 或其他客户端的测试结果。

| 客户端 | 当前支持状态 |
| --- | --- |
| Codex | 已完成本项目的 Skill 加载和真实模型行为测试；自然语言安装仍取决于当前 Agent 的文件和命令权限 |
| Claude Code | 官方机制支持同类 Skill 目录和显式调用；本项目尚未在该客户端运行测试 |
| 其他 AI 客户端 | 尚未核实，不提供正式安装路径或兼容性承诺 |

## 工作原理

```text
提出研究问题
      ↓
必要时澄清目标
      ↓
确定比较范围
      ↓
搜索并阅读公开资料
      ↓
比较差异
      ↓
整理发现与建议
      ↓
输出报告
```

证据核验的基本原则是：尽量读取原始网页，而不是只依赖搜索结果中的摘要。页面能够打开，不代表页面上的所有说法都已经得到验证；无法确认的信息应保留为未知或说明限制。

默认输出是普通用户可以阅读的报告，不会强制附上一大段 JSON。需要复核研究过程、且客户端允许写文件时，才可以额外生成结构化的 `research_contract.json` 研究记录。

## 已验证能力与使用限制

已经完成：

- 一次真实场景的主动澄清和多轮续接测试；
- 一次真实网页环境下的深度竞品分析测试；
- 一次 V1 与 V1.1 的固定资料比较 Pilot；
- 56 项离线测试。

需要注意：

- 以上真实模型测试主要在 Codex 中完成，单次运行不能证明稳定性；
- 官方来源身份判断规则已经补充，但修改后的模型行为尚未重新测试；
- 公开资料研究不等于登录 App 后的实际体验测试；
- 网页可能无法访问、内容可能过时，第三方资料也可能不准确；
- 不同客户端的网页工具和运行效果可能不同；
- Skill 和结构校验器都不能保证每条引用、结论或市场信息完全准确，重要决策仍应人工复核。

## 开发者信息

<details>
<summary>项目结构、结构化研究记录与测试命令</summary>

```text
skills/product-competitive-research/
  SKILL.md                      工作流入口
  references/                   澄清、证据与分析规则
  assets/report-template.md     报告模板
  scripts/validate_research.py  结构化记录校验器
tests/                          离线资料、回归测试与评测工具
examples/                       合成样例与真实运行节选
```

项目使用 Schema 1.1.0 定义可选的结构化研究记录。校验器只检查字段、状态和引用关系，不能判断事实是否真实或建议是否合理。

Python 3.10+，不需要第三方依赖：

```sh
python3 -m unittest -v
python3 skills/product-competitive-research/scripts/validate_research.py \
  examples/case-03/research_contract.json
```

Windows 可使用 `py -3` 或可用的 `python` 命令。完整合成样例见[报告](examples/case-03/report.md)和[结构化记录](examples/case-03/research_contract.json)。详细评测方法见 [rubric](tests/rubric.md)。

</details>

版本变化见 [CHANGELOG](CHANGELOG.md)。本项目采用 [MIT License](LICENSE)。

## 致谢

- [Anthropic Competitive Brief](https://github.com/anthropics/knowledge-work-plugins/blob/main/product-management/skills/competitive-brief/SKILL.md)
- [Browserbase Competitor Analysis](https://github.com/browserbase/skills/blob/main/skills/competitor-analysis/SKILL.md)
- [Agent Skills specification](https://agentskills.io/specification)

本仓库独立编写实现和合成测试资料，不包含以上项目的源码副本，也不依赖它们运行；致谢不代表相关组织背书。
