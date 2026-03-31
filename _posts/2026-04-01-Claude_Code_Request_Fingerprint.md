---
layout: post
title: Claude Code 的请求形态与 Max 账号复用：一次请求指纹引发的拆解
description: 很多人做 Claude Max 账号复用时，第一反应是模仿一个 User-Agent。但从还原源码看，真正难模仿的不是某一个 header，而是一整套会随着模型、工具池、上下文和会话状态一起变化的请求形态。本文拆解这套请求画像，并讨论它为什么可能让 Max 账号复用链路与真实官方客户端之间出现更多可见差异。
date: 2026-04-01
tags: AI Claude Code Claude Max API 技术笔记
---

> 作者：litianc
>
> 时间：2026年4月1日
>
> 阅读时长：10分钟

## 前言

最近在看一些基于 Claude Max 账号复用的接口实现时，我越来越觉得，一个常见误区是：很多人会把精力过度集中在 `User-Agent` 上，仿佛把这一项改对，整个请求就已经“像 Claude Code”了。

这当然重要，但看完源码之后，我越来越觉得，`User-Agent` 只是最表面的一层。真正难模仿的，不是某一个 header，而是一整套会随着模型、工具池、上下文和会话状态一起变化的请求形态。你可以抄到某一时刻的请求，但这不等于你能持续复现它背后的生成逻辑。

先把结论放在这里：**做 Claude Max 账号复用这件事，最难的不是“把请求发出去”，而是让请求在多轮交互里持续看起来更像一个真实官方客户端。** 而从源码里能看到，Claude Code 发给上游的请求并不是一个固定模板，而是经过多轮拼装、规范化和修补之后的动态结构。

需要先说明两点。第一，本文分析使用的 Claude Code 源码并非来自官方开源仓库，而是取自网络上传播的、基于公开发布包整理出来的研究样本，真实性、完整性和传播背景需要读者自行判断。第二，本文讨论的是**可能的识别线索**，不是在下结论说“这就是官方封号规则”。上游真正怎么做风控，我们并不知道。

## 一、为什么问题不在单个 Header，而在整个 Request Shape

如果只是从“能不能调用成功”的角度看，很多接口兼容层其实已经做得不错：模型名对上了，endpoint 对上了，header 也补得差不多，服务端就会给你一个正常响应。

但问题来了：**能调通，不等于长得像。**

从工程角度看，一个客户端请求像不像“官方客户端”，往往不是看单个字段，而是看一整组前后一致的信号：

- 请求头长什么样
- 认证方式怎么选
- body 顶层有哪些字段
- `messages` 是不是原样转发，还是经过整理
- `tools` 和 `system` 是不是静态模板，还是按运行时动态生成
- 同一会话的请求在多轮交互里，是不是保持了类似的变化规律

也就是说，真正值得看的不是某个 header，而是整个 request shape。这个词翻成中文有很多版本，我这里先叫“**请求形态**”。

回过头来看，这也解释了为什么很多 Max 账号复用链路一开始似乎都“差不多”，但越跑越容易出现差异。因为真正难复现的，从来不是静态截图里的那一帧，而是它背后的生成过程。

![图 1：Claude Code 请求形态的五层结构](/images/posts/claude_code_request_fingerprint/01-request-shape-layers.svg)

## 二、真实 Claude Code 请求长什么样

### 2.1 先分清两类请求

先说一个很容易混淆的地方。Claude Code 代码里至少存在两类不同的 `User-Agent` 构造方式：

1. 一类是 `claude-code/${version}` 这种更短的格式。

2. **主模型请求**  
   在主请求路径里，`User-Agent` 用的是 `claude-cli/${version} (...)`，不是上面那个。

如果你不先把这两类格式拆开，后面看 request shape 很容易得出错误结论。

### 2.2 主模型请求的顶层结构

后文主要分析的是 first-party Anthropic messages 这条主请求路径。从 `claude.ts` 里的 `paramsFromContext()` 看，发往上游的请求大致长这样：

