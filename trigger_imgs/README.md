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

1. 推荐网页或直接调用 GitHub 的快捷指令上传；网页可直接[点这里选图](https://github.com/fivsevn/fivsevn-flux/upload/main/trigger_imgs)。
2. 保存图片到本目录，保留手机原文件名。
3. 配文写在提交的 **可选详细说明（extended description）** 中，支持 Markdown；留空则只发图。提交并推送到 `main`。
4. 等待 [Build and deploy Flux](https://github.com/fivsevn/fivsevn-flux/actions/workflows/build.yml) 完成，打开 [flux](https://flux.fivsevn.com/) 核对图片和配文。

> **格式与批量**：支持 JPG/JPEG、PNG、WebP、GIF、HEIC/HEIF。一次上传多张，每张各发一帖，共用这次配文。
>
> **自动处理**：按提交的北京时间命名、转 WebP、补全共享 metadata 并建帖；核验线上页面和图片后清理入口原图及已转换旧图的 `main` 历史。每页展示 11 则正式帖子，失败时保留原图，同次提交重跑不重复发布。

> **标题与配文**：标题默认使用提交时间，提交摘要只是操作说明；配文使用详细说明。自定义标题请改保存帖子的 `title`。
>
> **修改旧帖**：编辑 `flux/` 下对应帖子的 `index.md`；重新上传图片会生成新帖。

历史清理会更新版本编号；旧 Working Copy 副本请重新克隆，不要合并旧历史。

[构建与维护](../README.md#publish-images) · [文字入口](../trigger_text.md)
