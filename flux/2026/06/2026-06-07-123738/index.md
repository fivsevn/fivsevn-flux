---
id: 2026-06-07-123738
date: '2026-06-07T12:37:38+08:00'
title: 7 June, 2026 12:37
source: wordpress
wp_post_id: 3681
wp_url: https://fivsevn.com/2026/06/07/7-june-2026-1237/
wp_slug: 7-june-2026-1237
status: published
tags: []
comments: 0
sync: auto
---

以前看到这个：
<https://t.me/Z_Turns/1403>
> Created by Nickilism
> 在 Safari 中分享 URL 给这个 Shortcuts，会自动生成 Markdown 文件，再选择发给如 ChatGPT、Grok 等 Chatbot 来实现文章的总结。

作者站点：

- <https://github.com/Neurogram-R>
- <https://neurogram.notion.site/Neurogram-5dff7288cc914a85a7d8cf2b8d8706b1>

这个快捷指令特别好。我主要用它来抓取原文，再交给 AI 做逐句翻译和整理。
今天我改了一下内容抓取方式：原版用的是 iOS / Safari 自带的网页正文提取，也就是先把网页识别成 Article，再转成 Markdown；我改成了用 Jina Reader 提取正文，也就是把网页 URL 拼成 https://r.jina.ai/原链接，由 Jina Reader 返回 Markdown。
这样改的原因是：文章比较长、网页结构比较复杂的时候，Safari 不一定能抓全正文；Jina Reader 通常更适合把网页转换成完整的 Markdown 文本。当然，它依赖外部服务，高频或批量使用时可能会遇到限制，必要时需要 API key 或付费方案。但我目前只是针对部分文章手动整理，用量不高，问题不大。
我保留快捷指令这一层，是因为我想把交给 AI 的指令提前打包好。我的前置指令里包含 frontmatter 写法、翻译要求、格式规范等内容。这样从 Safari 分享网页后，快捷指令就能自动完成“抓取网页 → 组装提示词 → 输出 Markdown 文件”的流程，再把结果交给 ChatGPT、Grok 或其他工具处理。
