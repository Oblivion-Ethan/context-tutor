# Contributing

这个仓库优先保证“数据可迁移、来源可回查、适配器可替换”。

## 开发前

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
make test
```

## 改动原则

- 不把模型调用写进 `library.py`；模型只走 `adapters/`。
- 新增字段先加 schema，再加代码，再补测试。
- 不静默覆盖旧卡；用 `retired` 或新 id。
- 不编页码、不编原文；缺来源就标“来源未给”。
- 不把“看过卡”当“掌握”；掌握需要用户实际作答证据。

## 提交

- 一个 PR 只做一件事；
- 带测试；
- 如果改了数据格式，在 PR 说明迁移方式。
