# GitHub Tag 发布

Designer 的发布流程已经完全移到编辑器外部，由 GitHub Actions 负责打包和发布。

## 使用方式

1. 在仓库里确认需要发布的代码、SDK submodule 指针和 CI 配置都已经提交。
2. 创建并推送版本 Tag。

```bash
git tag v1.2.3
git push origin v1.2.3
```

3. GitHub 会触发 `.github/workflows/designer-release.yml`。
4. 该 workflow 会在 Windows runner 上打包 Designer，生成 `EmbeddedGUI-Designer.exe` 所在的运行目录，并归档为 zip。
5. workflow 会把 zip、`designer-package-metadata.json`、`repo-health.json` 和 `SHA256SUMS.txt` 上传到对应的 GitHub Release。

## 说明

- Designer 编辑器内部不再提供 release / 打包入口。
- EXE 打包、校验和 GitHub Release 发布统一由 CI 处理。
- 如果只想验证打包结果，可以手动运行 `.github/workflows/designer-package.yml`。
