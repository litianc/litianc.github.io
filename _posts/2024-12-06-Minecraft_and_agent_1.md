---
layout: post
title: 我的世界与智能体（一）搭建LLM驱动的机器人
description: 在可预见的未来，LLM对游戏的改变，将会从智能助手、精神陪伴、NPC的升级，逐步扩大到规则的制定，甚至影响现实世界的社会秩序。就像科幻电影《西部世界》中的AI，在虚拟世界中扮演着人类角色，甚至可以涌现出人类文明。这样的文明可能会成为现实，虽然它今天还只是个游戏，只是《我的世界》中第一个机器人。
tags: AI 人工智能 Agent
---

> 作者：litianc
>  
> 时间：2024年12月6日
> 
> 阅读时长：10分钟

## 我的世界=西部世界?

大语言模型的出现给了开放世界类游戏更多想象空间，尤其是深受Z时代喜爱的《我的世界》（Minecraft），快要被智能体玩坏了。Project Sid 智能体文明项目由初创公司 Altera 推出，它在 Minecraft 的 1000 个自主的 AI 智能体合作数天，“涌现”出政府、经济、文化、宗教等组织行为，在共同创建的虚拟社会中开展各种各样的任务。此外，有大学生提出通过LLM驱动DND（Dungeons and Dragons）项目，让NPC在游戏中扮演更加复杂和真实的人物角色，提供更加丰富和沉浸式的游戏体验。复旦NLP团队和米哈游，联合发表论文《综述：全新大语言模型驱动的Agent》讨论了人机共存的虚拟世界中LLM的价值和社会的复杂性。

<div align="center" style="display: flex; justify-content: center; align-items: flex-end;">
  <div style="margin: 10px;">
    <img src="/images/posts/Minecraft_and_agent_1/dnd.png" alt="地下城与龙" style="height: auto; max-height: 300px;">
    <p align="center">地下城与龙</p>
  </div>
  <div style="margin: 10px;">
    <img src="/images/posts/Minecraft_and_agent_1/altera.png" alt="Project SID" style="height: auto; max-height: 300px;">
    <p align="center">Project Sid</p>
  </div>
</div>

在可预见的未来，LLM对游戏的改变，将会从智能助手、精神陪伴、NPC的升级，逐步扩大到规则的制定，甚至影响现实世界的社会秩序。就像科幻电影《西部世界》中的AI，在虚拟世界中扮演着人类角色，甚至可以涌现出人类文明。这样的文明可能会成为现实，虽然它今天还只是个游戏，只是《我的世界》中第一个机器人。

> 笔者计划围绕我的世界与智能体出一个系列文章，从搭建LLM驱动的机器人开始，逐步探索我的世界Agent进阶玩法，最后再探讨虚拟社会治理与伦理问题。第一篇，我们介绍如何搭建一个LLM驱动的机器人，并展示一些有趣的效果。

## 话不多说，先看效果

建造是《我的世界》中的一种玩法，多名玩家可以相互协作，以像素点的方式搭建各种3D建筑和场景。
我们在网上找几个大神玩家建造的建筑效果给大家展示。

<div align="center">
  <img src="/images/posts/Minecraft_and_agent_1/minecraft-competition.jpg" alt="Minecraft Competition" style="width: 70%; height: auto;">
  <p>Claude-sonnet-3.6对比 gpt-o1-preview</p>
</div>

<div align="center" style="display: flex; justify-content: center; align-items: flex-end;">
  <div style="margin: 10px;">
    <img src="/images/posts/Minecraft_and_agent_1/minecraft-sonnet1.jpg" alt="地下城与龙" style="height: auto; max-height: 300px;">
    <p align="center">Claude-sonnet-3.6</p>
  </div>
  <div style="margin: 10px;">
    <img src="/images/posts/Minecraft_and_agent_1/minecraft-gpt4o.jpg" alt="Project SID" style="height: auto; max-height: 300px;">
    <p align="center">gpt-4o</p>
  </div>
</div>

## 我的世界，出发

### 简洁搭建流程

千里之行，始于足下。我们动手搭建一个最小版本的LLM驱动的机器人，并展示一些有趣的效果。

首先，我们会构建一个我的世界服务器，整个世界只有空地，用于搭建建筑。
<div align="center">
  <img src="/images/posts/Minecraft_and_agent_1/minecraft-login.png" alt="Minecraft Login" style="width: 70%; height: auto;">
</div>

然后，使用Minecraft客户端，连接这台服务器并登录，也可以将服务器信息共享给其他朋友，一同参与建造。当然，这里我们准备邀请的是机器人朋友。
<div align="center">
  <img src="/images/posts/Minecraft_and_agent_1/minecraft-localserver.png" alt="Minecraft Local Server" style="width: 70%; height: auto;">
