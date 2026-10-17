# fivsevn flux

[flux.fivsevn.com](https://flux.fivsevn.com/) 是随手文字和图片的发布页面。自 2026-10-18 起，内容直接来自 GitHub，不再通过 WordPress。

## 发文字

修改 devlog 仓库里的 [`posts/_flux/trigger.md`](https://github.com/fivsevn-agy/fivsevn-devlog/blob/main/posts/_flux/trigger.md)，替换正文，提交并推送到 `main`。顶部配置为：

```yaml
status: published
title: ""
```

正文使用 Markdown，支持 `[文字](网址)`、标题、列表、引用、表格和图片；普通换行也保留。`status: published` 公开发布；`status: draft` 只保存为草稿、不进入站点。仓库本身公开，草稿字段不提供保密能力。无需 `category`、`timezone` 或 `wp_status`；旧状态字段仅为历史提交兼容而保留读取支持。当前不支持定时发布。

`title` 是上方可点击的标题，留空时自动用提交时间生成时间文字，例如 `18 Oct, 2026 06:40`；也可以填写 `title: "今天的随手记"`。下方的 `date` 是实际发布时间，独立保存，统一使用 `Asia/Shanghai`。下一条想恢复默认时间标题，清空 trigger 的 `title` 即可。

每次 trigger 提交保存一条独立记录；相同提交重试不重复发文。显式填写 `slug` 时沿用原来“同 slug 只创建一次”的行为。修改旧帖应编辑 flux 对应文件，不重新提交 trigger。

## 发图片

继续用快捷指令选择 `fivsevn-assets/post/stream/`，通过 Working Copy 提交并推送。每张新图片生成一条记录，提交的 extended description 是配文，可以使用 Markdown。图片自动复制到 flux 文章包，之后显示不依赖 WordPress 或原图片 CDN。相同图片路径不会重复发文；要编辑旧帖，修改 flux 文章包。

assets 的 foodie、fieldlog、bygone、YouTube 等流程仍按各自原规则运行。

## 何时上线

[Publish flux](https://github.com/fivsevn/fivsevn-flux/actions/workflows/build.yml) 约每 5 分钟检查两个公开仓库，按先后顺序读取所有尚未处理的提交，保存记录、构建页面并直接部署 GitHub Pages。GitHub 定时任务可能延后；需要立即检查时可手动运行这个任务。

原 devlog 的任务只校验 Markdown。校验成功不等于 flux 已部署；以 Publish flux 的成功结果和实际页面为准。

`.publishing/state.json` 保存两个来源的处理位置，和新内容一起提交。重试不覆盖已存在的 flux 记录。来源历史被重写、处理位置消失时停止并报错，不擅自重发旧内容。

## 修改已发布内容

每条记录位于 `flux/YYYY/MM/{id}/index.md`，附件位于旁边的 `assets/`。直接修改对应 Markdown 并推送，自动构建上线。只改顶部 `title` 就能修改上方标题，时间线和独立页面同时更新。保留原 `id`、目录和 `date` 可保持网址、下方实际发布时间与排列位置。`status: hidden` 撤下网页；公开 Git 仓库及历史仍保留文件。

历史的 150 个文章包保留原网址和日期，全部由 flux 管理（`sync: manual`）。WordPress 导入工作流已停用，旧导入脚本已停用；以后修改或删除 WordPress 内容不会影响 flux。历史来源字段只用于追溯。

## 页面构建

`scripts/build.py` 把 Markdown 生成为首页、分页和单篇页。时间线保持 typing → 口袋 → 内容仓库链接 → 消息 → 分页 → 许可声明的顺序。`scripts/package_site.py` 只打包生成网页、公开附件和站点素材，不把脚本或草稿包发布到 Pages。

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python scripts/build.py
python scripts/package_site.py
```

本地检查无需运行导入脚本。`scripts/ingest_github.py` 会只读访问 GitHub，并在本地写入新文章包和处理位置；自动任务负责将这些变更一并提交。

内容许可：CC BY-NC-SA 4.0。引用及第三方材料仍遵循其原有权利与许可。
