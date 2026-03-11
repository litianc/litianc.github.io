---
layout: post
title: 想靠 Gemini 缓存省钱？先别走 API 中转——三组测试的教训
description: 为了给 ClawParty 项目降本，我们测试了 Gemini 3 Flash 的隐式缓存能否在 NewAPI 代理中转场景下生效。三组测试结果一致：缓存未命中。本文记录完整测试过程、额外踩坑，以及最终的原因分析和替代方案。
date: 2026-03-10
tags: AI Gemini API 技术笔记
---

> 作者：litianc
>
> 时间：2026年3月10日
>
> 阅读时长：8分钟

## 前言

ClawParty 是我们内部的一个多模型对话平台，底层基于 OpenClaw 构建，目前主力模型是 Claude Haiku 4.5。最近在做成本审计时，我们把目光投向了 Gemini 3 Flash。

选择 Gemini 3 Flash 不只是因为便宜。从 [PinchBench](https://pinchbench.com/) 等 benchmark 来看，Claude Haiku 4.5 的成功率为 67.0%，而 Gemini Flash 系列也在快速追赶——加上 Gemini 3 Flash 在推理和多模态任务上表现强劲、吞吐量超 200 tokens/s，作为 OpenClaw 平台上的备选模型完全够格。更关键的是价格：Gemini 3 Flash 的定价比 Haiku 便宜 50-60%（截至 2026 年 3 月，Gemini 3 Flash 输入 $0.50/M vs Haiku $1.00/M，输出 $3.00/M vs $5.00/M），如果再加上 Gemini 的隐式缓存（Implicit Caching），input token 可以再打一折——算下来成本能压到原来的 5-6%，非常诱人。

但我们的架构里有一层 NewAPI 中转代理，所有模型请求都经过这层代理做统一管理和计费。问题来了：隐式缓存在中转场景下还能生效吗？

为了验证这个问题，我花了一个下午跑了三组测试。结论先放在这里：**不行，通过 NewAPI 代理无法触发 Gemini 隐式缓存**。下面是完整的排查过程。

## 一、Gemini 隐式缓存机制简介

Google Gemini API 提供自动的隐式缓存机制，核心规则很简单：

- 多个请求如果共享相同的前缀内容（比如 system prompt），Gemini 后端会自动缓存这些公共前缀
- 缓存命中后，input token 费用享受 **90% 折扣**（只收 10%）
- 最低门槛：Flash 系列需要 1024 tokens（包括 Gemini 3 Flash），Pro 需要 2048 tokens
- 触发条件：**相同 API key + 相同前缀内容（逐字节匹配）**

不需要额外的 API 调用，纯自动生效——前提是满足上面的条件。

## 二、测试环境

| 项目 | 值 |
|------|------|
| 代理类型 | NewAPI（支持 OpenAI 兼容 + Gemini 原生协议转发） |
| 测试模型 | `gemini-3-flash-preview` |
| System Prompt | 约 1149 tokens 的专业知识 prompt |
| 测试方式 | 固定 system prompt，变换 user query，观察 cached_tokens 是否 > 0 |

测试思路很直接：用同一个 system prompt 发多轮请求，如果缓存生效，从第二轮开始应该能在响应的 usage 字段中看到 `cached_tokens`（OpenAI 兼容格式）或 `cachedContentTokenCount`（Gemini 原生格式）大于 0。

## 三、测试一：OpenAI 兼容格式

先走最常用的 `/v1/chat/completions` 端点，这也是 ClawParty 目前在用的格式。

请求结构：

```json
{
  "model": "gemini-3-flash-preview",
  "messages": [
    {"role": "system", "content": "<~1149 tokens system prompt>"},
    {"role": "user", "content": "What is Redis?"}
  ],
  "max_tokens": 30
}
```

5 轮请求，每轮间隔 3 秒，结果如下：

| 轮次 | 用户问题 | prompt_tokens | cached_tokens |
|------|----------|:---:|:---:|
| 1 | What is Redis? | 1149 | 0 |
| 2 | What is Kafka? | 1148 | 0 |
| 3 | Explain Kubernetes. | 1148 | 0 |
| 4 | Redis follow-up (多轮) | 1167 | 0 |
| 5 | What is Docker? | 1148 | 0 |

返回的 usage 结构长这样：

```json
{
  "prompt_tokens": 1149,
  "completion_tokens": 26,
  "total_tokens": 1175,
  "prompt_tokens_details": {
    "cached_tokens": 0,
    "text_tokens": 1149
  }
}
```

五轮全部 `cached_tokens: 0`，NewAPI 仪表盘也没有显示缓存命中。第一个格式宣告失败。

## 四、测试二：Gemini 原生协议（小 prompt）

OpenAI 兼容格式走的是 NewAPI 的格式转换层，可能是转换过程中破坏了缓存条件。于是我切到 Gemini 原生的 `generateContent` 端点试试：

```json
{
  "contents": [
    {"role": "user", "parts": [{"text": "What is Redis?"}]}
  ],
  "systemInstruction": {
    "parts": [{"text": "<~1149 tokens system prompt>"}]
  },
  "generationConfig": {
    "maxOutputTokens": 30,
    "thinkingConfig": {"thinkingBudget": 0}
  }
}
```

同样 5 轮，结果依然一样：

| 轮次 | 用户问题 | promptTokenCount | cachedContentTokenCount |
|------|----------|:---:|:---:|
| 1 | What is Redis? | 1149 | N/A |
| 2 | What is Kafka? | 1148 | N/A |
| 3 | Explain Kubernetes. | 1147 | N/A |
| 4 | What is Docker? | 1149 | N/A |
| 5 | Explain microservices. | 1149 | N/A |

注意返回的 `trafficType` 是 `ON_DEMAND`，即全价计费，没有任何缓存命中的迹象。响应中连 `cachedContentTokenCount` 字段都不存在——说明 Gemini 后端压根没有尝试匹配缓存。

## 五、测试三：Gemini 原生协议（大 prompt）

1149 tokens 刚过 1024 的门槛，可能比较边缘。为了排除这个变量，我把 system prompt 扩大到约 1967 tokens（远超门槛），并增加到 7 轮、间隔 6 秒：

| 轮次 | 用户问题 | promptTokenCount | cachedContentTokenCount |
|------|----------|:---:|:---:|
| 1 | What is Redis? | 1967 | N/A |
| 2 | What is Kafka? | 1967 | N/A |
| 3 | Explain Kubernetes. | 1966 | N/A |
| 4 | What is Docker? | 1967 | N/A |
| 5 | Explain microservices. | 1967 | N/A |
| 6 | What is gRPC? | 1967 | N/A |
| 7 | Compare SQL vs NoSQL. | 1968 | N/A |

7 轮，接近 2000 tokens 的前缀，依然没有触发缓存。到这里基本可以确认：**问题不在 prompt 大小，而在中转代理本身**。

## 六、额外发现

三组缓存测试做完了，结论已经很清楚。不过测试过程中还踩了两个坑，和 Gemini API 的使用直接相关，顺便记录一下。

### 流式协议兼容性问题

通过 NewAPI 使用 Gemini 原生流式协议（`streamGenerateContent`）时，下游的 `@google/genai` SDK 会报错：

```
Incomplete JSON segment at the end
```

原因是 NewAPI 返回的流式响应以 `}` 结尾，缺少 SDK 期望的终止标记。这是一个[已知问题](https://github.com/google-gemini/gemini-cli/issues/9060)。解决方案是切回 OpenAI 兼容格式（`/v1/chat/completions`），NewAPI 对这个格式的流式支持没有问题。

### Thinking 模型的测试陷阱

`gemini-3-flash-preview` 是 thinking 模型。测试连通性时如果设 `maxOutputTokens: 1`，思考过程会吃掉全部 token 预算，导致实际输出为空（`parts: null`），看起来像是请求失败了。

正确的做法是加上 `thinkingConfig: {"thinkingBudget": 0}` 禁用思考，同时给 `maxOutputTokens` 留够空间（比如 10 以上）。

## 七、原因分析

回到最核心的问题：为什么缓存不生效？

Gemini 隐式缓存要求 **相同 API key + 相同前缀（逐字节匹配）**。而最可能的原因其实很简单——NewAPI 的核心设计理念就是多 key 轮转和负载均衡，这恰好和隐式缓存的前提条件冲突。具体来说，至少有三个环节可能破坏缓存条件：

1. **API Key 轮转** — NewAPI 后端配置了多个 Google API key 做负载均衡，不同请求落到不同 key 上，缓存自然无法跨 key 命中。这是最主要的原因。
2. **请求内容被修改** — NewAPI 转发时可能对 payload 做了微调（增删字段、调整顺序），哪怕一个字节的差异就会导致前缀不匹配。
3. **响应元数据丢失** — 退一步讲，即使后端确实触发了缓存，NewAPI 在转换响应格式时也可能丢弃了 `cachedContentTokenCount` 字段，导致我们看不到。

## 八、结论与建议

三组测试结果一致：**通过 NewAPI 中转代理无法触发 Gemini 隐式缓存**。

如果你也在用类似的中转架构，并且希望享受 Gemini 的缓存折扣，有以下几个替代方案：

| 方案 | 优点 | 缺点 |
|------|------|------|
| **直连 Google API** | 隐式缓存自动生效，90% 折扣 | 需要 `AIza...` 格式的 key，可能需要科学上网 |
| **显式缓存 API** | 可控 TTL，更可靠 | 需要直连，额外的 API 调用 |
| **联系 NewAPI 服务商** | 可能有配置选项透传缓存 | 取决于服务商是否支持 |
| **接受无缓存成本** | 零改动 | 大量对话时成本偏高 |

我们最终选择了**直连 Google API**。在 ClawParty 中把 Gemini 配置为独立的 provider，填入 Google 原生 API key，绕过 NewAPI 中转。根据 Google 官方文档，直连模式下隐式缓存应当自动生效——后续我们会验证并更新结果。

一句话总结：**Gemini 隐式缓存和 API 中转代理天然不兼容，想省钱就直连**。
