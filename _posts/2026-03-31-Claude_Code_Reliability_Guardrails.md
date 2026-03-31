---
layout: post
title: Claude Code 为什么不容易失控：从源码看它的执行护栏
description: 不少 Agent CLI 追求“想到就做”，Claude Code 更像是在做“可控执行”。本文基于 Claude Code 2.1.88 的 sourcemap 还原样本，拆解它在工具暴露、权限判定、Shell 安全、并发调度和 harness 隔离上的五道执行护栏。
date: 2026-03-31
tags: AI Claude Code Agent CLI 技术笔记
---

> 作者：litianc
>
> 时间：2026年3月31日
>
> 阅读时长：9分钟

## 前言

如果你最近用过几款 Agent CLI，大概会有一个很直观的感受：它们都很能干，但不一定都很稳。

有的工具给模型一把梭地开放终端、文件系统和网络能力，主打一个“想到了就直接做”；这种体验确实爽，但副作用也很明显。一旦模型判断失误、提示词被带偏，或者工具调用顺序稍微乱一点，轻则改错文件、跑错命令，重则把工作区和上下文一起带偏。

我最近在读 Claude Code 的 sourcemap 还原样本时，越来越强烈地感受到一件事：**Claude Code 之所以看起来“不容易失控”，并不主要是因为模型更聪明，而是因为它外面那层执行框架更严。** 换句话说，很多 Agent CLI 在卖“能力”，Claude Code 更像是在做“可控执行”。

更重要的是，在高权限 Agent 逐渐进入真实开发流的当下，这类执行护栏很可能比 benchmark 分数更决定一个工具是否值得长期使用。

本文基于 `@anthropic-ai/claude-code` 2.1.88 npm 包对应的 sourcemap 还原样本来分析。先交代三个边界：

- 这不是 Anthropic 官方开源仓库，我讨论的是一个研究样本，不把它当成官方权威文档。
- 本文关注的是其中呈现出来的工程设计思路，而不是逐行逐句做源码考据。
- 文中所说的“可靠”，主要指**执行层面的可控性**，不是指模型回答一定更准确，也不是说它绝对安全。

## 一、先把“可靠”说清楚：不是答得更对，而是更不容易乱来

在 Agent CLI 里，“可靠”其实至少有两层意思。

第一层是**结果可靠**：模型理解需求是否准确，生成的代码是否正确。这更多取决于模型本身、上下文质量和任务难度。

第二层是**执行可靠**：当模型决定调用工具时，这个动作会不会越权、误删、乱跑、状态串掉，或者把一些本来不该暴露的信息带出去。

这篇文章讨论的是第二层。因为从源码角度看，Claude Code 在这件事上做了不少“看起来有点麻烦，但工程上很值”的设计。大致可以归成五道护栏：

1. 模型看到的能力，不等于系统真实拥有的全部能力
2. 每次 tool use 在执行前都要过一遍护栏流水线
3. Shell 不是裸奔的，危险路径和绕过技巧会被单独处理
4. 并发执行不是简单的 `Promise.all`
5. harness 自己的内部状态、提示通道和文件路径是隔离出来的

下面一条条看。

先放一张简化对照表，方便后文理解：

| 维度 | 很多 Agent CLI 的常见倾向 | Claude Code 源码里看到的倾向 |
|------|------|------|
| 工具暴露 | 先全量暴露，再在调用时拦截 | 先过滤工具池，再决定模型能看到什么 |
| 工具执行 | 收到 tool use 后尽快执行 | 先过 hooks、classifier、permission 流水线 |
| Shell 安全 | 命令级 allow/deny 为主 | 路径、参数、危险删除单独建模 |
| 并发策略 | 不并发，或直接并发 | 只对 `isConcurrencySafe` 的调用分批并发 |
| 内部状态 | UI、系统、模型文本流容易混在一起 | harness 内部路径和 side channel 明确隔离 |

## 二、第一道护栏：模型看到的能力，不等于系统拥有的全部能力

很多 Agent CLI 的默认思路是：工具系统里有什么，就把什么一股脑暴露给模型。Claude Code 没这么做。

