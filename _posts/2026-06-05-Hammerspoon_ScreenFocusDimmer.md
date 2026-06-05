---
layout: post
title: 用 Hammerspoon 给 Mac 多屏加一个焦点灯
description: 多屏办公时，鼠标在几个屏幕之间来回切换，注意力却不一定能立刻跟上。本文记录一次从真实使用痛点出发的小工具开发过程：使用 Hammerspoon 作为 macOS 自动化底座，开发 ScreenFocusDimmer Spoon，让当前鼠标所在屏幕保持明亮，其他屏幕自动变暗。
date: 2026-06-05
tags: Mac Hammerspoon 自动化 Spoon 效率工具 AI
---

> 作者：litianc
>
> 时间：2026年6月5日
>
> 阅读时长：8分钟

## 前言

最近我在 Mac 上接了多块屏幕之后，遇到一个很小但很真实的问题：屏幕变多了，信息展示空间确实更大了，但注意力也更容易被分散。

尤其是在写代码、查资料、和 AI 对话同时进行的时候，几个屏幕上都会有窗口。鼠标从主屏移到副屏，视觉焦点却经常慢半拍。晚上工作时这个感觉更明显，所有屏幕都亮着，窗口又多，眼睛需要不断重新确认“我现在到底在看哪块屏幕”。

我想要的效果其实很简单：鼠标在哪块屏幕，哪块屏幕就保持明亮；其他屏幕稍微暗下来。它不需要真的改变显示器硬件亮度，只需要像舞台追光一样，帮我把当前注意力所在的位置标出来。

一开始这看起来像是一个系统设置里的小开关，但 macOS 并没有提供这样的功能。于是我开始寻找可以自己动手实现的方案，最后选中了 Hammerspoon，并把这个功能做成了一个 Spoon 插件：`ScreenFocusDimmer`。

![ScreenFocusDimmer 演示：黄色方框标出当前焦点屏幕，鼠标跨屏后焦点随之切换](/images/posts/screen_focus_dimmer/screen-focus-dimmer-demo.gif)

> 演示动图中用黄色方框和文字标出了切换前后的焦点屏幕。鼠标从一个屏幕移动到另一个屏幕后，当前屏幕保持明亮，其他屏幕自动变暗。

## 一、为什么会需要一个焦点灯

多屏办公带来的提升非常直接：一个屏幕写代码，一个屏幕看文档，一个屏幕放聊天或者监控面板。信息不用频繁切换窗口，桌面空间一下子宽敞了很多。

但它的副作用也很明显。屏幕越多，视觉噪音越多。很多时候，我们不是找不到窗口，而是所有窗口都在同时向你招手。

这个问题在几类场景中特别明显：

1. 写代码时，主屏是编辑器，副屏是浏览器和终端。
2. 做研究时，一个屏幕看资料，另一个屏幕整理笔记。
3. 和 AI 协作时，一边运行命令，一边看对话，一边查文档。
4. 夜间工作时，多块屏幕同时发光，眼睛更容易疲劳。

所以这里真正想解决的不是“亮度控制”，而是“注意力提示”。当前屏幕不一定要变得更亮，只要其他屏幕稍微暗一点，人的眼睛就会自然回到当前操作区域。

这也是后来实现时的一个重要判断：我没有去调用显示器硬件亮度接口，而是使用一层半透明黑色遮罩盖在非当前屏幕上。这样既简单，也更稳定，因为外接显示器的亮度控制在 macOS 上并不总是可靠。

## 二、本文环境

为了避免以后软件升级后出现差异，先把本文使用的版本记录下来。

| 项目 | 版本 |
|------|------|
| Hammerspoon | `1.1.1`，Build `6936` |
| ScreenFocusDimmer Spoon | `0.1.0` |
| 遮罩透明度 | `dimAlpha = 0.55` |
| 检测间隔 | `checkInterval = 0.25` 秒 |

项目源码已经放在 GitHub：

