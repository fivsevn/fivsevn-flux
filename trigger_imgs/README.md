# flux 图片入口

把图片上传到 **`fivsevn/fivsevn-flux` 的 `trigger_imgs/`**，提交并推送到 `main` 即可发布。

1. Working Copy / 快捷指令先拉取最新的 `main`；网页上传可直接[点这里选图](https://github.com/fivsevn/fivsevn-flux/upload/main/trigger_imgs)。
2. 保存图片到本目录，保留手机原文件名。
3. 配文写在提交的 **可选详细说明（extended description）** 中，支持 Markdown；留空则只发图。提交并推送到 `main`。
4. 等待 [Publish flux](https://github.com/fivsevn/fivsevn-flux/actions/workflows/build.yml) 完成，打开 [flux](https://flux.fivsevn.com/) 核对图片和配文。

> **格式与批量**：支持 JPG/JPEG、PNG、WebP、GIF、HEIC/HEIF。一次上传多张，每张各发一帖，共用这次配文。
>
> **自动处理**：按上传提交的北京时间命名、转为 WebP、建帖并发布；核验线上页面和图片后清理入口原图。失败时保留原图，同次提交重跑会沿用已有帖子。
>
> **修改旧帖**：编辑 `flux/` 下对应帖子的 `index.md`；重新上传图片会生成新帖。

[详细英文说明](../README.md#publish-images) · [文字入口](../trigger_text.md)
