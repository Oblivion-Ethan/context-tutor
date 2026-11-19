from __future__ import annotations

import argparse
import json
from pathlib import Path

from .adapters import build_adapter
from .config import DEFAULT_PROFILE, load_profile
from .library import Library


def _print_stats(stats: dict) -> None:
    print(
        "源文件：{sources}｜句子卡：{sentences}｜语境卡：{context_cards}"
        "｜待审：{draft_context_cards}｜已校对：{reviewed_context_cards}｜已退役：{retired_context_cards}".format(
            **stats
        )
    )
    print(f"可复习句子：{stats['reviewable_sentences']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="context-tutor",
        description="语境优先的英语学习脚手架：入库、句子卡、语境卡、复习。",
    )
    parser.add_argument("--data-dir", default="data", help="数据目录，默认 ./data")
    parser.add_argument("--profile", default=None, help="学习者画像 JSON 路径")

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="初始化数据目录与默认画像")

    ingest = sub.add_parser("ingest", help="把一段英文文本切成句子卡")
    ingest.add_argument("file", help="UTF-8 文本文件")
    ingest.add_argument("--title", required=True, help="来源标题")
    ingest.add_argument("--kind", default="article", help="article / textbook / paper / notes")
    ingest.add_argument("--author", default="")
    ingest.add_argument("--edition", default="")
    ingest.add_argument("--max-words", type=int, default=None, help="每句最多几个候选词")

    enrich = sub.add_parser("enrich", help="为候选词生成语境卡（需要适配器）")
    enrich.add_argument("--adapter", default="mock", choices=["mock", "openai"])
    enrich.add_argument("--limit", type=int, default=None)
    enrich.add_argument(
        "--replace-drafts",
        action="store_true",
        help="先把同库里的 draft 卡退役，再用新适配器重跑（mock 换真适配器时用）",
    )

    promote = sub.add_parser("promote", help="人工校对：把语境卡标为 reviewed 或 retired")
    promote.add_argument("card_id")
    promote.add_argument("--status", default="reviewed", choices=["reviewed", "retired"])

    lookup = sub.add_parser("lookup", help="按词查语境卡与所在句子")
    lookup.add_argument("word")
    lookup.add_argument("--context", default=None, help="当前句子，用于优先匹配")

    review = sub.add_parser("review", help="生成填空复习卡")
    review.add_argument("--limit", type=int, default=5)
    review.add_argument("--show-answer", action="store_true")

    show = sub.add_parser("show", help="查看一张句子卡")
    show.add_argument("sentence_id")

    stats = sub.add_parser("stats", help="查看库统计")
    stats.add_argument("--json", action="store_true")

    export = sub.add_parser("export", help="导出完整 JSON")
    export.add_argument("--out", default="exports/library.json")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    profile = load_profile(args.profile) if args.profile else dict(DEFAULT_PROFILE)
    library = Library(args.data_dir, profile)

    if args.command == "init":
        profile_path = Path(args.data_dir) / "profile.json"
        profile_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"已初始化：{Path(args.data_dir).resolve()}")
        print(f"画像：{profile_path}")
        return 0

    if args.command == "ingest":
        result = library.ingest_file(
            args.file,
            title=args.title,
            kind=args.kind,
            author=args.author,
            edition=args.edition,
            max_words=args.max_words,
        )
        print(f"已入库：{result['source']}")
        print(f"新增句子卡：{result['sentences_added']}｜库内句子卡：{result['sentences_total']}")
        print("候选词已标在句子卡里；生成语境义请运行 enrich。")
        return 0

    if args.command == "enrich":
        adapter = build_adapter(args.adapter)
        result = library.enrich(
            adapter,
            limit=args.limit,
            replace_drafts=args.replace_drafts,
        )
        print(
            f"适配器：{result['adapter']}｜新增语境卡：{result['created']}"
            f"｜被校验拒绝：{result['rejected']}"
        )
        if result["replace_drafts"]:
            print("已先把同库 draft 卡退役。")
        if result["adapter"] == "mock":
            print("注意：mock 只写占位义，status=draft；真实语境义需要接入 LLM/词典适配器。")
        return 0

    if args.command == "promote":
        ok = library.set_status(args.card_id, args.status)
        if not ok:
            print("找不到这张语境卡。")
            return 1
        print(f"已更新：{args.card_id} → {args.status}")
        return 0

    if args.command == "lookup":
        result = library.lookup(args.word, context=args.context)
        print(f"查询：{args.word}")
        if not result["contexts"]:
            print("语境卡：暂无。先 enrich，或接入真实适配器。")
        for card in result["contexts"]:
            print(
                f"- {card['surface']}｜{card['sense']}｜{card['status']}｜置信度 {card['confidence']}"
            )
        if result["sentences"]:
            print("所在句子：")
            for sentence in result["sentences"]:
                print(f"- [{sentence['id']}] {sentence['text']}")
        return 0

    if args.command == "review":
        items = library.review(limit=args.limit)
        if not items:
            print("没有可复习的句子：先 ingest。")
            return 0
        print(f"复习卡 {len(items)} 张｜先填空，再核对。")
        for index, item in enumerate(items, start=1):
            print(f"\n{index}. {item['cloze']}")
            if args.show_answer:
                print(f"   答案：{item['answer']}")
        return 0

    if args.command == "show":
        matches = library.store.find("sentences", id=args.sentence_id)
        if not matches:
            print("找不到这张句子卡。")
            return 1
        sentence = matches[0]
        print(sentence["text"])
        print(f"主干提示：{sentence['main_clause']}")
        if sentence.get("modifiers"):
            print("修饰/从句：" + "｜".join(sentence["modifiers"]))
        print("候选词：" + ("、".join(sentence.get("candidate_words", [])) or "无"))
        print(f"难度：{sentence['difficulty']}｜来源：{sentence['source_id']}")
        return 0

    if args.command == "stats":
        stats_data = library.stats()
        if args.json:
            print(json.dumps(stats_data, ensure_ascii=False, indent=2))
        else:
            _print_stats(stats_data)
        return 0

    if args.command == "export":
        path = library.export(args.out)
        print(f"已导出：{path.resolve()}")
        return 0

    parser.print_help()
    return 1
