---
layout: post
title: 跟进DeepSeek-R1（二）：本地部署模型的 APIKEY 功能 
description: Ollama是本地部署大模型最通用的软件之一，对于有一定算力性能的电脑，装上ollama便可得到一个私人的AI助理。然而，以下两种情形可能会遇到较大的挑战...
tags: AI 人工智能 DeepSeek Ollama
---

> 作者：litianc
>  
> 时间：2025年3月1日
> 
> 阅读时长：4分钟

## 问题
Ollama是本地部署大模型最通用的软件之一，对于有一定算力性能的电脑，装上ollama便可得到一个私人的AI助理。然而，以下两种情形可能会遇到较大的挑战：
一、在企业内部署大模型，希望供多人使用，可能会遇到接口服务被滥用而无法追溯的问题；
二、个人使用，希望通过互联网上访问自建API，直接暴露端口可能会导致其他用户通过全网扫描而被攻击，导致数据泄露等问题。
因此，给Ollama等大模型的API端口增加一层身份认证是非常有必要的。

## 方案
这一问题，在ollama开源社区有非常广泛的讨论，也有人给出了诸多优秀的解决办法。其中，被认为最符合用户习惯的方式是像大模型服务商（如openai）那样，使用“API密钥”进行认证。这样，我们的所有的上层应用则不需要做任何代码改动，只需要在已有接口中配置APIKEY即可。
![image](/images/posts/ollama_auth/1740796310154.jpg)

方案1: 通过Nginx或Caddy 反向代理软件自带的认证功能，在访问流量入口增加API密钥认证。有部署过个人网站或企业运维的小伙伴应该非常熟悉这两个软件，他们是web服务的万金油。
方案2: 通过程序控制，重新写一个代理服务。下文中将介绍ParisNeo写的ollama_proxy_server。

此外，看到社区用户的投票，相信不久的一天ollama也会原生支持API密钥。

## ollama_proxy_server
Ollama_proxy_server，为了好记简称OPS，是一个轻量化的反向代理服务器，为ollama服务增加了一个安全层，并最小化影响ollama本身的服务。

Github仓库如下：
https://github.com/ParisNeo/ollama_proxy_server

它提供两种运行方式，python直接运行，以及docker运行。它的运行机制非常简单清晰，即通过一个白名单将运行通过认证的APIKEY都记录下来，并将不在白名单中的流量过滤。

### 安装步骤
``` sh
git clone https://github.com/ParisNeo/ollama_proxy_server.git
cd ollama_proxy_server; pip install -e .
```

如需做负载均衡，在配置文件config.ini中编辑相应的ollama IP地址和端口。默认信息入如下：
``` ini 
[DefaultServer]
url = http://localhost:11434
queue_size = 5

[SecondaryServer]
url = http://localhost:3002
queue_size = 3

# Add as many servers as needed, in the same format as [DefaultServer] and [SecondaryServer].
```

然后在authorized_users.txt文件中配置好APIKEY，每行是一个APIKEY，示例中用的是user:key的格式，但在实际使用中，需要将“aaa:bbb”整体都作为APIKEY填入应用程序中。

启动命令：
```
python3 ollama_proxy_server/main.py --config config.ini --users_list authorized_user.txt --port 8080
```

这样，通过暴露本机的8080端口，既可以得到一个经过安全认证的ollama服务接口。

## 验证
通过Cherry studio软件增加一个模型服务，选取局域网内的IP地址（或暴露在公网上的IP地址），可以提供一个更加安全的ollama模型服务。
![image](/images/posts/ollama_auth/Snipaste_2025-03-01_15-06-04.png)

并进行模型对话验证：
![image](/images/posts/ollama_auth/image.png)


