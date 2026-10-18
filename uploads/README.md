# flux 图片上传

手机快捷指令的保存位置：**`fivsevn/fivsevn-flux` 仓库的 `uploads/`**。

1. 在 Working Copy 拉取 flux 的最新 `main`。
2. 把新图片保存到本目录，可以使用子目录；每次新发使用新文件名。
3. 提交并推送到 `main`，自动启动 Publish flux。
4. 提交标题写普通说明；图片配文写在提交的 extended description，支持 Markdown。一次提交多张图时，每张各生成一帖，使用同一段配文。

支持 `.jpg`、`.jpeg`、`.png`、`.webp`、`.gif`，扩展名不区分大小写。HEIC 请先转换成 JPEG；不能识别或已损坏的文件会让任务报错。

同一路径的图片只创建一次帖子。修改旧帖、替换图片或改配文，请到 `flux/年/月/帖子编号/` 修改对应的文章包。移动或删除本目录的原稿不会修改已发布的帖子。

19 张旧原稿已从 assets 移入本目录，并设为迁移基线，不会重新发帖。以后 flux 图片统一保存在这个仓库。

[完整发布、修改和删除说明](https://github.com/fivsevn-agy/fivsevn-devlog/blob/main/posts/README.md#1-短内容flux)