- 源码地址：[litianc/screen-focus-dimmer-spoon](https://github.com/litianc/screen-focus-dimmer-spoon)
- Release 下载：[v0.1.0](https://github.com/litianc/screen-focus-dimmer-spoon/releases/tag/v0.1.0)

## 三、为什么是 Hammerspoon

Hammerspoon 是一个 macOS 自动化工具。它本身不像 Alfred、Raycast 那样提供一组现成的效率功能，而是把 macOS 的很多底层能力暴露给 Lua 脚本。

比如它可以读取鼠标位置、监听屏幕变化、管理窗口、绑定快捷键、控制菜单栏、处理剪贴板，甚至创建覆盖在屏幕上的图形元素。换句话说，它不是一个单点工具，而是一个桌面自动化运行时。

![Hammerspoon 自动化链路：macOS 能力经过 Hammerspoon、init.lua 配置和 Spoon 插件，最终生成屏幕焦点效果](/images/posts/screen_focus_dimmer/hammerspoon-automation-stack.png)

> Hammerspoon 更像一个自动化底座。它把 macOS 的屏幕、鼠标、窗口层级等能力暴露给 Lua 脚本，Spoon 再把具体需求封装成可复用的小工具。

这个功能之所以适合用 Hammerspoon 来做，是因为它刚好需要几类能力：

1. 获取当前有哪些屏幕。
2. 判断鼠标当前位于哪块屏幕。
3. 在指定屏幕上绘制一层半透明遮罩。
4. 当屏幕数量变化时自动启停。
5. 用快捷键随时打开或关闭。

如果写成一个完整的 macOS App，当然也可以实现，但成本明显更高。对于这种高度个人化、功能边界很清晰的小工具，Hammerspoon 反而是更合适的选择。

## 四、安装 Hammerspoon

Hammerspoon 的安装方式很简单。可以从官网下载安装包，也可以通过 Homebrew 安装。

```bash
brew install --cask hammerspoon
```

安装完成后，第一次打开 Hammerspoon，需要在 macOS 的“系统设置”里授予辅助功能权限。这个权限很重要，因为 Hammerspoon 需要读取鼠标、窗口和屏幕相关信息，也需要在桌面上创建覆盖层。

为了方便后续从终端重载配置，还可以安装 Hammerspoon 的命令行工具 `hs`。在 Hammerspoon 控制台或配置文件中执行：

```lua
hs.ipc.cliInstall()
```

之后就可以在终端中使用：

```bash
hs -c 'hs.reload()'
```

Hammerspoon 的入口配置文件是：

```text
~/.hammerspoon/init.lua
```

它有点像桌面自动化世界里的 `.vimrc` 或 `.zshrc`。所有脚本、快捷键、Spoon 插件都可以从这里加载。

我这次没有设置 Hammerspoon 开机自启动。原因也很简单：这是一个个人体验增强工具，不是系统必须组件。如果没有启动，可以在应用程序里手动打开 Hammerspoon，或者在终端中执行：

```bash
open -a Hammerspoon
```

## 五、从零开发 ScreenFocusDimmer Spoon

Hammerspoon 里有一个插件形态叫 Spoon。简单理解，Spoon 就是可以被 Hammerspoon 加载的 Lua 插件包，一般放在：

```text
~/.hammerspoon/Spoons/
```

我们的插件目录叫：

```text
ScreenFocusDimmer.spoon
```

它不是一个独立 App，而是运行在 Hammerspoon 里的一个功能模块。Hammerspoon 提供 macOS 自动化能力，Spoon 负责把具体需求封装成可复用的小工具。

这个插件的目标很明确：

1. 如果只有一个屏幕，不做任何检测，也不显示遮罩。
2. 如果有两个或更多屏幕，开始低频检测鼠标所在屏幕。
3. 鼠标停留在同一块屏幕时，不重复更新遮罩。
4. 鼠标移动到另一块屏幕时，隐藏当前屏幕遮罩，显示其他屏幕遮罩。
5. 停止插件或重载 Hammerspoon 时，清除所有遮罩。

为了让逻辑更清楚，我把它拆成两层：

- `core.lua`：纯 Lua 状态机，负责判断什么时候启用、什么时候切换屏幕。
- `init.lua`：Hammerspoon 适配层，负责读取屏幕、创建遮罩、绑定快捷键。

核心思路可以用一句话概括：**只在鼠标跨屏时切换遮罩，而不是鼠标每移动一下就重画界面。**

遮罩本身使用的是 `hs.canvas`。它会在非当前屏幕上创建一块黑色半透明矩形：

```lua
overlay:appendElements({
  type = "rectangle",
  action = "fill",
  fillColor = { red = 0, green = 0, blue = 0, alpha = self.dimAlpha },
  frame = { x = 0, y = 0, w = "100%", h = "100%" },
})
```

这里的 `dimAlpha` 就是深浅差异的关键。默认值是 `0.32`，比较克制；我后来为了让效果更明显，把本机配置调成了 `0.55`。这个值越大，非当前屏幕就越暗。

Hammerspoon 加载配置如下：

```lua
hs.ipc.cliInstall()

hs.hotkey.bind({ "cmd", "alt", "ctrl" }, "R", function()
  hs.reload()
end)

hs.loadSpoon("ScreenFocusDimmer")
spoon.ScreenFocusDimmer.dimAlpha = 0.55
spoon.ScreenFocusDimmer.checkInterval = 0.25
spoon.ScreenFocusDimmer:bindHotkeys({
  toggle = { { "cmd", "alt", "ctrl" }, "D" },
})
spoon.ScreenFocusDimmer:start()

hs.alert.show("Hammerspoon loaded")
```

其中：

- `⌘ + ⌥ + ⌃ + D`：开关 ScreenFocusDimmer，对应配置里的 `cmd + alt + ctrl + D`。
- `⌘ + ⌥ + ⌃ + R`：重载 Hammerspoon 配置，对应配置里的 `cmd + alt + ctrl + R`。
- `dimAlpha = 0.55`：把明暗差异调得比较明显。
- `checkInterval = 0.25`：每 0.25 秒检查一次鼠标所在屏幕。

![ScreenFocusDimmer Spoon 项目结构：core.lua 负责状态判断，init.lua 负责 Hammerspoon 适配，tests 负责锁定关键行为](/images/posts/screen_focus_dimmer/spoon-project-structure.png)

> 这个 Spoon 的代码结构很小：`core.lua` 只做状态判断，`init.lua` 负责和 Hammerspoon API 对接，测试用例则用来锁住单屏、多屏、跨屏切换这些关键行为。

## 六、使用与最终效果

安装插件时，只需要把 `ScreenFocusDimmer.spoon` 放到 Hammerspoon 的 Spoons 目录：

```text
~/.hammerspoon/Spoons/ScreenFocusDimmer.spoon
```

然后在 `~/.hammerspoon/init.lua` 中加载它。

如果使用 Release 包，可以直接下载 zip 文件，解压后把 `ScreenFocusDimmer.spoon` 目录放到上面的 Spoons 目录：

[ScreenFocusDimmer.spoon.zip](https://github.com/litianc/screen-focus-dimmer-spoon/releases/download/v0.1.0/ScreenFocusDimmer.spoon.zip)

最终效果是：

1. 单屏时，插件保持启用状态，但不会启动轮询，也不会显示遮罩。
2. 接入多屏后，插件自动开始工作。
3. 鼠标在哪块屏幕，哪块屏幕保持明亮。
4. 其他屏幕被半透明黑色遮罩压暗。
5. 拔掉外接屏或关闭插件时，遮罩会被清理掉。

这个效果比我想象中更自然。它不会强行改变窗口布局，也不会打断当前操作，只是在视觉上给出一个轻微但明确的提示：现在正在工作的地方在这里。

## 七、资源占用与轻量化设计

一开始我也担心这种方案会不会很吃资源。毕竟听起来像是在持续检测鼠标，还要在多个屏幕上盖遮罩。

但实际设计下来，它比想象中轻很多。

首先，它不是实时视频处理，也不是每一帧都重绘屏幕。插件只是每 `0.25` 秒检查一次鼠标当前在哪块屏幕。

其次，遮罩并不是每次都重新创建。每块屏幕对应一层 `hs.canvas` 遮罩，创建后会被复用。鼠标还在同一块屏幕时，插件直接返回 `noop`，不会重复更新。

更重要的是，单屏时它不会启动检测。也就是说，如果没有外接显示器，插件虽然在配置中启用，但实际不会进入工作状态。

这里的轻量化主要来自三个判断：

1. 只在多屏时启动检测。
2. 只在鼠标跨屏时更新遮罩。
3. 使用遮罩模拟亮度变化，而不是控制硬件亮度。

第三点尤其重要。真正控制显示器亮度会遇到很多复杂问题，例如外接显示器协议不一致、系统权限限制、不同品牌显示器支持程度不同。相比之下，半透明遮罩虽然只是视觉模拟，但对这个需求来说刚好够用，而且更可控。

这也是很多个人工具开发中值得记住的一点：不要一开始就追求“物理上最真实”的实现，而要先判断用户真正需要的体验是什么。在这里，我需要的是注意力被引导，而不是显示器硬件亮度被精确调节。

## 八、从桌面自动化到个人化操作系统

这次写 ScreenFocusDimmer 的过程，让我重新意识到桌面自动化的价值。

Hammerspoon 这样的工具，负责把 macOS 变成一个可编程的环境。屏幕、鼠标、窗口、快捷键、剪贴板、菜单栏，这些原本分散在系统里的对象，都可以通过 Lua 脚本组织起来。它本身不预设你要解决什么问题，只是把能力开放出来。

而 AI 编程助手的出现，又把脚本开发的门槛降了下来。

过去这种工具主要属于高级用户。你需要愿意读文档，知道 macOS 有哪些 API，也能自己处理脚本的边界情况。现在则可以从一个很自然的描述开始：

> 鼠标在哪块屏幕，哪块屏幕就亮一点，其他屏幕暗一点。

然后 AI 可以协助查文档、拆逻辑、写代码、测试行为、打包成 Spoon，甚至上传到 GitHub。用户需要表达的是体验问题，AI 负责把这个问题逐步翻译成可以运行的自动化脚本。

这个变化很有意思。因为操作系统厂商服务的是最大公约数，它不可能为每个人的小习惯都做一个正式开关。但真实工作流恰恰由很多小习惯组成：

1. 晚上自动降低非当前屏幕的干扰。
2. 会议开始时自动整理窗口并关闭通知。
3. 根据当前 App 自动切换输入法、音量和窗口布局。
4. 连接外接显示器后恢复固定桌面环境。
5. 用快捷键把当前资料、截图、剪贴板内容送进 AI 工作流。

这些功能单独看都不大，可能也不值得做成一个完整 App。但它们如果围绕一个人的工作方式组合起来，就会逐渐变成一套私人化的桌面系统。

从这个角度看，未来的个性化软件不一定都是 App Store 里的完整应用，也可能是一组围绕个人习惯生成的小脚本、小插件和小自动化。Hammerspoon 提供自动化底座，AI 提供脚本生产能力，二者结合之后，很多过去“不值得专门开发”的功能，都可以被快速做出来。

电脑因此不只是一个被使用的工具，也逐渐变成一个可以被继续塑形的工作空间。

## 总结

ScreenFocusDimmer 是一个很小的插件。它没有复杂的界面，也没有宏大的功能，只是让 Mac 在多屏使用时，自动把注意力聚焦到鼠标所在的屏幕。

但这个小工具背后的过程很有代表性：先从一个具体的不适感出发，再找到 Hammerspoon 这样的自动化底座，最后借助 AI 把需求落成脚本和插件。

对我来说，这也是个人计算机重新变得有趣的地方。不是所有需求都要等待系统更新，也不是所有想法都要开发成大型软件。很多真实、细碎、只属于自己的工作习惯，都可以用这种方式一点点补上。

项目源码在这里：

[litianc/screen-focus-dimmer-spoon](https://github.com/litianc/screen-focus-dimmer-spoon)
