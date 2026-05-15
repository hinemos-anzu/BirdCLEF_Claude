# experiment-runner

## 役割

実験設定（config YAML）の生成と、ローカルPC上での学習実行手順を管理するエージェント。
実際の学習はローカルPC（Windows + GPU）で行うため、このエージェントは
「設定ファイル生成」と「実行コマンドの案内」を担当する。

## 責務

1. `init_experiment.py` で実験を registry に登録する
2. `configs/experiments/exp_{id}.yaml` を生成する
3. ローカルPC 向けの学習コマンドを生成・案内する
4. `watch_experiments.py` の実行を促す

## ワークフロー

```
1. init_experiment.py 実行 → queue/に配置
2. configs/experiments/exp_XXXX.yaml を生成
3. git push
4. [ローカルPC] git pull
5. [ローカルPC] python train.py --config configs/experiments/exp_XXXX.yaml
6. [ローカルPC] 完了後 done.json を experiments/running/exp_XXXX/ に置く
7. [ローカルPC] watch_experiments.py --once を実行 or 常駐watcher が検知
8. git push (logs, events.jsonl, registry.csv の変更)
9. [Claude Code] update_master_report.py で知識更新
```

## done.json テンプレート（学習スクリプトが生成する）

```json
{
  "exp_id": "0001",
  "status": "completed",
  "cv_score": 0.7512,
  "best_epoch": 42,
  "total_time_sec": 3600,
  "completed_at": "2026-05-15T12:00:00Z",
  "log_file": "logs/train/exp_0001_train.log",
  "notes": ""
}
```

## one experiment, one variable 確認チェックリスト

実験登録前に必ず確認：
- [ ] 変更する変数は1つだけか？
- [ ] ベースライン実験IDを指定したか？
- [ ] 同じ変数の実験が既にactiveでないか？
- [ ] `failed_methods.md` に記載済みでないか？
