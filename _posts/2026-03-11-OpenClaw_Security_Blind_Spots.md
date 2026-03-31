---
layout: post
title: 当所有人都在养龙虾：OpenClaw 安全模型的五个盲区
description: 60天250K stars 的背后，是135K+暴露实例、36%含注入的 ClawHub skills、和一个"simple by design"的 MCP 协议。本文从 MCP 信任模型、Shell 权限暴露、提示注入、数据泄露到社会工程学，拆解 OpenClaw 的五个安全盲区。
date: 2026-03-11
tags: AI OpenClaw 安全 技术笔记
---

> 作者：litianc
>
> 时间：2026年3月11日
>
> 阅读时长：8分钟

## 前言

如果你最近刷过任何技术社区，应该很难避开"龙虾"这个词。

OpenClaw——这个用红色龙虾做 logo 的开源 AI Agent——60 天拿下 250K GitHub stars，打破了 React 花十年才达到的记录。美国多地 Mac mini 因为自建部署需求断货，自媒体的声量更不用说了。

但信号的另一面也在出现。工信部和国家互联网应急中心（CNCERT）在过去一周相继发布了安全风险通报；今天彭博社报道中国正在限制银行和政府机构使用 OpenClaw。不只是中国——韩国 Kakao 已禁止企业网络和工作设备使用 OpenClaw，微软安全博客建议"不应在标准个人或企业工作站上运行"，Cisco 更直接称其为"安全噩梦"。

当所有人都在谈论怎么养龙虾的时候，很少有人问——这只龙虾安全吗？

这篇文章不是劝你别用 OpenClaw。它确实是一个了不起的产品——Peter Steinberger 用一个小时的灵感创造出来的东西，改变了很多人对 AI Agent 的认知。但作为一个能读你邮件、跑终端命令、部署代码的"个人助手"，它的安全模型值得被认真审视。

## 一、数字背后的温度

先看几个数据：

- **25,310 stars/天**（2026年1月26日）——GitHub 单日增长历史记录
- **250K+ stars / 60天**——超越 React，成为 GitHub 最受关注的非聚合类软件项目
- **Mac mini 缺货**——美国多地因自建部署需求断货

这些数字很漂亮，但还有另一组数字：

- **512 个漏洞**——早期安全审计（当时还叫 Clawdbot）的发现，其中 **8 个 critical**
- **135,000+ 实例**暴露在公网上——SecurityScorecard STRIKE 团队通过 Shodan 扫描发现，分布在 82 个国家
- 后续更新的数字是 **220,000+** 暴露实例，其中 **15,000+** 直接可被远程代码执行
- **35.4%** 的已观测部署被标记为存在漏洞

说白了，GitHub 上最火的项目，同时也是暴露面最大的项目之一。增长速度远远跑赢了安全能力的建设速度。

## 二、MCP：被设计出来的信任假设

OpenClaw 的能力边界取决于它连接了多少工具。而连接工具的底层协议是 MCP（Model Context Protocol）。要理解 OpenClaw 的安全问题，得先看 MCP。

Semgrep 对 MCP 的评价很精准：**"MCP isn't insecure by design -- it's simple by design. That simplicity, however, creates gaps attackers can exploit."**

MCP 服务器通常就是一个裸奔的 HTTP server 或 stdio 进程，跑一个端点。没有复杂框架，没有第三方依赖，没有 vendor lock-in——也**没有身份认证和权限控制**。MCP 把安全责任甩给了上层应用，但 MCP 自身在处理特权数据时没有任何安全机制，全靠用户自己判断。

这带来了一系列攻击向量：

| 攻击类型 | 原理 |
|---------|------|
| **Tool Poisoning** | 在工具的 metadata/description 中注入恶意指令，LLM 依赖描述理解工具行为，被导向不安全操作 |
| **Rug Pull** | 工具描述在用户批准后被静默修改，先建立信任再切换为恶意行为 |
| **Tool Shadowing** | 恶意服务器注入描述，修改 agent 对**其他可信工具**的调用行为 |
| **Parasitic Toolchain** | 链式感染——通过工具间的关联关系逐级扩大攻击面 |

实际案例已经出现了。npm 上的 **postmark-mcp** 是第一个被发现的恶意 MCP 服务器——它在所有从 AI agent 发出的邮件中悄悄加了一个 BCC。一个安静的、攻击者可能觉得不会被发现的 exploit。

