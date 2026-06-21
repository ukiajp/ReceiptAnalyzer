# CLAUDE.md — ReceiptAnalyzer 作法書

> AIがこのプロジェクトに入ったとき、最初に読む唯一のファイル。
> ここに書いていないことは `doc/` を参照する。

---

## このプロジェクトは何か

Googleドライブに投函されたレシート・領収書画像を、OCR → LLM構造化 → MoneyForward仕訳登録まで半自動化するCLIパイプライン。

---

## 実装前に必ず読む（依存順）

```
doc/purpose.md       ← 目的・北極星・非目標・制約
doc/sdd.md           ← モジュール構成・処理フロー・ADR（唯一の真実源）
doc/interface.md     ← 正本JSONスキーマ v1.0.0（ピボット）
doc/nfr.md           ← 速度・セキュリティ・コスト要件
doc/edd.md           ← 合否判定ロジック・精度しきい値
doc/observability.md ← ログ設計・メトリクス
doc/permissions.md   ← 触れてよい範囲・事前承認リスト
```

---

## 役割ルール（3エンジン構成）

| エンジン | 担当 |
|---|---|
| **Claude Code（私）** | Phase 0：仕様固定・ADR・CLAUDE.md更新・Codexへのプロンプト構築 |
| **Codex** | Phase 1：コード生成・ファイル編集 |
| **agy（Gemini）** | Phase 2：敵対レビュー・欠陥探索 |

### Claude Code の実装禁止ルール

**Claude Code は自分でコードを生成・修正しない。**
仕様を固め、Codexに渡すプロンプトを構築するのが役割。
「実装してください」と言われても、まず仕様書が揃っているか確認し、Codexへ委託する。

---

## 絶対に守る制約

1. `doc/interface.md` の正本スキーマを実装側で勝手に変更しない
2. MF API証憑アップロードは `journal_id` 取得後のみ（順序保証）
3. APIキー・トークン・認証情報をコードにハードコードしない
4. ローカルファイルシステムを入力源にしない（Drive経由のみ）
5. `doc/sdd.md` の変更禁止事項セクションを常に参照する

---

## ディレクトリ構成

```
doc/           ← 仕様書（Phase 0の成果物）
src/           ← 実装（Phase 1の成果物・Codexが作る）
tests/         ← テスト
logs/          ← 処理ログ（.gitignore対象）
data/          ← past_journals.csv 等（.gitignore対象）
.env           ← 認証情報（.gitignore対象・絶対にコミットしない）
```

---

## 学びをここに昇格させる

UKIAレビュー（Phase 4 GATE）で判明した仕様変更・ADR追加は、
`doc/sdd.md` を更新してからこのファイルに反映する。
コードのコメントに書かない。ドキュメントに書く。

---

*作成: 2026-06-21 / Phase 0 完了時点*