</div>

最后，我们启用了Claude大语言模型驱动的机器人，并在客户端中通过对话给她下达建造命令。在我的世界中操作一个机器人的基础环境便完成了。

![mindcraft-move](/images/posts/Minecraft_and_agent_1/mindcraft-move.gif)

### 详细搭建步骤

本节主要帮助那些希望动手安装游戏环境和机器人的读者，避免重复前人踩过的坑。我们把搭建过程共分为三个模块，分别是：我的世界服务器、客户端和机器人。动手搭建过程需要一些计算机的基础知识，例如：docker、python、node等。

#### 模块一：我的世界服务器

我使用一台公有云ubuntu22.04的服务器，2核4G，作为我的世界服务器。

**第一步**，下载Orchestrator项目代码。

Orchestrator项目是由大神mc-bench开发的开源项目，项目最终目标是实现服务器和机器人一键部署，目前我们主要使用它用于搭建游戏服务器。

```git clone https://github.com/mc-bench/orchestrator.git```

如果国内服务器遇到clone失败，可以尝试使用代理。

```git clone https://ghp.ci/https://github.com/mc-bench/orchestrator.git```

> 特别提示：目前 这个代码库还没有打正式版本号，有可能最新的代码会出现运行不起来的情况，我目前跑通过的commit是83f9912b1a2c6aa485e4bed9819acb9e96ba9eb2，如果出现运行不起来的情况，可以用
``git reset --hard 83f9912b1a2c6aa485e4bed9819acb9e96ba9eb2``命令后尝试启动（别问我为什么知道，说多都是泪）。

**第二步**，安装基础环境

基础环境包括docker、docker-compose、redis-server、miniconda等，如果已经安装了可以跳过。
- docker
  ```bash
  # 1. 更新软件包索引并安装必要的依赖软件
  sudo apt update
  sudo apt install -y \
      apt-transport-https \
      ca-certificates \
      curl \
      software-properties-common

  # 2. 添加 Docker 的官方 GPG 密钥
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
  # 遇到需要错误可能需要升级openssl
  apt upgrade openssl

  # 3. 添加 Docker 的官方 APT 仓库
  sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"

  # 4. 更新 apt 包索引并安装 Docker
  sudo apt update
  sudo apt install -y docker-ce docker-ce-cli containerd.io

  # 5. 验证 Docker 是否安装成功
  sudo docker run hello-world

  # 6. 设置 Docker 注册表镜像加速器
  sudo mkdir -p /etc/docker
  sudo tee /etc/docker/daemon.json <<-'EOF'
  {
    "registry-mirrors": ["https://dockerpull.org"],
    "insecure-registries": ["https://dockerpull.org"]
  }
  EOF

  # 7. 重启 Docker 服务
  sudo systemctl daemon-reload
  sudo systemctl restart docker
  ```

- docker-compose
  ```bash
  # 1. 下载 Docker Compose 的最新版本
  sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose

  #  如果国内服务器下载失败，可以尝试使用代理。
    curl -L "https://ghp.ci/https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose

  # 2. 赋予可执行权限
  sudo chmod +x /usr/local/bin/docker-compose

  # 3. 验证安装
  docker-compose --version
  ```

- redis-server

  ```bash
  sudo apt update
  sudo apt install -y redis-server
  ```

- miniconda
  ```bash
  # 1. 下载 Miniconda 安装脚本
  wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
  # 2. 安装Miniconda
  bash Miniconda3-latest-Linux-x86_64.sh
  # 3. 创建conda环境
  conda create -n mc python=3.12
  # (如果按官方推荐的安装3.7后续安装依赖会报错)
  # 4. 激活conda环境
  conda activate mc
  #  5. 安装依赖
  pip install -r requirements.txt
  ```

第三步，启动服务

  ```bash
  python server_manager.py
  ```

  在运行完成后使用``docker ps``命令能够看到``mc-llm-37d232d1``的容器正在运行，说明启动成功，属于你的游戏服务器已搭建完成。通过防火墙和安全组设置，将25565端口设置为公开访问，同时记住这台服务器的ip地址，你和机器人就可以通过客户端连接到游戏服务器上。

#### 模块二：我的世界客户端

鉴于Minecraft是一个国际化广受关注的游戏，客户端的教程非常多，推荐一篇安装攻略：https://www.bilibili.com/opus/406887682451955645。
  
简单来说，需要安装Java运行环境（Jre）和Minecraft启动器。

Minecraft启动器分为官方启动器与第三方启动器，二者的功能是一模一样的。本文中使用的是HMCL启动器。启动游戏的版本为1.20.4。