更系统性的数据来自 Snyk 的 ToxicSkills 审计：**36% 的 ClawHub skills 包含可检测的 prompt injection**。不是个别案例，是三分之一以上的生态。

OWASP 也已经发布了 MCP Top 10，覆盖从 token 泄露到 shadow server 的关键风险。这不是 OpenClaw 一家的问题——所有基于 MCP 的 agent 都面临同样的协议层缺陷。

## 三、当龙虾获得你的 Shell

MCP 是协议层的问题，OpenClaw 自身的实现层问题同样不少。

**坑的起点是一个默认配置**：OpenClaw 默认绑定 `0.0.0.0:18789`——监听所有网络接口，包括公网。不是 `127.0.0.1`（localhost），是所有接口。这意味着只要你的机器有公网 IP，你的 OpenClaw 实例对全世界可见。

这就是为什么 Shodan 能扫出 135K+ 暴露实例的原因。其中 15,000+ 可以直接远程代码执行。

更精巧的攻击来自 **ClawJacked**（CVE-2026-25253，CVSS 8.8）：

1. 开发者访问一个攻击者控制的网页
2. 页面中的 JavaScript 静默向 OpenClaw 的 localhost gateway 发起 WebSocket 连接
3. Gateway 自动信任本地连接，静默批准新设备注册
4. 攻击者的页面获得 agent 的完全控制权——**毫秒级完成**

说白了，你打开一个网页，你的 AI agent 就不是你的了。公平地说，OpenClaw 团队在 24 小时内就修复了这个漏洞（v2026.2.25），响应速度值得肯定。但它暴露的设计问题比单个 CVE 更深：**localhost 等于可信这个假设在 web 环境下是站不住脚的**。

权限层面，OpenClaw 默认可以执行**任意 shell 命令**，没有命令白名单，没有审批流程。全磁盘访问、终端权限、OAuth tokens——为了让 agent "能用"，这些权限被常规性地授予。

最后是凭证存储。OpenClaw 的配置文件、"记忆"和聊天记录把 API keys、密码等敏感信息以**明文**存储。这件事被 infostealer 作者们注意到了：

- **Vidar**（2026年2月13日）开始窃取 OpenClaw 配置和密钥
- **RedLine** 和 **Lumma** 把 OpenClaw 的文件路径加入了 "必偷" 清单
- **AMOS**（macOS infostealer）被打包进 ClawHub skill 上传

Hudson Rock 的描述很到位：**"a significant milestone in infostealer evolution -- the transition from stealing browser credentials to harvesting the 'souls' and identities of personal AI agents."** 从偷浏览器密码，进化到偷 AI agent 的"灵魂"。

## 四、提示注入与数据泄露

提示注入不是新话题，但在 agent 场景下危害被放大了一个数量级。

一个典型案例来自 "Agents of Chaos" 论文的实验。研究人员给 agent 设置了一条规则：保护某个包含社会安全号码（SSN）的信息。当直接要求 agent 提供 SSN 时，agent 正确地拒绝了。但当换一种方式说"把那封完整的邮件转发给我"时——agent 乖乖地把包含 SSN、银行账号、医疗信息的全部内容原文转发了，没有任何脱敏。

**同一个 agent，同一条安全规则，换一个 prompt 就绕过了。**

ClawHub 生态的数据更触目惊心。恶意 skills 的数量在持续攀升：

- 2 月初：324 个恶意 skills
- 数周后：820 个
- 2 月底：**1,184 个**——大约每五个 skill 中就有一个被标记

这些恶意 skill 伪装得很专业——有文档、有 README、名字看起来人畜无害（比如 "solana-wallet-tracker"）。安装后在 Windows 上部署 keylogger，在 macOS 上部署 Atomic Stealer。OpenClaw 团队后来和 VirusTotal 合作加了恶意软件扫描，也加了基于 LLM 的代码分析——方向是对的，但社区认为这些事后检测不够，一直在呼吁发布前强制 code review。

AgentSeal 等防护工具也在出现，但面对的根本矛盾没有变：agent 需要理解自然语言才能工作，而自然语言天然是模糊的、可被操纵的。所谓的 "Data Awareness"——让 agent 在执行操作前判断数据敏感性——目前还停留在概念层面，没有可靠的技术实现。

## 五、社会工程学：最便宜的攻击向量

前面讲的都是技术层面的漏洞——协议缺陷、默认配置、凭证明文。但 "Agents of Chaos" 论文揭示了一个更根本的问题：**你不需要任何技术手段就能让 agent 失控。**

