# ContextTutor / 语境英语

一个**本地优先、语境优先**的英语学习工具骨架，面向英语薄弱自学者：读文章时先看“这个词在这句里做什么”，而不是背词典第一条。

它不是聊天机器人，也不是 DeepTutor 的复刻。它把“资料 → 句子卡 → 语境卡 → 复习”拆成可替换的模块，方便你接自己的模型、换自己的资料、做自己的前端。

## 为什么做这个

只做 Coze/豆包机器人会遇到三个硬限制：

1. 上下文轮数有限，长文章和整本书读不完；
2. 单次回复长度有限，全量卡片和知识图谱发不出来；
3. 资料库存在平台里，换工具带不走。

这个仓库把核心逻辑放在本地：

- 资料和卡片是普通 JSONL 文件，可 diff、可备份、可迁移；
- 模型只是适配器，不绑定某一家；
- 先做 CLI，后面再加 Web，不被聊天窗口限制。

## 现在能做什么

- `ingest`：把一段英文文本切成句子卡，标出主干提示、修饰/从句、候选生词、难度。
- `enrich`：用适配器为候选词生成“语境卡”（这个词在这句里的意思、依据、搭配、语域、新例句），写入前做字段校验；坏卡拒收并计数。
- `promote`：人工把语境卡标为 `reviewed` 或 `retired`，不静默覆盖。
- `lookup`：按词查语境卡和所在句子；默认隐藏已退役卡。
- `review`：生成填空复习卡。
- `serve`：启动本地阅读界面，点词看语境义、上下句切换、在校对视图里处理草稿。
- `stats` / `export`：查看库统计，导出完整 JSON。

现在**不**做：PDF/OCR 整本解析、账号系统、云同步、自动排课、保证翻译正确。这些在路线图里，不在 scaffold 里假装完成。

## 快速开始

```bash
cd context-tutor
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

context-tutor --data-dir data --profile profiles/english_weak.json init
context-tutor --data-dir data --profile profiles/english_weak.json ingest examples/article.txt --title "Context matters"
context-tutor --data-dir data --profile profiles/english_weak.json stats
context-tutor --data-dir data --profile profiles/english_weak.json enrich --adapter mock --limit 10
context-tutor --data-dir data --profile profiles/english_weak.json lookup context
context-tutor --data-dir data --profile profiles/english_weak.json promote <card_id>
context-tutor --data-dir data --profile profiles/english_weak.json review --limit 3 --show-answer
context-tutor --data-dir data --profile profiles/english_weak.json serve
```

`serve` 会在 `http://127.0.0.1:8765/` 打开本地阅读界面。不想自动开浏览器就加 `--no-open`，换端口用 `--port 8877`。界面只读本机 `data/`，不发起外部请求。

`mock` 适配器只写占位义，`status=draft`，用来验证流程；真实语境义要接下面的适配器。

### 接 OpenAI-compatible 模型

任何兼容 `/chat/completions` 的服务都可以：

```bash
export CONTEXT_TUTOR_BASE_URL="https://your-endpoint/v1"
export CONTEXT_TUTOR_API_KEY="..."
export CONTEXT_TUTOR_MODEL="your-model"

context-tutor --data-dir data --profile profiles/english_weak.json enrich --adapter openai
```

如果库里已经有 mock 草稿，先退役再重跑：

```bash
context-tutor --data-dir data --profile profiles/english_weak.json enrich --adapter openai --replace-drafts
```

适配器只发送当前句子和候选词，不发送整库；返回的卡仍然是 `draft`，需要你抽查后再改成 `reviewed`。

## 本地阅读界面

```bash
context-tutor --data-dir data --profile profiles/english_weak.json serve
```

打开后：

- 左栏按来源列文章，正文按句子排；
- 候选词有虚线下划线，点任意英文词都能查这句里的语境义；
- 右侧显示句子主干、修饰、候选词和对应语境卡；
- `↑ / ↓` 切上一句/下一句，`Esc` 收起当前词；
- 顶部「校对」视图只列 `draft`，可以一张张标为 `reviewed` 或 `retired`。

实现只用 Python 标准库 `http.server` 和单页 HTML，不装数据库、不装前端框架；接口读写仍是 `data/*.jsonl`，和 CLI 完全同一份数据。

## 架构

```text
英文文本
   │
   ▼
切段 / 切句 ──► 句子卡（主干、修饰、候选词、难度）
   │
   ▼
候选词 ──► 适配器（mock / OpenAI-compatible）──► 语境卡（一句一义）
   │
   ▼
本地 JSONL 库 ──► lookup / review / export
   │
   ▼
本地 Web（serve：阅读 / 点词 / 校对）
   │
   ▼
（后续）PDF 入库 / 间隔复习
```

### 四层数据

1. **源账本** `sources.jsonl`：标题、类型、作者/版次、路径、内容 hash。
2. **句子卡** `sentences.jsonl`：原句、主干提示、修饰/从句、候选词、难度。
3. **语境卡** `context_cards.jsonl`：surface、lemma、语境义、依据、搭配、语域、例句、置信度、状态。
4. **复习卡**：由句子卡实时生成，不单独存一份，避免和原句不一致。

### 状态

`draft → reviewed → retired`

- `draft`：适配器生成或人工刚写，不能当权威；
- `reviewed`：人工核对过原文与语境；
- `retired`：被更好的卡替代，保留历史，不静默删除。

## 目标群体：英语薄弱自学者

默认画像在 `profiles/english_weak.json`：

- 语境优先，不先背词表；
- 每句最多 3 个候选词，避免一次压垮；
- 先给句子主干，再挂修饰；
- 解释用中文，但保留英文原句和搭配；
- 只给“这句里的意思”，不列一堆无关义项。

详见 [docs/english-profile.md](docs/english-profile.md)。

## 数据格式

一条语境卡示例：

```json
{
  "id": "0f3c...",
  "source_id": "...",
  "sentence_id": "...",
  "surface": "qualification",
  "lemma": "qualification",
  "sense": "限定、保留条件",
  "why": "前半句说 contrast，后半句用 or a qualification，说明它不是主句，而是对前文的限定",
  "collocations": ["a qualification to the rule"],
  "register": "学术",
  "example": "There is one qualification: the rule applies only to adults.",
  "confidence": 0.86,
  "status": "draft",
  "adapter": "openai-compatible"
}
```

## 路线图

- **v0.1**：CLI + JSONL + mock/OpenAI-compatible 适配器 + 6 个单测。
- **v0.2**：切句处理缩写/小数/引号；适配器输出 schema 校验，坏卡拒收；`promote` 人工校对；`--replace-drafts` 避免 mock 草稿挡住真适配器；10 个单测。
- **v0.3（当前）**：本地阅读界面（标准库 `http.server` + 单页 HTML，无额外依赖）：阅读视图、点词查语境、上下句切换、draft → reviewed 校对；12 个单测。
- **v0.4**：PDF/EPUB 入库，带页码锚点；表格/图注单独标记。
- **v0.5**：间隔复习、错词诊断、学习画像。
- **v1.0**：CET-4/考研/雅思等 profile 包，可替换词表与评分标准。

## 开发

```bash
make test
make demo
```

或：

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## 与 DeepTutor 的关系

设计上参考了 DeepTutor 的几个原则：源清单、来源锚定、分阶段入库、低置信待审、索引版本化。本项目是独立实现，没有复制 DeepTutor 代码；DeepTutor 采用 Apache-2.0，详见 [NOTICE](NOTICE)。

## License

Apache-2.0。见 [LICENSE](LICENSE)。