它在 `tools.ts` 里先维护了一份“可能存在的完整工具池”，包括 `BashTool`、`FileReadTool`、`FileEditTool`、`WebFetchTool`、`SkillTool`、`AgentTool`、MCP 资源工具等等。但真正要给模型时，又会再过几层过滤：

- `filterToolsByDenyRules()` 会把被 deny rule 命中的工具直接过滤掉，而且是**在模型看到它们之前**就过滤，不是等模型调用时才拒绝。
- `getTools()` 会根据 `simple mode`、REPL 模式、feature flag、工具启用状态继续裁剪。
- `assembleToolPool()` 再把内建工具和 MCP 工具合并，同时保留 built-in 优先级和去重规则。

也就是说，在 Claude Code 这里，“系统安装了某个能力”和“模型此刻能用这个能力”是两回事。这个区别非常关键。

因为一旦你允许模型先看到某个危险工具，再在调用阶段拦截它，你已经把一部分系统结构暴露出去了。Claude Code 选择的是更保守的做法：**能不让模型看到的，就尽量别让它看到。**

这点和很多“开放能力优先”的 Agent CLI 很不一样。后者往往更强调扩展性，前者更强调最小暴露面。

## 三、第二道护栏：每一次 tool use，都要先过一条执行流水线

Claude Code 的工具执行不是“模型发来一个 tool_use，然后直接 `tool.call()`”。真正的执行路径要长得多。

而且这种“绕”不是后期补丁，而是从工具协议层就写进去了。在 `Tool.ts` 里，tool protocol 预留了 `validateInput()`、`checkPermissions()`、`preparePermissionMatcher()`、`toAutoClassifierInput()` 这些入口。也就是说，Claude Code 的 tool abstraction 从一开始就不是“可调用函数”，而是“带验证、权限和可观测性的执行单元”。

从 `QueryEngine.submitMessage()` 进入后，`query()` 会收集模型返回的 `tool_use` block；到了真正执行阶段，再把它们交给 `runTools()` 或 streaming executor。

真正像“执行护栏内核”的代码在 `toolExecution.ts`：

```ts
startSpeculativeClassifierCheck(...)

for await (const result of runPreToolUseHooks(...)) {
  ...
}

const resolved = await resolveHookPermissionDecision(
  hookPermissionResult,
  tool,
  processedInput,
  toolUseContext,
  canUseTool,
  assistantMessage,
  toolUseID,
)
```

这一段至少做了四件事：

1. **先启动 classifier**：对 Bash 命令做投机式的安全分类检查，而不是等到最后一刻才想起来风险控制。
2. **再跑 pre-tool hooks**：允许外部钩子在工具实际执行前插入检查、补充上下文、修改输入，甚至直接阻止继续执行。
3. **然后统一收敛 permission decision**：不管是 hook 返回的决定，还是运行时权限系统、交互式审批、自动模式分类器，最后都落在同一个 permission decision 上。
4. **拒绝也要结构化回写**：如果没通过，不是简单抛异常，而是生成带 `tool_result` 的结构化错误消息，明确告诉模型这次调用为什么没被允许。

这条流水线背后的设计取向很清楚：**工具执行不是一个函数调用问题，而是一个编排问题。**

一旦你把工具执行看成编排问题，就会自然地引入 hook、permission、telemetry、decision source、structured rejection 这些东西；而不是只盯着“工具跑没跑起来”。

## 四、第三道护栏：Shell 不是裸奔的，危险路径会被单独拎出来处理

如果说前两道护栏更多是框架层的设计，那 BashTool 的路径验证就是最硬核、也最有说服力的一层。

先看第一段：

```ts
if (isDangerousRemovalPath(absolutePath)) {
  return {
    behavior: 'ask',
    message: `Dangerous ${command} operation detected...`,
    suggestions: [],
  }
}
```

这段来自 `pathValidation.ts`。它做的事情很直接：对于 `rm` / `rmdir` 这类删除命令，只要目标是关键系统路径，就必须显式审批，**即使存在 allowlist 规则也不能自动放行。**

