# .github

GitHub 仓库配置目录。

- `workflows/test.yml` — 推送到 main 或提 PR 时自动跑单元测试 + 仪表盘自检
- `workflows/build.yml` — 打 `v*` 标签（或手动触发）时用 PyInstaller 打包单文件 exe，
  自检通过后上传 Artifacts 并附加到对应 Release
