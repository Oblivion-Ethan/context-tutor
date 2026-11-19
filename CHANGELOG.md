# Changelog

## 0.3.0

- 新增 `serve`：本地阅读界面，只依赖 Python 标准库，不装数据库/前端框架。
- 阅读视图：按来源列文章，句子级阅读，候选词标出来，点任意英文词查这句里的语境义。
- 右侧语境卡面板：主干、修饰、候选词、语境义、依据、搭配、语域、例句、置信度、状态。
- 键盘 `↑ / ↓` 切句，`Esc` 收起当前词。
- 新增校对视图：只列 `draft`，可标为 `reviewed` 或 `retired`，写回同一份 JSONL。
- 新增 `/api/overview`、`/api/source`、`/api/lookup`、`/api/review`、`/api/cards/<id>/status`。
- 单测从 10 个增加到 12 个，覆盖页面、阅读 API 与状态更新。

## 0.2.0

- 切句保护常见缩写（Mr./Dr./e.g./etc.）、小数、引号、省略号。
- 适配器输出写入前校验：缺 `sense`、置信度非数字、非法状态、适配器错误都拒收。
- 新增 `promote`：人工把语境卡标为 `reviewed` 或 `retired`。
- 新增 `enrich --replace-drafts`：先退役旧草稿，再跑新适配器，避免 mock 卡挡住真卡。
- `lookup` 默认隐藏已退役卡。
- 统计增加已校对、已退役数量。
- 单测从 6 个增加到 10 个。

## 0.1.0

- 初始 CLI：init / ingest / enrich / lookup / review / show / stats / export。
- JSONL 库：sources / sentences / context_cards。
- mock 与 OpenAI-compatible 适配器。
- docs、JSON Schema、GitHub Actions CI、Apache-2.0 许可证。