这一点很重要。很多系统做权限时容易掉进一个坑：既然用户曾经“允许过某类命令”，那同类命令就一路绿灯。Claude Code 在这里专门把“危险删除”从一般 allow rule 中拔了出来，单独处理。

更有意思的是第二段，它防的不是“粗心误删”，而是**绕过技巧**：

```ts
// rm -- -/../.claude/settings.local.json
// ... naive filter drops it, validation sees zero paths
function filterOutFlags(args: string[]): string[] {
  let afterDoubleDash = false
  ...
}
```

注释写得非常直白：如果你天真地把所有以 `-` 开头的参数都当成 flag，那么在 POSIX 语义里，`--` 后面的参数就会被误判，导致像 `rm -- -/../.claude/settings.local.json` 这种 payload 绕过路径校验。

换句话说，Claude Code 的 Bash 安全不是“给 Shell 套一层 if 判断”，而是**真把 shell 参数解析当成安全边界来对待**。

这类细节特别能说明问题。因为只有在你认真把 Agent CLI 当成“可能被绕过的执行系统”来设计时，才会去补这种边缘 case。

### 权限默认不是放行，sandbox 打开后还会再补一层

除了 Bash 参数解析，Claude Code 的文件权限逻辑本身也是偏保守的。比如在 `filesystem.ts` 里，工作目录判定不是简单做一个“路径字符串是不是以 cwd 开头”的比较，而是会同时考虑原始路径和 symlink 解析后的路径，避免符号链接、路径展开差异带来的误判。

更重要的是，如果路径既不在 working directory，也没有明确规则允许，那么默认结果不是“先试试看”，而是直接 `ask`。

```ts
// Default to asking for permission
return {
  behavior: 'ask',
  message: `Claude requested permissions to read from ${path}...`,
}
```

这其实就是一个很典型的 fail-closed 设计：**拿不准时，不自动放行。**

而如果 session 本身打开了 sandbox，Claude Code 还会再补一层宿主机级别的写保护。在 `sandbox-adapter.ts` 里，它会显式把 `settings.json`、`.claude/skills` 等路径加入 `denyWrite`，甚至还会清理可能被人故意植入的 bare repo 文件，防止后续 unsandboxed git 调用看到这些“埋雷”。

这说明它的安全策略不是单层的“权限弹窗”，而是**权限系统一层、sandbox 一层，能在不同层面都拦就尽量都拦。**

## 五、第四道护栏：并发执行不是简单的 Promise.all

另一个很容易让 Agent CLI 失控的点，不是权限，而是状态。

尤其是工具一多，很自然就会有人写出这种逻辑：只要看起来像只读操作，就一把 `Promise.all` 并发执行。问题是，只读与否并不总是容易判断；更麻烦的是，就算并发执行本身没问题，**上下文怎么合并**也是一门学问。

Claude Code 在 `toolOrchestration.ts` 里做得相当克制：

- 先按 `isConcurrencySafe` 把工具分成批次。
- 并发批次只运行“连续的可并发块”；不可并发的工具还是串行。
- 并发执行时，context modifier 不会立刻写回，而是先排队，等整个批次跑完再按工具顺序回放，降低状态漂移的概率。

这其实是一种很典型的“系统软件思维”：**并发不是为了快，而是为了在不破坏状态一致性的前提下变快。**

如果你对比不少 Agent CLI 的实现，会发现很多系统要么完全不并发，牺牲效率；要么直接并发，牺牲确定性。Claude Code 在这里做的是第三种选择：有条件地并发，而且把上下文合并本身当成正式问题来处理。

## 六、第五道护栏：harness 自己的内部状态、文件路径和侧信道是隔离的

前面几道护栏都还属于“工具怎么跑”。最后这道更偏架构层：**harness 自己的内部世界，没有跟模型看到的世界混在一起。**

一个很典型的例子在文件权限里。读取权限的默认逻辑是：

- 工作目录内允许读
- internal harness paths 允许读
- 规则允许则放行
- 否则默认 ask

