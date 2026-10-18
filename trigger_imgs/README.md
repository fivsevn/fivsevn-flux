# flux 图片入口

将图片上传到 **`fivsevn/fivsevn-flux` 仓库的 `trigger_imgs/`**，提交并推送到 `main` 即可发布。

1. 让快捷指令先通过 Working Copy 拉取该仓库最新的 `main`。
2. 保存图片到本目录，保留手机原文件名，不用手动命名或转换格式。
3. 需要配文时，写在提交的 extended description 中（支持 Markdown）；不写则只发图。提交并推送到 `main`。
4. 等待 [Publish flux](https://github.com/fivsevn/fivsevn-flux/actions/workflows/build.yml) 完成，打开 [flux](https://flux.fivsevn.com/) 核对图片和配文。

> **格式与批量**：支持 JPG/JPEG、PNG、WebP、GIF、HEIC/HEIF。同次提交多张图片时，每张各发一帖，使用同一段配文。
>
> **自动处理**：仓库按上传提交的北京时间命名、转换 WebP、保存发布包并发布；核验公开页面和图片后清理入口原图。失败时保留原图，同次提交重跑不重复发帖。
>
> **修改旧帖**：编辑 `flux/` 下对应的发布包。重新上传图片会生成新帖。

[详细英文说明](../README.md#publish-images-from-the-phone-shortcut) · [文字入口](../trigger_text.md)
