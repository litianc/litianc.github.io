---
layout: post
title: 用 Hammerspoon 给豆包语音输入加一个「右 Option 守门键」
description: 继多屏鼠标焦点灯之后，我继续用 Hammerspoon 做了第二个 Spoon 小工具：DoubaoVoiceInput。它解决的是豆包语音输入里一个很小但高频的打断：当输入法不在豆包时，右 Option 不会启动语音输入。本文记录这个需求从真实使用场景到 Spoon 实现、安装和调参的过程。
date: 2026-06-07
tags: Mac Hammerspoon 自动化 Spoon 豆包输入法 语音输入 效率工具 AI
---

> 作者：litianc
>
> 时间：2026年6月7日
>
> 阅读时长：7分钟

## 前言

前两天我写了一篇关于 Hammerspoon 的小工具文章：用 `ScreenFocusDimmer` 给 Mac 多屏加一个「鼠标焦点灯」。它解决的是多屏办公时注意力容易被几块屏幕分散的问题。

那篇文章写完之后，我对 Hammerspoon 的感觉更明确了：它不是一个单点效率工具，而是一个可以继续塑形 macOS 工作流的自动化底座。很多系统里没有的小开关，只要需求足够清楚，就可以被写成一个很小的 Spoon。

这次要做的是第二个小工具，场景从“屏幕焦点”换成了“语音输入”。

我现在越来越多地使用豆包输入法的语音输入。原因不只是它识别效果不错，更重要的是它是一个独立的系统输入法。只要输入法还在 macOS 里，写文章、聊天、搜索、和 AI 对话时都可以直接调用它，不需要先打开某个特定应用。

我之前也用过微信输入法的语音输入。微信输入法在微信聊天场景里当然很顺手，但它对我来说有一个明显限制：它不是一个完全独立的语音输入入口。如果微信退出了，这个能力也就跟着不可用了。对一个想要在系统范围内随时使用语音输入的人来说，这种依赖会让工作流不够稳定。

豆包输入法更接近我想要的形态：它把语音输入放到了系统输入法层。无论我当前是在浏览器、编辑器、笔记软件，还是 AI 对话窗口里，只要能输入文字，就可以尝试用语音把想法说出来。

它还有一个很顺手的设置：可以把右 Option 设置成语音输入快捷键。这个键平时几乎不用，按一下就开始说话，很适合在写文章、和 AI 对话、记笔记时快速把想法说出来。

但使用一段时间后，我遇到一个很烦的小问题：如果当前输入法已经切到了 ABC、系统拼音或其他输入法，再按右 Option，就不会进入豆包语音输入。于是原本“按一下就说话”的动作，会突然变成“先看输入法状态，再切回豆包，再重新按一次”。

这不是一个大 bug，但它刚好卡在语音输入最要命的地方：**启动动作不能打断表达。**

所以我继续沿用上一篇的思路，用 Hammerspoon 做了一个独立的 Spoon：`DoubaoVoiceInput`。它把右 Option 变成一个「豆包语音输入守门键」：当前是豆包时直接放行；当前不是豆包时，第一次提示，第二次确认后自动切回豆包并启动语音输入。

## 一、为什么语音输入也需要一个守门键

语音输入的价值在于降低表达阻力。

键盘输入需要把想法拆成字词和按键，语音输入则更接近“边想边说”。尤其是在和 AI 工具协作时，我经常不是要写一段非常正式的文字，而是要快速描述一个需求、一个判断、一个临时想法。

这时候，输入动作越轻越好。

右 Option 作为语音输入快捷键，原本就是一个很好的选择。它位置固定，不容易和常用快捷键冲突，也不需要鼠标去点输入法菜单。

问题在于，macOS 的输入法状态不是一个稳定背景。很多应用会记住自己的输入源，或者你刚刚为了输入英文、写代码、搜索命令，手动切到了 ABC。等你下一次想用豆包语音输入时，当前输入法可能已经不是豆包。

于是右 Option 的含义就变了：

1. 当前是豆包输入法时，它是“开始语音输入”。
2. 当前不是豆包输入法时，它只是一个普通的右 Option。