```json
{
  "model": "...",
  "messages": [...],
  "system": [...],
  "tools": [...],
  "tool_choice": ...,
  "betas": [...],
  "metadata": {...},
  "max_tokens": ...,
  "thinking": ...,
  "temperature": ...,
  "context_management": ...,
  "output_config": ...,
  "speed": ...
}
```

这些字段不是每次都全有，但它们构成了主模型请求的基本骨架。换句话说，Claude Code 发给上游的不是一个“只有 messages 的简化聊天请求”，而是一个包含工具、system prompt、上下文管理、thinking 和输出配置的 agentic request。

![图 2：主模型请求的结构示意图](/images/posts/claude_code_request_fingerprint/02-request-anatomy.svg)

### 2.3 一张总表：哪些是稳定信号，哪些是易变信号

| 层次 | 典型字段 | 稳定性 | 可能形成差异的强度 |
|------|------|------|------|
| Header | `x-app`、`User-Agent`、`X-Claude-Code-Session-Id` | 中等 | 高 |
| 认证 | `Authorization` / `x-api-key` / `anthropic-beta` | 中等 | 高 |
| 顶层 body | `model/messages/system/tools/...` | 高 | 高 |
| Metadata | `device_id/account_uuid/session_id` | 中等 | 高 |
| Message 形态 | `tool_use/tool_result` 的组织方式 | 低 | 很高 |
| Tool schema | `description/input_schema/defer_loading/cache_control` | 低 | 很高 |
| System blocks | 分块、`cache_control`、动态 prepend | 低 | 很高 |

这张表最值得注意的一点是：**越靠近运行时生成逻辑的部分，稳定性越低，但越可能与一个“只模仿表面字段”的接口形成差异。**

## 三、Max 账号复用链路最容易出现差异的几类信号

### 3.1 `User-Agent` 不是单个版本号，而是带上下文的结构化标识

主模型请求的 `User-Agent` 不是简单的：

```text
claude-cli/2.1.88
```

而是更接近：

```text
claude-cli/${version} (${USER_TYPE}, ${ENTRYPOINT}, agent-sdk?, client-app?, workload?)
```

也就是说，它里面除了版本号，还会带：

- `USER_TYPE`
- 入口点 `CLAUDE_CODE_ENTRYPOINT`
- `agent-sdk` 版本
- `client-app`
- `workload`

如果一个接口只模仿了最前面的 `claude-cli/x.y.z`，但后面的环境信息长期缺失、固定不变或组合不合理，那它和真实客户端之间其实还是有可见差异。

### 3.2 主请求头里不只有 `User-Agent`

在主请求路径里，比较稳定会出现的是：

- `x-app: cli`
- `X-Claude-Code-Session-Id`

按场景可能出现的还有：

- `x-client-app`（SDK 场景）
- `x-claude-remote-container-id`
- `x-claude-remote-session-id`
- `x-anthropic-additional-protection`（特定场景）
- `x-client-request-id`（first-party 直连）

其中 `x-client-request-id` 很有意思。它不是业务必需字段，而是客户端为了把超时请求和服务端日志对应起来，自动注入的随机 UUID。一个“能用但不太像官方”的客户端，很可能压根不会补这种辅助诊断字段。

### 3.3 认证方式本身也是请求画像

从认证逻辑看，Claude Code 不是只支持一套 auth。常规路径大致是：

- 订阅用户走 OAuth：
  - `Authorization: Bearer ...`
  - `anthropic-beta: OAUTH_BETA_HEADER`
- 非订阅用户走 API key：
  - `x-api-key`

但这里也不能说得太死。代码里还能看到一些非订阅场景会额外走 `Authorization: Bearer ...` 的路径，所以更准确的说法是：**认证头和认证模式并不是完全固定模板，而是会随着账号类型和运行环境分叉。**

这意味着，请求头和认证路径是联动的，而不是“拿什么 key 都走同一套 header 组合”。

如果一个接口在所有场景下都统一使用相同 header 组合，那它和真实客户端之间的差异就不只是“细节没抄全”，而是连认证路径都没对上。