启动游戏后，在“多人游戏”中，选择“添加服务器”，并将上面得到的"[服务器ip]:25565"填入服务器地址，点击“完成”即可加入这个世界。

#### 模块三：Mindcraft机器人
  Mindcraft是一个基于Minecraft的AI助手，它能够与玩家互动，提供游戏内的帮助和指导。Mindcraft使用自然语言处理技术，能够理解玩家的指令，并根据指令执行相应的操作。Mindcraft还可以与玩家进行对话，提供游戏内的聊天服务。Mindcraft还可以与玩家进行游戏内的互动，例如按照玩家指令搭建建筑、共同冒险等。

  - 模型选择
  
    Mindcraft 默认支持 OpenAI|Gemini|Anthropic|Replicate|Hugging Face|Groq|Ollama|Qwen|Novita 等模型API接口，并且也可以通过本地化部署模型来实现，但社区用户测试，演示效果最好的是Anthropic和OpenAI的模型，因此，这里演示Anthropic的模型API接口（Claude-sonnet-3.5）。

    *注：Anthropic是Claude大模型的母公司。*
  
  - Mindcraft启动
    ```bash
    # 1、购买一台海外云服务器，拉取Mindcraft代码
      git clone https://github.com/kolbytn/mindcraft.git

    # 2、安装node/npm，这里推荐使用nvm安装
      curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
      source ~/.bashrc
      nvm install --lts
      nvm use --lts

    # 3、安装依赖
      cd mindcraft
      npm install

    # 4、添加模型api_key
      # 将目录下的keys.example.json文件重命名为keys.json
      # 从 claude 官网，充值购买api的token额度，并生成api_key，填入keys.json文件对应位置，例如：
      {
        "ANTHROPIC_API_KEY": "sk-ant-api03-xxxx-Y9Hj8AAA" //这里用xxxx代表了真实的api_key
      }    

    # 5、修改setting.json
      # host改为Minecraft服务器的ip地址，port的值改为25565，host_mindserver改为false。
      {
        "host": "your.ip.address.here", // or "localhost"
        "port": 25565,
        "host_mindserver": false, 
        //...
        "allow_insecure_coding": true, 
      }
      # 根据模型修改profiles目录，例如，我用自带的配置andy_npc作为我的机器人伙伴，就将andy_npc加入profiles，并注释其他模型配置文件：
      {
        "profiles": [
            "./profiles/andy_npc.json"
        ],
      }
    # 6、启动
      node main.js
    ```
### 机器人首次试用

在我的世界中，玩家可以通过对话方式要求Mindcraft机器人执行各种任务，例如：采集资源、建造建筑、与其他NPC互动等。

例如：我们让他搭建一个三种颜色的小屋子，只需要一句对完话，机器人就可以按照我们的要求进行搭建。
![](/images/posts/Minecraft_and_agent_1/mindcraft-building.gif)

此外，还可以打断进行中的工作流程，安排新的任务，例如：我们让他搭建一个房子，中途提出增加两根柱子的需求。
![](/images/posts/Minecraft_and_agent_1/mindcraft-building2.gif)

初次试用的效果就先演示到这里，再回来说说我对我的世界这款游戏的理解。

## 为什么是我的世界

我的世界是一款开源，并且有活跃的社区，并且有广泛的玩家基础的游戏。

因为开源的特性，任何人都可以搭建专属的世界，也叫做私人服务器。我们可以使用云服务器、个人电脑、甚至是树莓派作为服务器，构建出一个强大的游戏环境。这样，我们可以在不影响其他玩家的前提下，测试我们自己的机器人，并且可以随时重置环境。

我的世界在全球范围内社区非常活跃，有很强的社交属性，有多达10亿级的玩家数量，他们可以提供各种帮助，例如：搭建世界，提供游戏资源等。在动手写这篇文章之前，我对这款游戏的环境、玩法和操作并不熟悉，但能很快通过 google + gpt 的工具搭建出一个简单的世界，这个过程深感这个社区的强大。

有一项我的世界玩家出身情况分布调查也非常有意思，国内玩家的出生时间最多分布在2002年~2007年。这代人正好在参加工作前，赶上AIGC开始普及，相信他们会有更多时间探索这款游戏和AI结合的颠覆性玩法。

## 下一步的工作
正如前文所说，笔者目前对我的世界游戏本身的了解有一定局限，所以还需要花大量时间来熟悉游戏的玩法，以便能更好地开发机器人的高级玩法。

此外，近一年AI的能力提升速度非常快，除了趣味性，AI结合虚拟社会的影响力和伦理问题也值得我们关注。总之，我会继续围绕我的世界和智能体开展更多工作。

> Ps：本文部分内容由AI参与撰写，感谢Claude AI的协助。