这种不确定性会让语音输入变得不可靠。更麻烦的是，它不是每次都失败，而是偶尔失败。偶尔失败的快捷键，比完全不能用的快捷键更打断心流，因为你会下意识怀疑自己刚才是不是按错了、是不是豆包没响应、是不是当前应用不支持。

我想要的效果很简单：无论当前是什么输入法，右 Option 都应该先帮我判断一下，如果已经是豆包，就按豆包原来的逻辑启动语音输入；如果不是豆包，就给我一个快速切回豆包的确认动作。

这就是「守门键」这个名字的来源。它不是替代豆包输入法，也不是重新实现语音识别，而是在语音输入入口前加了一层状态判断。

## 二、本文环境

为了避免以后版本变化造成差异，先把这次使用的环境记录下来。

| 项目 | 版本或配置 |
|------|------|
| Hammerspoon | `1.1.1`，Build `6936` |
| DoubaoVoiceInput Spoon | `0.1.0` |
| 豆包输入法 source ID | `com.bytedance.inputmethod.doubaoime.pinyin` |
| 右 Option keycode | `61` |
| 双击确认时间窗 | `doublePressWindow = 1.5` 秒 |
| 切换后触发延迟 | `triggerDelay = 0.18` 秒 |

项目源码已经放在 GitHub：

