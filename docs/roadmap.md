# 路线图

## v0.1 scaffold

- CLI：init / ingest / enrich / lookup / review / stats / export
- JSONL：sources / sentences / context_cards
- 适配器：mock + OpenAI-compatible
- 单测：切句、候选词、入库、查词、复习、导出

## v0.2 语境卡质量

- 切句处理缩写（Mr./Dr./e.g.）、小数、引号、省略号；
- 适配器输出校验：缺 `sense`、置信度非数字、非法状态直接拒收；
- `promote` 人工确认，`draft → reviewed / retired`；
- `--replace-drafts` 先把旧草稿退役，再跑新适配器；
- `lookup` 默认隐藏已退役卡；
- 测试从 6 个增加到 10 个。

验收：

```bash
make test
```

## v0.3 本地 Web（当前）

- 使用 Python 标准库 `http.server`，不额外引入 FastAPI/前端构建；
- 阅读视图：左原文、右卡片；
- 点词弹卡，支持键盘上下句；
- 校对视图：draft → reviewed / retired；
- 数据仍在本地 `data/`，与 CLI 共用同一份 JSONL；
- 12 个单测，覆盖页面、API 与状态写回。

验收：不装数据库也能打开；所有操作离线可用；导出的 JSON 与 CLI 一致。

## v0.4 PDF / EPUB 入库

- 按页/章切分，保留页码锚点；
- 表格/图注单独标记，不混进正文；
- OCR 结果标“未识别”，不猜字；
- source hash 变化时提示重新入库。

验收：同一 PDF 重复入库按 hash 去重；页码能回到原页。

## v0.5 复习与诊断

- 填空 → 换句 → 产出三步；
- 错因：没认出 / 认错义项 / 搭配不熟 / 语法卡住；
- 只把错因回到最小修复，不重讲整篇；
- 复习排期可关闭，不强制每日任务。

验收：答错只回到一个最小点；不把“看过”记成“掌握”。

## v1.0 Profile 包

- CET-4 / 考研 / 雅思等词表与难度曲线；
- 每个 profile 独立配置，不互相污染；
- 允许用户自带词表/教材目录。

验收：换 profile 不改变旧库数据，只改变候选词与讲法。