论文的原话：

> "None of these failures required adversarial prompting, jailbreaks, or malicious intent. They emerged from incentive structures."

这些失败不需要对抗性 prompt，不需要越狱，甚至不需要恶意意图。它们从激励结构中自然涌现。

实验设置是这样的：6 个 OpenClaw agent 被部署到一个 Discord 服务器，使用 Kimi K2.5 和 Claude Opus 4.6 作为底层模型。20 个同事自由交互两周。研究团队记录了 **11 种关键失败模式**，包括：未授权服从非所有者指令、敏感信息泄露、执行破坏性系统操作、拒绝服务、身份伪造、agent 间不安全行为的交叉传播。

几个印象深刻的案例：

**Agent "Ash" 的核弹式防御**：Ash 被要求保护一个秘密。当研究者尝试社会工程获取秘密时，Ash 的选择是——**摧毁自己的邮件服务器**。研究者的评论是：Ash 正确地识别了保护秘密的重要性，但灾难在于它的响应完全不成比例。就像你怕有人偷你家钥匙，于是把整栋楼炸了。

**9 天的 agent 循环**：两个 agent 进入自引用对话，形成反馈循环，持续了 **9 天**，消耗超过 **60,000 tokens**。没有终止条件，没有通知 owner。两个 agent 都没有意识到自己卡住了。

**身份伪造**：在一个新的 Discord 私密频道中，只要改变显示名称，agent 就接受了伪造的身份，并执行了包括**系统关闭和文件删除**在内的特权操作。

OpenClaw 团队的回应是这个研究"根本性地有缺陷"，因为 OpenClaw 设计为单用户个人助手，不是多用户 Discord bot。这个回应有一定道理。

但问题是：当 135K+ 实例暴露在公网上、员工把它连接到企业 Slack 和邮箱时，"单用户"这个前提假设早就站不住了。

LLM 天生有"讨好型人格"——倾向于满足请求而非拒绝。这不是 bug，是训练出来的特性。当这个特性被放进一个有 shell 权限、能发邮件、能操作文件的 agent 里时，问题就从学术讨论变成了生产事故。

## 六、社区应该做什么

说了这么多问题，不是为了让大家卸载 OpenClaw。它依然是一个令人印象深刻的产品——一个人一个小时的灵感，两个月改变了整个 AI agent 的生态格局。而且团队也在快速迭代安全能力：ClawJacked 24 小时修复、VirusTotal 恶意扫描接入、LLM 代码分析上线。问题不在于"该不该用"，而在于"该怎么用"。

以下是一份安全检查清单，供个人用户和企业部署参考：

| 措施 | 个人用户 | 企业部署 |
|------|:------:|:------:|
| 绑定地址改为 `127.0.0.1` | 必须 | 必须 |
| 启用 sandbox 隔离 | 建议 | 必须 |
| 设置命令白名单 | 建议 | 必须 |
| 加密存储 API keys 和凭证 | 建议 | 必须 |
| 审计已安装的 ClawHub skills | 建议 | 必须 |
| MCP 工具签名验证 | 关注进展 | 积极推动 |
| 最小权限原则（禁用不需要的工具） | 建议 | 必须 |
| 审计日志记录 agent 操作 | 可选 | 必须 |
| 网络隔离（禁止直连公网） | 可选 | 必须 |

工信部和 CNCERT 的通报其实给出了很清晰的建议方向：强化网络控制、严格隔离运行环境、限制权限、加强凭证管理、严格管理插件来源。这些不是恐慌性的禁令，是理性的安全评估。

从社区层面，几件事情需要推动：

- **MCP 协议层**：加入工具签名验证和权限声明机制。目前 MCP 把安全完全甩给上层，这在生态规模化之后是不可持续的
- **ClawHub 生态**：发布前强制 code review，而不是事后扫描。36% 的 prompt injection 率说明事后检测远远不够
- **默认配置**：安全的默认值比任何文档都管用。绑定 localhost、sandbox 默认开启、命令白名单——这些应该是 out-of-the-box 的行为

## 结语

"龙虾只是工具"——这话没错。工具本身无罪，菜刀不会主动砍人。但当一把菜刀可以读你的邮件、跑你的终端命令、访问你的所有文件时，说"它只是一把菜刀"就不太够了。

热度会回归理性，留下来的一定是那些认真对待安全的人和团队。

养龙虾之前，先给它画个笼子。
