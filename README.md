---
id: flux-readme
title: Flux

module: posts
submodule: root
topic: guide

type: note
status: active
canonical: true

summary: Flux 发布与维护。

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
updated: '2026-11-01'
metadata_updated: '2026-11-01'
---

# Flux

[flux.fivsevn.com](https://flux.fivsevn.com/)：短文、照片和链接，直接从本仓库发布。

## 发布

- 文字：修改 [`trigger_text.md`](trigger_text.md) 的正文，设 `status: published`，提交到 `main`。`title` 留空时使用提交时间。
- 图片：上传到 [`trigger_imgs/`](trigger_imgs/)，每张图片生成一帖；配文写在提交的详细说明中。
- 手机上传前先拉取最新 `main`。等待 [Actions](https://github.com/fivsevn/fivsevn-flux/actions/workflows/build.yml) 成功后查看网页。

## 修改旧帖

网页 `/page/年/月/编号/` 对应 `flux/年/月/编号/index.md`，图片在同包的 `assets/`。

直接修改正文、标题或素材；保留 `id`、目录、`extra.published_at` 和来源记录。隐藏设 `status: hidden`，恢复设 `status: published`、`visibility: public`。删除时移除整个发布包。

## 维护

- `scripts/`、`schemas/`：导入、构建与共享 metadata 校验。
- `site-assets/`、`style.css`：界面素材和样式。
- `.publishing/`：上传处理进度和已验证部署记录。
- `_site/`：构建结果，不提交。

Actions 自动补全资料、转换上传图片、生成页面并核验线上文件，成功后清理匹配的入口原图。失败查看对应步骤后重跑；不要清空发布进度。

本地检查与预览：

```sh
pip install -r requirements.txt
python -m unittest discover -s tests
python scripts/build.py
python -m http.server 8000 --directory _site
```
