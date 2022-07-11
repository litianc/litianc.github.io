---
layout: post
title: Filecoin 手续费模型-超额燃烧
description: 作为《Filecoin 手续费模型-EIP1559》的姊妹篇，本文进一步分析Filecoin的手续费模型中的超额燃烧，并介绍一种降低超额燃烧费的方法。
tags: 区块链 IPFS Filecoin
---

# Filecoin 手续费模型-超额燃烧

时间：2021.3.5

作者：litianc

阅读时长：6分钟

## 前言

Filecoin主网上线前，作者曾写过文章分析Filecoin手续费模型，讨论关于Filecoin改用EIP-1559设计后的手续费计算模型和优缺点。在讨论计算模型时，默认认为理性的交易发送者不会设置超过Gas燃烧阙值，但在现实情况中，官方给定的设置却出现了Gas超额燃烧的不理性的结果。作为[《Filecoin 手续费模型-EIP1559》](/2021/03/Filecoin_gas_1)的姊妹篇，本文进一步分析Filecoin的手续费模型中的超额燃烧，并介绍一种降低超额燃烧费的方法。

## Filecoin的手续费回顾

在之前的文章中，我们介绍了Filecoin采用EIP-1559的方案，用于解决恶意设置GasLimit的问题。我们从宏观层面分析了交易手续费的计算模型和主要影响因素。

当时，由于理解有限，文中将GasLimit直接套用在Gas实际燃烧（gasToBurn）的概念上，但是这样的描述是不准确的。理论上，这样计算出的结果已接近实际FIL消耗，但在特定情况下会有最多10%的偏差。这一偏差就是我们中所说的超额燃烧费。

那么，为什么会有超额燃烧，在何种情况下会产生超额燃烧呢？

## 超额燃烧的由来

我们知道，Gas是由交易发送者支付的Filecoin链上资源消耗对应的燃料数量，类比汽车行驶一段距离需要消耗相应的汽油xx升。

与以太坊相似的，Filecoin的Gas也有GasLimit和GasUsed的概念。

- GasLimit：表示该笔交易最多消耗燃料数量，由交易发送方设置。
- GasUsed：表示交易上链所消耗的燃料数量，在交易上链之后计算出来。

与以太坊不同的，Filecoin区块中包含的所有消息的GasLimit之和不得超过BlockGasLimit；而以太坊是统计所有消息的GasUsed之和。

	> 一个有趣的知识点：由于Filecoin的区块链采用DAG结构，一个Tipset中可以有多个区块，同一高度下的区块顺序由下一个Tipset的区块统计。因此，交易产生的GasUsed只有在下一个Tipset的区块上链后才能被准确计算出来。

正是由于设计的差异，决定了Filecoin需要对Gas进行更复杂的设计，于是就有了Gas超额燃烧的概念。Gas超额燃烧的设计出现在EIP-1559上线之前，它与EIP-1559并不冲突，可以把它看作是比EIP-1559更基础的Gas模型规则。

## 超额燃烧的计算

**Gas超额燃烧（GasOverestimationBurn）**：当GasLimit和GasUsed之间的差异较大时，需要燃烧的额外Gas量。

根据GasLimit与GasUsed的数值，我们将Gas分为三种情况：

*（为了方便建模，假设评估系数 k = GasLimit / GasUsed）*

1. GasLimit较接近GasUsed（1 <= k < 1.1）时，认为GasLimit设置合理:

   ```
   GasOverestimationBurn = 0
   ```

2. GasLimit明显大于GasUsed（k >= 2.1）时，认为GasLimit设置不合理:

   ```
   GasOverestimationBurn = GasLimit - GasUsed
   ```

3. 当GasLimit处于上述两者之间（ 1.1 <= k < 2.1）时，认为这是一个过渡范围，采用抛物线进行拟合：

   ```
   GasOverestimationBurn = (GasLimit - 1.1* GasUsed) * (GasLimit - GasUsed) / GasUsed 
   GasOverestimationBurn = (k - 1.1) * (k - 1) * GasUsed
   ```

接下来，采用控制变量法，假设GasUsed=30000，横轴为 k，纵轴为 GasOverestimationBurn，得出Gas超额燃烧曲线，如下图。

![image-20210305140346917](/images/posts/Filecoin_gas_2/Gas超额燃烧曲线.png)

从Gas超额燃烧曲线，我们能够看出当GasLimit设置越高，超额燃烧也就越高；GasLimit越接近GasUsed，超额燃烧也就越少，在合理的GasLimit条件下，超额燃烧为0。

正常情况下，Filecoin客户端只需要在设置GasLimit时，比预估的Gas设置稍高一点（蓝色区间），就能实现“零”超额燃烧。但是现实却是，官方代码中给定的默认系数k=1.25，因此现阶段链上的大多数的交易都产生了超额燃烧费用。这究竟是一个feature，还是一个bug呢？让我们继续往下分析。

## Feature还是bug？

通过官方的社群交流平台的记录和github上的问题追踪，我们最终确定这是由一个Bug引发的官方的修改。在主网上线3个月后，社区成员提交的一个[问题报告](https://github.com/filecoin-project/lotus/issues/5066)。报告内容是ProveCommitSector交易类型（以下简称Prove交易）的Gas评估在特定条件下会有40%左右的评估偏差，从而导致Gas溢出、交易出错。为了避免Prove交易的Gas溢出问题，官方经过反复调整，最终还是把默认系数设置为1.25（即预留25%的向下波动空间）。

在v1.4.2 的版本时，经过我们对自建节点三种交易类型的数据分析，得出以下结论：

* Prove交易的评估偏差波动较大，最低与最高相差40%；
* PreCommitSector（以下简称Precommit）交易的有一定偏差，但偏差波动较小；
* SubmitWindowedPoSt（以下简称WindowedPoSt）交易能准确评估。

## 超额燃烧优化

上述三种交易是当前Filecoin网络矿工消耗手续费最多的交易类型。如果能够减少这三类交易的超额燃烧，甚至做到“零”超额燃烧，对矿工来说可以节省不小的开销。

我们对超额燃烧进行优化的基本思路是根据不同的交易类型分别实现。目前能够直接实现“零”超额燃烧的交易有PreCommit交易和WindowedPoSt交易；对于Prove交易，需等到共识部分的代码完善后才能实现最理想的优化。（Ps：3.4 的 v1.5.0 升级有部分改动，Prove交易数据需进一步实测）

因此，对于不同阶段的矿工，可操作的优化方法和优化空间也有所不同。

对于算力已经稳定，只需要发送WindowedPoSt交易的矿工，优化的操作比较简单：可以直接调整 mpool 中的评估系数GasLimitOverestimation，直至“零”超额燃烧。

对于正在增加算力的矿工，则需要权衡Gas超额燃烧的收益与Gas溢出的风险，结合节点新增算力的速度和交易的历史数据，计算出最适合自身节点的评估系数。

如果有代码修改能力的矿工，可以尝试在mpool的源代码中修改不同的交易类型的评估系数，从而实现当前手续费的最优化。

## 总结

超额燃烧费是Filecoin区块链搭建之初的基础设计，它的实现不受后来的EIP-1559的影响。这部分费用本身是带有一定惩罚属性的，法不责众，理论上Filecoin的所有的交易都应当很容易避免超额燃烧。目前官方正在通过底层数据结构修改来进行完善，以减少Prove交易的Gas评估偏差。我们相信普遍的超额燃烧情况只是一个短期的状态，通过技术升级最终将解决这一问题。那时，生态应用开发者和用户不必知晓底层复杂的概念逻辑，可以把注意力更多地投入到业务设计和产品体验中。