相关代码在 `filesystem.ts`。其中这行注释非常关键：

```ts
// Allow reads from internal harness paths (session-memory, plans, tool-results)
```

也就是说，Claude Code 明确区分了“用户工作区”和“harness 内部运行文件”，后者是作为一类受控内部路径存在的，不是随便混进工作目录里。

另一个很有意思的点，是它对工具输出里的 side channel 做了专门协议：

```ts
// The harness scans tool output for these tags, strips them before
// the output reaches the model, and surfaces an install prompt to the user
```

这段来自 `claudeCodeHints.ts`。简单说，CLI 或 SDK 可以在工具输出里埋一个 `<claude-code-hint />` 标签，harness 会识别它、从模型可见输出中剥离，再用它驱动 UI 上的安装提示。

这里其实很适合打一个通俗的比方。很多 Agent CLI 像是一间前厅和后厨没分开的餐馆：顾客坐在桌边，抬头就能看到备菜台、采购单、收银小票，甚至厨师之间的喊话。信息当然更多，但也更乱。Claude Code 明显不是这个思路。它更像一家前厅后厨分开的餐馆：哪些是给顾客看的菜单，哪些是后厨内部的备料单，哪些是服务员之间的对讲信息，系统里分得比较清楚。

放到源码里看，`session memory`、`plans`、`tool results` 这类内部文件路径，会被当作 harness 自己的内部路径处理；而像 `<claude-code-hint />` 这样的提示信号，也会先被 harness 识别并剥离，再决定是否展示给用户，而不是直接原样丢给模型。说白了，Claude Code 不是没有“后台”，而是这个后台不会轻易跑到前台来。

## 七、所以，Claude Code 为什么不容易失控

如果把上面几道护栏压缩成一句话，那就是：

**Claude Code 把 Agent CLI 真正当成了一个“带副作用的执行系统”来设计。**

不是说模型想干什么就干什么，而是：

- 先决定模型能看到什么能力
- 再决定每个工具调用要过哪些检查
- 对 Shell 这种高风险能力做专门的路径与参数防护
- 对并发状态做保守编排
- 把 harness 自己的内部状态与模型上下文显式隔离

很多 Agent CLI 的产品思路更像“把大模型接上终端”。Claude Code 的思路更像“在大模型外面包一层系统软件”。

这也是为什么我更愿意把它理解成一个 harness，而不只是一个 CLI。

## 八、这不等于绝对安全

最后还是要收一下边界，避免把结论说大了。

第一，本文分析的是 2.1.88 版本的还原样本，足够说明设计思路，但不代表 Anthropic 内部实现的全部上下文。

第二，本文所说的“更可靠”，主要指**执行可控性**。它不等于模型就一定理解得更对，也不等于不会写错代码，更不等于绝对安全。

第三，Claude Code 本身依然是一个高权限 Agent 系统。只不过它在源码层面，很明确地表现出一种态度：高权限能力要被编排、被限制、被审计，而不是直接裸露给模型。

## 九、总结

回头看这次源码阅读，最值得记下来的其实不是某一个技巧，而是一种取向。

很多 Agent CLI 解决的是“怎样让模型能做更多事”，Claude Code 解决的是“怎样让模型在做事时不那么容易失控”。前者强调能力上限，后者强调执行边界；前者更像把大模型变成操作员，后者更像给这个操作员配了一整套护栏、值班员和记录系统。

这也是我读完源码之后，对 Claude Code 最大的改观：它的核心竞争力不只是代码能力，而是那层经常被忽略的 harness。

如果把视角再拉远一点，这其实也是下一阶段 Agent CLI 分化的关键。比起“还能多接几个工具”，谁能把副作用约束住、把状态收拢住、把高权限动作编排好，谁才更接近一个能被长期信任的工程系统。

如果后面继续写这个系列，我打算下一篇换个角度，回到 Claude Code 的模型请求本身：它发给上游的请求到底长什么样，以及这些请求画像里的细节，为什么可能让逆向接口更容易被识别，甚至带来额外的封号风险。