### 3.4 `metadata.user_id` 并不是普通 UUID

这部分我觉得特别值得单独拎出来。Claude Code 的 `metadata` 里最关键的字段是：

```ts
{
  user_id: jsonStringify({
    ...extra,
    device_id,
    account_uuid,
    session_id
  })
}
```

也就是说，`metadata.user_id` 本身是一个 **JSON 字符串**，里面再包一层：

- `device_id`
- `account_uuid`（非 OAuth 场景下可能为空字符串）
- `session_id`
- 以及环境变量提供的额外 metadata

如果一个 Max 账号复用接口把 `metadata.user_id` 当成普通字符串、简单 UUID，或者干脆不传，那和真实请求的差异就已经不是“长得不太像”，而是“形状都不一样”。

### 3.5 body 顶层字段是动态组合出来的，不是死模板

真正发请求前，Claude Code 还会动态决定这些字段：

- `betas`
- `thinking`
- `output_config`
- `context_management`
- `speed`

这些字段受模型能力、provider、feature gates、fast mode、thinking 配置、task budget 等多种条件影响。

而且这里还有一个容易被忽略的细节：**beta 的传输方式本身也可能因 provider 而变。** 在 first-party 直连场景里，很多 beta 是通过 SDK 的 `betas` 参数传出去的；但到了 Bedrock 这类 provider，一部分 beta 又会被搬进 body 里的额外字段，而不是保持同样的传输路径。对 Max 账号复用链路来说，这种“同一类能力，不同 provider 走不同装配方式”的细节，往往比字段名本身更难补齐。

另一个更隐蔽的点是，有些 beta 不是“当前开关是什么，就实时发什么”，而是为了保持 cache key 稳定，会在一个 session 里锁住。也就是说，即使表面上看是动态字段，它们的变化规律也不一定是线性的“打开就出现，关闭就消失”。这类行为对真实客户端是工程优化，对兼容实现却很像隐藏的状态机。

所以，从 Max 账号复用的实现角度看，最危险的误区就是：拿一份抓包请求，当作永久模板。短期也许能跑通，长期大概率会越来越不像。

## 四、真正难模仿的，不是字段本身，而是发送前的“整理过程”

如果说前一节还在讲“请求长什么样”，这一节就是这篇文章真正的重点：**Claude Code 发出去的请求，不是当前会话对象的原样序列化，而是经过一轮发送前整理之后的结果。**

### 4.1 `messages` 会被规范化，不是原样转发

在 `normalizeMessagesForAPI()` 里，至少会发生这些事情：

- attachment 位置被重排
- display-only 的 virtual message 被去掉
- `progress`、大部分 `system` 消息不会进 API
- `local_command` 系统消息会被转成 user turn
- 连续 user message 会被合并
- assistant message 会按 `message.id` 重新合并

也就是说，用户在 REPL 里“看到的历史”，和真正发给上游的 `messages`，并不是一回事。

### 4.2 `tool_use` 会被标准化，`caller` 这类字段会按条件剥离

assistant 里的 `tool_use` 在发送前会做这些处理：

- tool input 按工具规则规范化
- tool name 被 canonicalize
- legacy / injected 字段会被去掉
- 关闭 tool search 时，`caller` 会被显式剥掉

这点非常关键。因为很多兼容层只会“保留之前请求里的字段”，但真实客户端其实会按当前模式把某些字段删掉。如果一个请求长期带着本不该出现的 `caller`，或者反过来缺少该出现的字段，差异就出来了。

### 4.3 `tool_use/tool_result` 不匹配时，客户端还会主动修

`ensureToolResultPairing()` 会在最后阶段处理很多结构问题：

- orphaned `tool_result`
- duplicate `tool_use`
- orphaned server tool uses
- 缺失的 `tool_result`
- role alternation 被破坏

必要时它甚至会插入 synthetic error `tool_result` 或占位文本，保证请求结构至少符合 API 的要求。

