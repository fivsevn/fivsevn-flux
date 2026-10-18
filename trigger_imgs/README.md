# flux 图片入口

手机快捷指令只需把图片保存到 **`fivsevn/fivsevn-flux` 仓库的 `trigger_imgs/`**，然后提交并推送到 `main`。

1. 让快捷指令先通过 Working Copy 自动拉取 flux 最新 `main`。
2. 保存图片，使用新时间戳文件名，例如 `20261018-093012-01.jpg`；同秒多张加序号。
3. 让快捷指令提交并推送。以上设置好后，日常只需运行一次快捷指令。需要配文就写在提交的 extended description，支持 Markdown；不写则只发图。

支持 JPG/JPEG、PNG、WebP、GIF、HEIC/HEIF，大小写均可。手机不用预先转换格式，也不用创建发布包。一次提交多张图片时，每张各生成一帖，使用同一段配文。

自动化：校验图片 → 转 WebP → 将文字和图片存入 `flux/年/月/帖子编号/` → 制作并发布网页 → 核验公开页面和图片 → 删除本入口已处理的原图。转换或发布失败时保留原图，重跑不重复发帖。坏图报错后，可以在同一路径换成正常图片或删除坏图，再提交推送；旧失败记录不会卡住后续发布。

照片以 WebP 质量 85 保存；PNG 和 GIF 使用无损 WebP，保留透明背景及动图。已有 WebP 不重复压缩。历史发布包的图片不批量重压。

本目录是临时收件箱。以后修改旧帖或换图，编辑对应的发布包；每次新发必须使用新文件名。原始上传仍可从 Git 历史恢复。文字入口为同仓库的 [`trigger_text.md`](../trigger_text.md)。

[完整发布、修改和删除说明](https://github.com/fivsevn-agy/fivsevn-devlog/blob/main/posts/README.md#1-短内容flux)
