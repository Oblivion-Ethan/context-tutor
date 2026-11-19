# 架构说明

## 1. 这个仓库解决什么问题

英语薄弱自学者常见的问题不是“没有词典”，而是：

- 每个词都查，句子还是不懂；
- 词典给十条义项，不知道这句用哪条；
- 查完就忘，下一次换一句还是不会；
- 资料散在 PDF、网页、笔记里，无法积累成自己的库。

ContextTutor 的核心不是“回答一个问题”，而是把阅读资料变成**可查、可复习、可迁移的语境卡**。

## 2. 为什么不直接做聊天机器人

聊天机器人适合即时问答，不适合：

- 长文入库；
- 大量卡片持久化；
- 跨会话带走；
- 多轮校对；
- 未来接 Web/移动端。

所以这里采用“库 + CLI + 适配器”的分层，聊天机器人以后只是一个前端。

## 3. 模块

```text
src/context_tutor/
  cli.py              # 命令行入口
  library.py          # 入库、查词、复习、导出
  storage.py          # JSONL 追加/读取
  models.py           # Source / SentenceCard / ContextCard
  config.py           # 学习者画像
  english/
    segment.py        # 切段、切句
    candidates.py     # 候选词排序
    context.py        # 主干/修饰的粗提示
  adapters/
    base.py           # 适配器契约
    mock.py           # 占位适配器，只用于测试
    openai_compat.py  # OpenAI-compatible 适配器
```

## 4. 数据流

```text
text
  → split_paragraphs / split_sentences
  → SentenceCard（原句 + 主干提示 + 修饰 + 候选词 + 难度）
  → adapter.analyze_word(sentence, word)
  → ContextCard（语境义 + 依据 + 搭配 + 语域 + 例句 + 置信度）
  → JSONL 库
  → lookup / review / export
```

## 5. 适配器契约

适配器只做两件事：

```python
analyze_word(sentence, word) -> {
  "sense": "这句里的中文意思",
  "why": "语境依据",
  "collocations": [...],
  "register": "口语/学术/正式",
  "example": "同义项的新英文例句",
  "confidence": 0.0-1.0,
  "status": "draft"
}

translate_sentence(sentence) -> str | None
```

硬约束：

- 只解释**当前句子**里的义项，不列无关词典义；
- 没有把握就返回 `status="draft"`、低置信，不装作确定；
- 不编原文页码；页码由入库层记录，不由适配器猜；
- 适配器失败时返回可读错误，不让整批入库崩掉；
- 写入前统一走 `adapters/validate.py`：缺 `sense`、置信度非数字、非法状态直接拒收，并返回 `rejected` 计数。

## 6. 状态与人工校对

`draft`：机器生成或人工草稿，只能当线索。
`reviewed`：人工对照原句/原文后确认，可以当权威。
`retired`：被新卡替代，保留历史。

当前 CLI 用 `promote <card_id> --status reviewed|retired` 做人工校对；`enrich --replace-drafts` 会先把旧草稿退役，避免 mock 草稿挡住真适配器。v0.3 再加 Web 校对视图。

## 7. 掌握循环（预留，不在 v0.1 实现）

未来每个词/句走三步：

1. **识别**：在原句里认出语境义；
2. **回忆**：换一句同义项的新句，能说出意思；
3. **产出**：自己写一句或口头用出来。

证据只认用户的实际作答，不把“看过卡”当掌握。这和 DeepTutor 的 mastery loop 是同一原则，但本项目先做数据层，不先做评分器。

## 8. 从 DeepTutor 借鉴的原则

- **清单事实与检索分离**：库里有几个源、处理到哪，和“这次检索到什么”是两件事。
- **来源锚定**：卡片必须能回到原句/原文；没有来源就标“转述/来源未给”。
- **分阶段入库**：先结构，再抽卡，再合并；不整本一次吞。
- **低置信待审**：置信度低或推断项不直接当结论。
- **索引版本化**：未来换模型/换切分时，旧库不直接覆盖，保留版本。

本项目没有复制 DeepTutor 代码；只借鉴这些工程原则。

## 9. 当前边界

- 句子切分是规则版，能处理常见缩写、小数、引号、省略号，但列表、破折号、复杂引语仍会切错；
- 主干/修饰是粗提示，不是句法树；
- 候选词是频率+长度启发式，不是个性化难度模型；
- 没有 PDF/OCR；
- 没有 Web；
- 没有间隔复习调度器；
- 适配器输出没有自动事实校验，需要人工抽查。

这些都在路线图里，不在 scaffold 里假装完成。