这就解释了一个很现实的问题：**抓包抓到的“正常请求”只是一帧结果，它背后可能已经经过客户端修补。**  
如果你只是抄最终结果，而没有实现这些修补逻辑，那么下一轮请求一旦会话状态变化，就很可能出现偏差。

### 4.4 `tools` 和 `system` 也不是静态模板

`tools` 不是写死的 JSON，而是每轮调用 `toolToAPISchema()` 动态生成。它由两层组成：

- session-stable 的 base schema
- per-request 的 overlay，比如 `defer_loading`、`cache_control`

而 `system` 也不是一段大字符串，而是拆成多个 text block，再按块打上 `cache_control`。真正发出去前，还会额外拼上 attribution header、CLI prefix、advisor/chrome 相关 instructions。

说白了，真实客户端的请求，不只是“内容在变”，而是“生成内容的管道也在变”。

![图 3：发送前的整理流水线](/images/posts/claude_code_request_fingerprint/03-normalization-pipeline.svg)

## 五、为什么单点伪装不够

回过头来看，这些细节共同指向一个结论：**Max 账号复用链路最容易在一致性上出现问题。**

你当然可以：

- 改 `User-Agent`
- 补一个 `x-app: cli`
- 加上 `messages/tools/system`
- 模拟一部分 `metadata`

但问题是，真实官方客户端不是这些东西的静态合集，而是一组彼此联动的信号：

- `User-Agent` 和 auth 路径要一致
- `metadata` 和 session 行为要一致
- `tools` 和当前模型能力要一致
- `messages` 的形态和会话历史要一致
- `betas/output_config/thinking` 和当前 feature state 要一致

只改一个点，当然可能让请求“更像”；但如果其它层没有跟着一起像，反而更容易形成一种别扭的状态：**某些字段看起来像，整体行为却不像。**

这就解释了为什么很多人会有一种体验：早期调通很顺，但越往后越不稳定。因为你模仿的是一帧成功请求，不是生成这帧请求的机器。

## 六、怎么做验证，怎么避免误判

如果后面真要验证“某个 Max 账号复用接口是不是更容易出现差异”，我建议不要只看单个抓包 diff，而是按下面这个顺序做对照：

1. **Header 对照**  
   对比 `User-Agent`、`x-app`、session 相关头、client request id 是否存在

2. **认证路径对照**  
   对比 OAuth / API key 场景下 header 组合是否一致

3. **顶层 body 对照**  
   看 `messages/system/tools/metadata/betas/thinking/output_config` 哪些字段缺失、多出或长期固定

4. **多轮会话对照**  
   看第二轮、第三轮之后，请求是否仍保持类似变化规律

5. **异常路径对照**  
   比如 tool_result 缺失、tool search 开关变化、附件过大、provider 切换时，请求结构是否还能自洽

这里最重要的是第五步。因为很多“像不像”的差异，不是在 happy path 上暴露的，而是在边缘条件下露出来的。

当然，最后还是要强调边界：即使你看到请求差异，也不能直接推导出“这就是封号原因”。更合理的说法是：

**这些差异是可能的识别线索，会提高一个 Max 账号复用接口显得不像官方客户端的概率。**

IP、支付方式、账号年龄、流量模式、地理位置、中间网关的二次加工，甚至上游看不到的内部风控逻辑，都可能参与判断。

## 总结

如果只用一句话概括这次排查，我会这么说：

**Max 账号复用最难模仿的不是功能，而是一致性。**

很多人以为 Claude Code 的“官方感”来自某一个 `User-Agent`，但从这份还原源码看，更像是一整套请求形态共同构成了它的身份：header、认证、metadata、tools、system、message normalization、tool-result 修补，这些东西一起作用，才把一个请求塑造成“更像官方客户端”的样子。

也正因为如此，Max 账号复用真正难的，并不只是“发出一份成功请求”，而是让后续每一轮请求都继续保持相近的形态。

如果后面继续写这个方向，我更想做的一件事，是把这些请求形态整理成一份自动化审计清单，专门用来检查一个“自称兼容 Claude Code”的接口，到底在哪些层看起来还不像。  
