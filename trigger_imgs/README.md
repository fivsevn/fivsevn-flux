---
id: flux-trigger-imgs-readme
title: flux 图片入口

module: posts
submodule: guide
topic: guide

type: note
status: active
canonical: true

summary: flux 图片发布入口。

parents: []
related: []

tags:
- flux

audience:
- self
- internal
languages:
- zh

maturity: evolving
confidence: null

visibility: public
source_of_truth: site

filename_policy: entrypoint

created: null
updated: '2026-11-05'
metadata_updated: '2026-11-05'
---
# flux 图片入口

把图片上传到 **`fivsevn/fivsevn-flux` 的 `trigger_imgs/`**，提交并推送到 `main` 即可发布。

1. 每批保存前，先在 Working Copy 或 GitHub Desktop 同步该仓库的最新 `main`。
2. 确认快捷指令把图片保存到该本地仓库根目录的 `trigger_imgs/`，保留手机原文件名；电脑上传也放入同一目录。
3. 在 Working Copy 或 GitHub Desktop 中提交并推送到 `main`。配文写在提交的 **可选详细说明（extended description）** 中，支持 Markdown；留空则只发图。仅打开 app 或复制提交信息不等于已经推送。
4. 等待 [Build and deploy Flux](https://github.com/fivsevn/fivsevn-flux/actions/workflows/build.yml) 完成，打开 [flux](https://flux.fivsevn.com/) 核对图片和配文。

> **格式与批量**：支持 JPG/JPEG、PNG、WebP、GIF、HEIC/HEIF。一次上传多张，每张各发一帖，共用这次配文。
>
> **自动处理**：按提交的北京时间命名、转 WebP、补全共享 metadata 并逐图建帖；部署并核验线上页面和图片后清理入口原图，日常发布不改写 Git 历史。每页展示 11 则正式帖子，失败时保留原图，同次提交重跑不重复发布。

> **标题与配文**：标题默认使用提交时间，提交摘要只是操作说明；配文使用详细说明。自定义标题请改保存帖子的 `title`。
>
> **修改旧帖**：编辑 `flux/` 下对应帖子的 `index.md`；重新上传图片会生成新帖。

Git 历史清理仅在手动运行 `workflow_dispatch` 并勾选 `compact_image_history=true` 时执行，默认 `false`。维护后 Working Copy 和电脑副本需重新对齐或克隆，不要合并旧历史。

[构建与维护](../README.md#publish-images) · [文字入口](../trigger_text.md)
