---
layout: post
title: 用 LiteLLM 代理为 OpenClaw 注入 Session 标识：踩坑实录
description: 上一篇定位到 OpenClaw 的会话数累加问题源于缺少 metadata.user_id。本文记录如何用 LiteLLM Proxy + 自定义插件在中间层自动注入 session 标识，以及调试过程中最值得分享的 3 个坑。
date: 2026-03-03
tags: LiteLLM Python 代理 技术笔记
---

> 作者：litianc
>
> 时间：2026年3月3日
>
> 阅读时长：7分钟

## 前言

定位到 bug 的根因往往只是排查的一半，另一半是把修复方案落地——尤其当你不想（或不能）改客户端源码的时候。[上一篇文章]({% post_url 2026-03-02-OpenClaw_Concurrency_Control %})里，我定位到 OpenClaw 会话数不断累加的根因：它发出的请求不携带 `metadata.user_id`，导致上游网关每次都把请求当作新会话注册。

直接改 OpenClaw 源码侵入性太大，更优雅的做法是在中间插一层代理，透明地往请求里注入 session 信息——OpenClaw 不用改一行代码，只需要把 API 地址指向代理就行。这就是本文要讲的事：用 LiteLLM Proxy + 自定义插件，自动为每个请求注入符合上游格式要求的 `metadata.user_id`。

话不多说，直接开始。

## 一、为什么选 LiteLLM

中间代理的选型其实没纠结太久。我的核心需求就三个：能代理 Anthropic 原生 API（`/v1/messages`）、能在请求发往上游前拦截修改、部署简单。

LiteLLM 刚好全中：

1. **协议兼容**：同时支持 OpenAI 和 Anthropic 两种 API 格式的代理转发，OpenClaw 用的是 Anthropic 原生格式，不用改客户端。
2. **多模型路由**：一个代理实例统一管理 `claude-opus-4-6`、`claude-sonnet-4-6`、`claude-haiku-4-5-20251001` 三个模型，配置文件里写好路由规则即可。
3. **插件机制**：提供 `CustomLogger` 基类，支持 `async_pre_call_hook`——简单说就是一个钩子函数，在每个请求转发给上游之前会被调用，你可以在里面修改请求内容。正好满足注入需求。
4. **Docker 部署**：官方提供容器镜像，挂载一个 `config.yaml` 就能跑起来。

## 二、插件设计思路

我写的这个插件核心逻辑很简单：根据下游客户端的 API Key 生成一个确定性的 session 标识，注入到请求的 `metadata.user_id` 中。

为什么用 API Key 作为种子？因为同一个 OpenClaw 实例用的 Key 是固定的，这样同一个实例的所有请求都会得到相同的 session UUID，上游网关据此绑定为同一个会话，不再累加。

具体实现上，用 `uuid5` 基于 Key 的 hash 值生成确定性 UUID。uuid5 的特点是同样的输入永远生成同样的输出（不像 uuid4 每次随机），所以同一个 Key 永远对应同一个 session UUID。再拼上上游要求的前缀格式：

```
user_0000000000000000000000000000000000000000000000000000000000000000_account__session_<uuid>
```

上游网关会用正则匹配 `session_<uuid>` 部分来做会话绑定。插件只在请求体中没有 `user` 或 `metadata.user_id` 的时候才注入，已有的不覆盖——避免影响 Claude Code 等本身就带 session 标识的客户端。

最终的插件代码不到 30 行：

```python
from litellm.integrations.custom_logger import CustomLogger
import uuid

USER_ID_PREFIX = "user_" + "0" * 64 + "_account__session_"

class OpenclawSessionInjector(CustomLogger):
    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        has_user = data.get("user")
        has_metadata_user_id = (
            isinstance(data.get("metadata"), dict)
            and data["metadata"].get("user_id")
        )
        if has_user or has_metadata_user_id:
            return data

        api_key_hash = "default_openclaw"
        if user_api_key_dict:
            token = getattr(user_api_key_dict, "token", None) or getattr(user_api_key_dict, "api_key", None)
            if token:
                api_key_hash = str(token)

        session_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, api_key_hash))
        injected_user_id = f"{USER_ID_PREFIX}{session_uuid}"

        data["user"] = injected_user_id
        if not isinstance(data.get("metadata"), dict):
            data["metadata"] = {}
        data["metadata"]["user_id"] = injected_user_id
        return data

proxy_handler_instance = OpenclawSessionInjector()
```