[litianc/doubao-voice-input-spoon](https://github.com/litianc/doubao-voice-input-spoon)

这篇文章和上一篇「鼠标焦点灯」可以看成同一个系列：都不是要开发一个完整 App，而是用 Hammerspoon 作为 macOS 自动化底座，把一个非常具体的个人工作流问题封装成一个 Spoon。

## 三、延续上一篇：Hammerspoon 适合修这种小别扭

上一篇 `ScreenFocusDimmer` 用到的是 Hammerspoon 的屏幕、鼠标和 `hs.canvas` 能力。这一篇 `DoubaoVoiceInput` 用到的是另一组能力：键盘事件监听、输入法状态读取、输入法切换和模拟按键。

这也是 Hammerspoon 很有意思的地方。它不是只服务某一类自动化，而是把 macOS 桌面环境里的很多对象都暴露给 Lua：

1. 屏幕、鼠标、窗口。
2. 键盘、快捷键、事件监听。
3. 输入法、剪贴板、菜单栏。
4. 定时器、通知、控制台和配置重载。

Spoon 则是把某一个具体需求封装起来的插件形态。Hammerspoon 提供底层能力，Spoon 负责把这些能力组织成一个可复用的小工具。

这次的需求刚好需要几类 Hammerspoon API：

1. 用 `hs.eventtap` 监听右 Option。
2. 用 `hs.keycodes.currentSourceID()` 判断当前输入法。
3. 用 `hs.keycodes.currentSourceID(sourceID)` 切换到豆包输入法。
4. 用 `hs.eventtap.event.newKeyEvent()` 在切换后补发一次右 Option。
5. 用 `hs.alert` 给出轻量提示。

如果写成一个完整 macOS App，当然也可以做。但为了一个右 Option 的交互修正去开发 App，就有点重了。Hammerspoon 的优势正在这里：它让这种“小别扭”可以用几十行 Lua 解决，并且可以继续被安装、测试、打包和上传到 GitHub。

![Hammerspoon、DoubaoVoiceInput Spoon 和豆包输入法的关系：用户按下右 Option，Hammerspoon 监听事件，Spoon 判断输入法状态，最后交给豆包语音输入](/images/posts/doubao_voice_input/hammerspoon-doubao-architecture.png)

> 这张图也可以和上一篇「鼠标焦点灯」放在一起看：同一个 Hammerspoon 自动化底座，上一次接的是屏幕和鼠标，这一次接的是键盘事件和输入法。

## 四、交互设计：不是强制切换，而是双击确认

一开始最直接的想法是：无论当前是什么输入法，只要按右 Option，就自动切到豆包并启动语音输入。

但仔细想一下，这个设计有点太强了。

虽然我平时几乎不用右 Option 做别的事，但输入法和快捷键毕竟属于系统级交互。如果一个脚本在任何情况下都抢占右 Option，可能会制造新的误触。比如当前正在某个特殊应用里，或者只是碰到了这个键，它都立刻切输入法并触发语音输入，这反而不够优雅。

所以最后采用了一个更克制的方案：

1. **当前是豆包输入法**：右 Option 直接放行，不做任何拦截，让豆包按自己的原生逻辑启动语音输入。
2. **当前不是豆包输入法**：第一次右 Option 被 Spoon 拦截，只显示提示「再按一次右 Option 切换到豆包语音输入」。
3. **短时间内第二次右 Option**：Spoon 切换到豆包输入法，然后补发一次右 Option，启动豆包语音输入。
4. **超过时间窗**：把下一次右 Option 重新当作第一次提示。

这个设计保留了一个很轻的确认动作。它不会改变豆包输入法已经正常工作时的体验，也不会在非豆包状态下立刻强制切换，而是把“我确实要用豆包语音输入”表达成一个快速双击。

对我来说，这比完全自动更舒服。因为它不是把系统交互变得更激进，而是让不确定的地方多了一步很短的确认。

![DoubaoVoiceInput 的交互流程：当前是豆包输入法时直接放行，当前不是豆包时第一次提示，1.5 秒内第二次按下后切回豆包并补发右 Option](/images/posts/doubao_voice_input/doubao-voice-input-flow.png)

> 这里最关键的不是“自动切换”，而是“只在不确定时介入”。如果当前已经是豆包，Spoon 不做多余动作；只有当前不是豆包时，才把右 Option 变成一次确认。

## 五、从零做成一个 Spoon

这个 Spoon 的代码结构很小，我把它拆成两层：

- `core.lua`：纯 Lua 状态机，不依赖 Hammerspoon，负责判断右 Option 这次应该放行、提示还是切换并触发。
- `init.lua`：Hammerspoon 适配层，负责监听键盘事件、读取和切换输入法、发通知、模拟右 Option。

博客里不需要把所有事件处理细节都贴出来，真正值得看的只有状态机这一小段。它把右 Option 的结果分成三类：

1. 当前是豆包：放行。
2. 当前不是豆包，且第一次按：提示并拦截。
3. 当前不是豆包，且短时间内第二次按：切换并触发。

对应到代码，大致是这样：

```lua
function Core:handleRightOption(currentSourceID, now)
  if currentSourceID == self.doubaoSourceID then
    self:reset()
    return {
      action = "pass-through",
      consume = false,
    }
  end

  if self.pendingSince and (now - self.pendingSince) <= self.doublePressWindow then
    self:reset()
    return {
      action = "switch-and-trigger",
      consume = true,
      targetSourceID = self.doubaoSourceID,
    }
  end

  self.pendingSince = now
  return {
    action = "prompt",
    consume = true,
    message = "再按一次右 Option 切换到豆包语音输入",
  }
end
```

这里最重要的是 `consume`。当 `consume = false` 时，说明这次右 Option 要继续传给系统和豆包输入法；当 `consume = true` 时，说明这次按键已经被 Spoon 接管，不应该再传下去。

剩下的细节都放在 Hammerspoon 适配层里。比如右 Option 是修饰键，它的按下和松开都属于 `flagsChanged` 事件；如果 Spoon 吞掉了按下事件，也要吞掉对应的松开事件，避免系统看到一个孤立的 key up；切换到豆包后，Spoon 还会稍等 `0.18` 秒，再补发一次右 Option，避免输入法还没切换完成就触发失败。

整个实现里，我最喜欢的是 `core.lua` 和 `init.lua` 的边界。输入法判断策略放在纯 Lua 状态机里，可以直接测试；Hammerspoon API 只出现在适配层里。这样即使以后要把右 Option 换成别的键，或者把豆包换成另一个输入法，也不用重新理解所有事件细节。

## 六、安装与使用

安装方式和上一篇 Spoon 类似。先把 `DoubaoVoiceInput.spoon` 放到 Hammerspoon 的 Spoons 目录：

```bash
mkdir -p ~/.hammerspoon/Spoons
cp -R DoubaoVoiceInput.spoon ~/.hammerspoon/Spoons/
```

然后在 `~/.hammerspoon/init.lua` 中加载：

```lua
hs.loadSpoon("DoubaoVoiceInput")
spoon.DoubaoVoiceInput.doubaoSourceID = "com.bytedance.inputmethod.doubaoime.pinyin"
spoon.DoubaoVoiceInput.doublePressWindow = 1.5
spoon.DoubaoVoiceInput.triggerDelay = 0.18
spoon.DoubaoVoiceInput:start()
```

如果你的配置文件里已经有上一篇的 `ScreenFocusDimmer`，也不需要做额外整合。两个 Spoon 都运行在 Hammerspoon 里，但互不依赖：一个处理多屏视觉焦点，一个处理豆包语音输入入口。

保存配置后，重载 Hammerspoon：

```bash
hs -c 'hs.reload()'
```

如果你不确定豆包输入法的 source ID，可以用下面的命令查看当前系统里的输入法：

```bash
hs -c 'return hs.inspect(hs.keycodes.methods(true))'
```

我本机看到的豆包输入法 ID 是：

```text
com.bytedance.inputmethod.doubaoime.pinyin
```

如果你的输出不同，把 `spoon.DoubaoVoiceInput.doubaoSourceID` 改成实际值即可。

## 七、最终效果和几个可调参数

最终效果并不复杂：

1. 在豆包输入法下，按右 Option，语音输入正常启动。
2. 在 ABC 或其他输入法下，第一次按右 Option，只出现提示，不会误触发其他动作。
3. 看到提示后，再按一次右 Option，系统会切回豆包，并进入语音输入。

真正影响手感的是几个小参数：

| 参数 | 当前值 | 作用 |
|------|------|------|
| `doublePressWindow` | `1.5` | 第一次提示后，第二次确认在多少秒内有效。想更干脆可以调成 `1.0`。 |
| `triggerDelay` | `0.18` | 切换到豆包后，等待多久再补发右 Option。偶尔触发失败时，可以调到 `0.25` 或 `0.3`。 |
| `showAlerts` | `true` | 是否显示 Hammerspoon 提示。刚开始建议保留，形成肌肉记忆后可以关掉。 |

## 八、把输入法也纳入个人操作系统

这次的小工具比上一篇 `ScreenFocusDimmer` 还要小。

它不改变屏幕，不整理窗口，也不生成任何界面。它只是在右 Option 和豆包输入法之间加了一层判断。但我觉得它很能代表 Hammerspoon 这类工具的价值：**不是替代某个 App，而是修补 App 与系统之间那些不够贴合个人习惯的地方。**

操作系统提供的是通用能力，输入法提供的是语音识别能力，但真实工作流发生在它们之间。你希望某个键永远可靠地进入语音输入，希望输入法状态不要打断表达，希望一个高频动作不用被菜单栏图标牵着走。这些都不是标准产品需求里的大功能，却会真实影响每天使用电脑的手感。

过去这类需求往往只能忍着。因为它太小，不值得开发一个 App；又太个人化，不太可能等到系统更新。

现在情况变了。Hammerspoon 提供 macOS 自动化底座，AI 编程助手可以把自然语言需求翻译成脚本、测试和 Spoon 结构。我们需要表达的不是“调用哪个 API”，而是：

> 我希望右 Option 永远像豆包语音输入的入口。如果当前不是豆包，就提醒我再按一次并自动切过去。

剩下的事情，可以一步步变成代码：读取输入法、监听右 Option、处理双击时间窗、切换输入源、模拟按键、写测试、打包、上传 GitHub。

这也是我越来越喜欢这类小工具的原因。它们单独看都不大，却会一点点把电脑从“通用设备”改造成“贴合自己工作方式的环境”。

上一篇鼠标焦点灯解决的是多屏注意力，这一篇右 Option 守门键解决的是语音输入启动。它们都很小，但方向是一致的：把那些每天重复遇到的小摩擦，变成可编程、可复用、可继续迭代的个人自动化。

## 总结

`DoubaoVoiceInput` 是一个很小的 Hammerspoon Spoon。它解决的不是语音识别本身，而是语音输入入口的可靠性问题。

当豆包输入法已经是当前输入法时，它不打扰原有流程；当当前不是豆包时，它用一次提示和一次确认，把右 Option 重新变成豆包语音输入入口。

对我来说，这正是 Hammerspoon 和 Spoon 最适合做的事情：不做大而全的软件，只给具体工作流补上一块刚好缺失的拼图。

项目源码在这里：

[litianc/doubao-voice-input-spoon](https://github.com/litianc/doubao-voice-input-spoon)
