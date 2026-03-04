---
layout: post
title: 当 User-Agent 被改写：一次 OAuth 封号的完整排查
description: 真实的 Claude Code 请求经过中间网关时 User-Agent 被改写，导致模型调度平台的三重身份伪装防线同时失效，真实 metadata.user_id 泄露给上游，OAuth 账户秒封。本文还原完整的事故链条和排查过程。
date: 2026-03-04
tags: Go OAuth 安全 技术笔记
---

> 作者：litianc
>
> 时间：2026年3月4日
>
> 阅读时长：7分钟

## 前言

用过共享模型账号的同学应该知道，封号这事儿就像开盲盒——有时候用了几个月相安无事，有时候第一个请求发出去账号就没了。

前两篇文章（[并发控制排查]({% post_url 2026-03-02-OpenClaw_Concurrency_Control %})、[LiteLLM Session 注入]({% post_url 2026-03-03-LiteLLM_Session_Injection %})）解决了会话计数累加的问题，整条链路跑得好好的。结果就在我以为可以收工的时候，一个 OAuth 账户在发出第一个请求后瞬间被封禁了。

一个请求，秒封。

排查后发现，问题出在一个极其不起眼的地方：请求经过中间网关时，`User-Agent` 从 `claude-cli/2.1.22 (external, cli)` 被改写成了 `Anthropic/JS 0.73.0`。就这一个 header 的变化，像推倒了多米诺骨牌一样，让模型调度平台内部精心设计的三重身份伪装防线同时失效——最终，我的真实账户信息原封不动地暴露在了上游的请求体里。

Token 说的是账户 A，`metadata.user_id` 说的是账户 B。上游一看，身份冲突，封禁。

这篇文章完整还原这条事故链：从请求如何被转发，到身份伪装机制如何运作，再到三重防线为何同时失效。

## 一、请求链路全貌

先交代一下我的使用架构。我用真实的 Claude Code 客户端发起请求，中间经过一层反向代理网关，再转发到模型调度平台，最后由平台转发至上游 Anthropic API：

```
真实 Claude Code 客户端
  → 中间网关（反向代理）
  → 模型调度平台
  → 上游 Anthropic API
```

模型调度平台的核心职责之一，是把多个用户的请求通过少量 OAuth 账户转发给上游。由于上游会检测请求是否来自合法的 Claude CLI 客户端，平台内置了一套"伪装机制"（mimic）——对非 Claude Code 客户端发来的请求，自动化妆成 Claude Code 的样子再转发。

## 二、三重防线

要理解为什么一个小小的 header 改写能搞出这么大动静，得先看看平台内部的伪装机制长什么样。我把它总结为三重防线，每一重都有各自的职责。

### 第一重：客户端识别——isClaudeCodeClient

平台首先要判断：这个请求是不是来自真正的 Claude Code 客户端？

```go
claudeCliUserAgentRe = regexp.MustCompile(`^claude-cli/\d+\.\d+\.\d+`)

func isClaudeCodeClient(userAgent string, metadataUserID string) bool {
    if metadataUserID == "" {
        return false
    }
    return claudeCliUserAgentRe.MatchString(userAgent)
}
```

两个条件，AND 关系：`User-Agent` 匹配 `^claude-cli/` 的正则，且请求体中存在 `metadata.user_id`。

在我的场景中，UA 被中间网关改成了 `Anthropic/JS 0.73.0`，正则不匹配。于是：

- `isClaudeCode = false`（误判！明明是真的 Claude Code）
- `shouldMimicClaudeCode = true`（触发伪装路径）

**一个真正的 Claude Code 请求被错误地归类为"需要伪装"的非 CC 请求。**

### 第二重：Metadata 注入——buildOAuthMetadataUserID

进入伪装路径后，平台会尝试为请求生成一个与 OAuth Token 匹配的 `metadata.user_id`：

```go
func (s *GatewayService) buildOAuthMetadataUserID(
    parsed *ParsedRequest, account *Account, fp *Fingerprint,
) string {
    if parsed.MetadataUserID != "" {
        return ""   // 客户端已经带了 user_id → 不生成新的
    }
    // ... 生成新的 user_id 的逻辑
}
```

问题来了：我的请求来自真实的 Claude Code，天然携带了 `metadata.user_id`（包含我的真实账户信息）。函数检测到已有值，直接返回空——不注入新的。

设计意图是合理的：如果客户端已经有了 user_id，就不覆盖它，留给后续的重写逻辑处理。但这个"留给后续处理"的假设，很快就会被打脸。

### 第三重：UserID 重写——RewriteUserID

最后一道防线，对所有 OAuth 账户的请求都会执行。它试图把 `metadata.user_id` 中的身份信息替换为与当前 OAuth Token 匹配的值：

```go
userIDRegex = regexp.MustCompile(
    `^user_[a-f0-9]{64}_account__session_([a-f0-9-]{36})$`,
)

func (s *IdentityService) RewriteUserID(body []byte, ...) ([]byte, error) {
    // ... 解析出 metadata.user_id ...
    matches := userIDRegex.FindStringSubmatch(userID)
    if matches == nil {
        return body, nil  // 匹配失败，原样返回
    }
    // ... 重写逻辑 ...
}
```

注意正则中的 `_account__session_`——account 和 session 之间是**两个下划线直接相连**，也就是说 account 部分为空。这个正则只能匹配平台自身在没有 `account_uuid` 时生成的旧格式：

```
user_{64位hex}_account__session_{uuid}
                       ↑↑
                  这里是空的
```

而真实 Claude Code 客户端发送的格式是：

