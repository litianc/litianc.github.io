---
layout: post
title: 用 Hammerspoon 给豆包语音输入加一个「右 Option 守门键」
description: 这是继「鼠标焦点灯」之后的第二个 Hammerspoon Spoon 小工具。它解决一个很小但很高频的问题：当前输入法不是豆包时，右 Option 不会启动豆包语音输入。
date: 2026-06-07
tags: Mac Hammerspoon 自动化 Spoon 豆包输入法 语音输入 效率工具 AI
---

> 作者：litianc
>
> 时间：2026年6月7日
>
> 阅读时长：4分钟

## 先说结论

这是一个很小的 Hammerspoon Spoon：`DoubaoVoiceInput`。

它只做一件事：

> 不管当前是什么输入法，按右 Option 时，都先判断一下能不能顺利进入豆包语音输入。

如果当前已经是豆包输入法，右 Option 直接放行，让豆包按原来的方式启动语音输入。

如果当前不是豆包输入法，第一次按右 Option 只提示；短时间内再按一次，它就自动切回豆包，并补发右 Option，启动语音输入。

![DoubaoVoiceInput 的实际提示效果：第一次提示再按一次右 Option，第二次切换到豆包并启动语音输入](/images/posts/doubao_voice_input/doubao-voice-input-screenshot.png)

项目源码在这里：

[litianc/doubao-voice-input-spoon](https://github.com/litianc/doubao-voice-input-spoon)

## 为什么要做它

我现在经常用豆包输入法的语音输入。

我喜欢它的原因很简单：它是一个独立的系统输入法。只要它还在 macOS 里，写文章、聊天、搜索、和 AI 对话时都可以直接用，不依赖某个 App 是否打开。

我之前也用过微信输入法的语音输入。它在微信里很顺手，但如果微信退出了，语音输入能力也跟着不可用了。对我这种想在系统里随时开口输入的人来说，这个依赖有点别扭。

豆包输入法有一个很好用的设置：把右 Option 设成语音输入快捷键。

右 Option 这个键平时几乎不用，拿来做语音输入入口很合适。但问题也在这里：如果我刚刚切到了 ABC、系统拼音或其他输入法，再按右 Option，就不会进入豆包语音输入。

原本应该是：

> 按一下，说话。

实际经常变成：

> 看一眼输入法，切回豆包，再按一次。

这一步很小，但它会打断表达。尤其是和 AI 对话、写草稿、记录灵感的时候，启动动作最好不要让人分心。

## 它怎么工作

我最后没有做成“按右 Option 就强制切豆包”。

那样太激进了。输入法和快捷键属于系统级交互，如果每次误触都直接切输入法并启动语音，反而会制造新的打扰。

所以这个 Spoon 用了一个更轻的双击确认：

1. 当前是豆包输入法：右 Option 直接放行。
2. 当前不是豆包输入法：第一次按右 Option，只提示“再按一次右 Option 切换到豆包语音输入”。
3. 在 `1.5` 秒内再按一次：切到豆包，并补发一次右 Option。
4. 超过时间窗：下一次重新当作第一次提示。

![DoubaoVoiceInput 的交互流程：当前是豆包输入法时直接放行，当前不是豆包时第一次提示，1.5 秒内第二次按下后切回豆包并补发右 Option](/images/posts/doubao_voice_input/doubao-voice-input-flow.png)

这里最重要的不是自动化本身，而是边界感：

> 已经正常时不打扰；不确定时才介入。

## 安装和配置

这次环境记录如下：

- Hammerspoon：`1.1.1`，Build `6936`
- DoubaoVoiceInput Spoon：`0.1.0`
- 豆包输入法 source ID：`com.bytedance.inputmethod.doubaoime.pinyin`
- 右 Option keycode：`61`

把 `DoubaoVoiceInput.spoon` 放到 Hammerspoon 的 Spoons 目录后，在 `~/.hammerspoon/init.lua` 里加载：

```lua
hs.loadSpoon("DoubaoVoiceInput")
spoon.DoubaoVoiceInput.doubaoSourceID = "com.bytedance.inputmethod.doubaoime.pinyin"
spoon.DoubaoVoiceInput.doublePressWindow = 1.5
spoon.DoubaoVoiceInput.triggerDelay = 0.18
spoon.DoubaoVoiceInput:start()
```

然后重载 Hammerspoon：

```bash
hs -c 'hs.reload()'
```

如果你的豆包输入法 ID 不一样，可以先切到豆包输入法，再用下面的命令查看：

```bash
hs -c 'return hs.keycodes.currentSourceID()'
```

常用参数只有三个：

- `doublePressWindow = 1.5`：第二次确认的有效时间。想更干脆可以调成 `1.0`。
- `triggerDelay = 0.18`：切到豆包后，等待多久再补发右 Option。偶尔触发失败时，可以调到 `0.25` 或 `0.3`。
- `showAlerts = true`：是否显示 Hammerspoon 提示。刚开始建议保留，形成肌肉记忆后可以关掉。

## 和上一篇的关系

上一篇我写的是 `ScreenFocusDimmer`：用 Hammerspoon 给 Mac 多屏加一个「鼠标焦点灯」。

这一篇是第二个小工具：`DoubaoVoiceInput`，给豆包语音输入加一个「右 Option 守门键」。

它们都不是大软件，也不是完整 App。它们更像是把每天反复遇到的小摩擦，变成一个可以复用的小开关。

对我来说，Hammerspoon 最有意思的地方就在这里：它把 macOS 里的屏幕、鼠标、键盘、输入法、窗口这些对象暴露给 Lua。再加上 AI 编程助手，我们不一定要先成为 macOS 开发者，才有资格改造自己的工作流。

以前遇到这种小问题，通常只能忍着。

现在可以直接说：

> 我希望右 Option 永远像豆包语音输入的入口。如果当前不是豆包，就提醒我再按一次并自动切过去。

然后一步步把它变成脚本、测试、Spoon 和 GitHub 项目。

这篇文章不想把代码展开太长，因为功能本身很小。真正重要的是这个思路：

> 让电脑迁就人的习惯，而不是让人一直记住电脑当前处在什么状态。