看着挺简洁对吧？实际调通这 30 行代码，我花了大半天。完整的代码和配置文件我已经放到 GitHub 上了：[litianc/litellm-session-injector](https://github.com/litianc/litellm-session-injector)，有需要的可以直接拿去用。

下面挑三个印象最深的坑聊聊，都是那种"不踩一脚根本想不到"的问题。

## 三、踩坑实录

### 坑 1：插件死活加载不上

插件文件写好了，放进容器里也能正常 import，重启 LiteLLM 后满怀期待地发了个请求——插件压根没被调用。

折腾了快一小时，最后发现是配置文件里的键名写错了。我用的是 `custom_callbacks`，看起来挺合理的名字对吧？但 LiteLLM 认的是 `litellm_settings` 下的 `callbacks`——少了个 `custom_` 前缀反而是对的。文档里没有明确说明这一点，最后是去翻了 `proxy_server.py` 的源码才确认。

```yaml
# 错的（看着像对的）
litellm_settings:
  custom_callbacks:
    - openclaw_plugin.proxy_handler_instance

# 对的（看着像错的）
litellm_settings:
  callbacks:
    - openclaw_plugin.proxy_handler_instance
```

顺带分享一个调试技巧：启动 LiteLLM 时加上 `--detailed_debug` 参数，日志里会明确打印已加载的插件列表，还会输出每个请求发往上游的完整 curl 命令，排查问题时非常好用。

---

### 坑 2：同一个插件，OpenAI 格式能用，Anthropic 格式不行

这是最隐蔽的一个坑。我先用 OpenAI 格式的接口（`/v1/chat/completions`）测试，一切正常。然后满心欢喜地切到 Anthropic 格式（`/v1/messages`），结果上游死活收不到我注入的 session 标识。

同一个插件，同样的注入逻辑，为什么换个 API 格式就不行了？

排查后发现，LiteLLM 内部对这两种格式走的是完全不同的处理链。OpenAI 格式那条路径会自动把请求体里的 `user` 字段转成 Anthropic 需要的 `metadata.user_id`；但 Anthropic 原生格式那条路径不做这个转换，`user` 字段会被直接忽略掉。

而 OpenClaw 用的恰恰是 Anthropic 原生格式。所以光设置 `data["user"]` 不够，必须同时手动设置 `data["metadata"]["user_id"]`，把两条路径都覆盖住：

```python
data["user"] = injected_user_id               # OpenAI 格式走这个
data["metadata"]["user_id"] = injected_user_id # Anthropic 格式走这个
```

这种"测试通过了但换个入口就挂"的问题特别容易漏掉，建议用哪个格式就用哪个格式测，别图省事。

---

### 坑 3：改了配置但 OpenClaw 不走代理

代理搭好了，插件也调通了，最后一步就是把 OpenClaw 的 API 地址指向代理。我改了全局配置文件 `~/.openclaw/openclaw.json` 里的 `baseUrl` 和 `apiKey`，重启——请求还是直连上游，完全没走代理。

原来 OpenClaw 在运行时会在 `agents/main/agent/` 目录下自动生成一套配置文件（`models.json`、`auth-profiles.json`），这套配置的优先级比全局配置更高。你以为改了全局配置就万事大吉，实际上 agent 级别的配置把你的修改覆盖了。

必须把以下三个地方都改掉才行：

- `~/.openclaw/openclaw.json` — 全局配置
- `~/.openclaw/agents/main/agent/models.json` — agent 级 LLM 配置
- `~/.openclaw/agents/main/agent/auth-profiles.json` — agent 级认证配置

如果跑了多个 Bot 实例（比如 Bot2 在 `~/.openclaw-bot2/`），每个实例都要改一遍。

## 四、最终架构

调通之后的请求链路如下：

```
OpenClaw Bot1/Bot2
│
│ Anthropic Messages API (/v1/messages)
│ x-api-key: sk-litellm-local
▼
LiteLLM Proxy (localhost:4000)
│
│ [OpenclawSessionInjector 插件]
│ 注入 metadata.user_id = "user_000...000_account__session_<uuid>"
│
│ Anthropic Messages API (/v1/messages)
│ x-api-key: sk-d4f3...ad82
▼
上游 API 网关
│
│ 正则匹配 session_<uuid>，绑定 session/account
▼
Anthropic Claude API
```

整个方案对 OpenClaw 完全透明：只需要修改配置文件里的 API 地址和 Key，不用动一行业务代码。LiteLLM 本身的多模型路由能力也顺手用上了——三个 Claude 模型的请求统一走一个代理入口，管理起来更方便。

## 五、验证效果

改完之后做了一轮简单验证：用 OpenClaw 连续发送 20 次请求，管理页面始终显示 1 个会话——之前同样的操作会累加到 20。同时让 Claude Code 和 OpenClaw 并行访问同一个账号，页面显示 2 个会话（各一个），符合预期。停止请求后等 5 分钟，会话数自动回落到 0，TTL 机制正常工作。

问题解决。

## 六、总结

回顾一下这次的工作。上一篇定位了问题根因——OpenClaw 不带 `metadata.user_id` 导致会话数累加；本文落地了修复方案——用 LiteLLM Proxy 插件在中间层自动注入 session 标识。

上面挑了三个印象最深的坑来讲：配置键名是"文档没写清楚"的典型，协议差异是"换个入口就挂"的隐蔽问题，agent 级配置覆盖则是"最后一公里"的部署陷阱。实际调试过程中遇到的问题远不止这些（比如参数结构、类型检查、格式匹配等），完整的踩坑记录可以参考 [GitHub 仓库](https://github.com/litianc/litellm-session-injector)里的文档。

后续打算把这套代理的监控完善一下，加上请求量统计和异常告警，方便日常运维。

> **适用范围提醒**：本文所解决的问题有特定的使用场景——通过共享网关转发请求、且上游依赖 `metadata.user_id` 做 session 绑定的情况。如果你是直接使用 Anthropic API 按量付费的用户，请求天然携带独立的 API Key 作为身份标识，不需要额外注入 session 信息。

如果你也在用类似的多租户网关架构，希望这篇踩坑记录能帮你少走一些弯路。