```
user_{64位hex}_account_{真实UUID}_session_{uuid}
                       ↑↑↑↑↑↑↑↑↑↑↑↑
                  这里有真实的账户 UUID
```

**正则不匹配，重写直接跳过。我的真实 `metadata.user_id` 原封不动地传给了上游。**

## 三、事故还原

把三重防线串起来，完整的事故链条是这样的：

```
真实 Claude Code 客户端
  │  发送请求，包含：
  │  - User-Agent: claude-cli/2.1.22 (external, cli)
  │  - metadata.user_id: user_{我的hex}_account_{我的UUID}_session_{...}
  │
  ▼
中间网关
  │  改写 User-Agent → Anthropic/JS 0.73.0
  │
  ▼
模型调度平台
  │
  ├─ 第一重防线 isClaudeCodeClient()：
  │    UA 不匹配正则 → isClaudeCode = false → 走伪装路径
  │    ❌ 误判
  │
  ├─ 第二重防线 buildOAuthMetadataUserID()：
  │    检测到客户端已带 user_id → 不注入新的
  │    ❌ 放弃了主动修正的机会
  │
  ├─ 第三重防线 RewriteUserID()：
  │    正则只匹配 account__session_（空account），
  │    不匹配 account_{真实UUID}_session_
  │    ❌ 重写失败，原样放行
  │
  ├─ Header 伪装 applyClaudeCodeMimicHeaders()：
  │    强制覆写 User-Agent 为 claude-cli/2.1.22
  │    ✅ Header 看起来没问题
  │
  ▼
上游 Anthropic API 收到：
  - OAuth Token：属于池中的账户 A ✅
  - User-Agent：claude-cli/2.1.22 ✅
  - metadata.user_id：user_{我的}_account_{我的UUID}_session_{...} ❌
  → Token 是账户 A，user_id 是账户 B → 身份不匹配 → 封禁
```

Header 层面伪装得很完美，但 body 里的身份信息把一切出卖了——像是换了一身西装走进酒店大堂，口袋里却还揣着另一个人的身份证。

## 四、为什么平时不出问题

搞清楚了 bug 怎么发生的，下一个自然的问题是：这玩意儿藏了多久？为什么之前没人踩到？答案是，日常使用中大多数请求走的是"安全"路径。

**最常见的场景：普通 SDK 客户端，不带 metadata.user_id。**

```
客户端不带 user_id
→ buildOAuthMetadataUserID() 主动生成新的
→ 格式与 OAuth Token 匹配 → 安全 ✅
```

这是绝大多数用户的使用方式。客户端不携带 `metadata.user_id`，平台为它生成一个与 OAuth Token 配套的值，身份一致，一切正常。

**我遇到的场景：真实 Claude Code 请求，UA 被改写。**

```
UA 被改 → 误判为非 CC → 走伪装路径
→ 但客户端已带 user_id → 不注入新的
→ 正则不匹配 → 不重写
→ 真实 user_id 泄露 → 封禁 ❌
```

这是三重防线同时失效的结果。每一层单独看都有合理的设计意图：
- 客户端识别层假设 UA 不会被篡改
- Metadata 注入层假设已有的 user_id 会被后续正确重写
- RewriteUserID 层的正则只适配了旧格式，没跟上新格式的演进

每一层都把希望寄托在下一层身上，结果下一层也有自己的盲区。（严格来说，即使 UA 没被改写，只要真实 CC 客户端的账户与 OAuth Token 的账户不一致，`RewriteUserID` 的正则同样无法匹配——只是这个场景在实际使用中更少见。）

## 五、修复思路

定位到根因后，修复方向就比较清晰了。核心原则：**在伪装路径下，不应该信任客户端携带的任何身份信息。**

两个方案并行推进，互不排斥。一是在 `buildOAuthMetadataUserID` 中增加 `forceMimic` 参数，当请求走伪装路径时强制生成新的 `metadata.user_id`，不再尊重客户端已有的值；二是扩展 `RewriteUserID` 的正则，让它同时匹配 `_account__session_`（旧格式，account 为空）和 `_account_{uuid}_session_`（新格式，account 非空），作为最后一道兜底。前者从根本上解决问题，后者确保即使判断逻辑出错，最后一道防线也能正确重写。

## 六、总结

回顾一下这三篇文章的脉络。第一篇发现会话数累加的根因是客户端不带 `metadata.user_id`，第二篇用 LiteLLM 代理在中间层注入了 session 标识，第三篇（本文）则揭开了一个更深层的安全问题——当 `User-Agent` 被中间网关改写时，模型调度平台的身份伪装机制会被完全穿透。

这次排查最大的启示是关于"纵深防御"的一个常见误区。我们设计了三重防线——客户端识别、metadata 注入、user_id 重写——看起来层层把关，万无一失。但实际上每一层都在假设前一层正常工作：注入层假设识别层判断正确，重写层的正则假设上游格式不变。当一个意外条件（UA 被改写）从第一层滑过去时，后面的每一层都没能独立拦住它。

真正的纵深防御，每一层都应该假设前置层可能失效。这个原则说起来简单，做起来需要刻意对抗"前面已经处理过了"的思维惯性。

从实操角度，如果你也在用类似的多租户网关架构，有两点值得注意：一是请求链路上任何中间层对 header 的改写都可能影响下游的判断逻辑，上线前最好做一次端到端的 header 审计；二是身份相关的字段（无论在 header 还是 body 里）在跨信任边界时必须重新校验，不能假设上游传来的值是安全的。

这个系列暂时告一段落。后续打算整理一份请求链路的端到端 header 审计清单，作为类似架构的排查参考——如果有新的发现，再来更新。
