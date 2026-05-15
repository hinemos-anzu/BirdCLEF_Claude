# Submission Audit Report — 2026-05-15

> **SYNTHETIC DATA — replace with real files**
> このレポートは合成データを使用して生成されました。実ファイルへの差し替え後、SHA256・統計値を再確認してください。

最終更新: 2026-05-15
対象コンペ: BirdCLEF+ 2026

---

## 1. 概要

BirdCLEF+ 2026の提出候補ファイルに対し、全監査ステップを実施した。
3つの入力ファイル（SED/ProtoSSM/blend）はすべて品質チェックをPASSした。
SED比率スイープ（5段階: 0.35, 0.38, 0.40, 0.42, 0.45）も全ファイルPASSし、
差分分析でrank相関 ≥ 0.996を確認した。

---

## 2. 検証対象ファイル一覧

| ファイル | shape | SHA256 |
|---------|-------|--------|
| data/sample_submission.csv | (7200, 207) | `885bada956c516d18d9d1637d82d592749c382892c583867373095753c0889a3` |
| submissions/candidates/submission_sed.csv | (7200, 207) | `c07bf3285e37eda5632c731c4a2f0613e2f3769646867ecfaf727306b03acb8e` |
| submissions/candidates/submission_protossm.csv | (7200, 207) | `5d595e4df735850172831f06f854a0b831600ce19a968040480cad106398448d` |
| submissions/candidates/submission.csv | (7200, 207) | `83767ece6e01943a2693ce956d172d1434a9aa42a413c9565bb07e2a3f789af0` |

---

## 3. 個別監査結果

### 3.1 submission_sed.csv (SEDモデル)

| 項目 | 値 |
|------|-----|
| shape | (7200, 207) |
| SHA256 | `c07bf3285e37eda5632c731c4a2f0613e2f3769646867ecfaf727306b03acb8e` |
| NaN / Inf | 0 / 0 |
| スコア範囲 | [0.000000, 0.786006] |
| mean / std | 0.007977 / 0.055226 |
| cells > 0.5 | 5,450 |
| 列順一致 | ✓ |
| 行数一致 | ✓ |
| **総合判定** | **✓ PASS** |

**特性**: 上位20種への強い集中予測（max 0.786）、全体は疎（mean 0.008）。
5,450セル(> 0.5)と突出して多く、高スコア予測の偏りが顕著。

**class別mean上位10種 (SED)**:
- asikoe: 0.082578
- ashpri: 0.082506
- bkbwar: 0.081936
- bnhcow: 0.081806
- ashwoo: 0.081653
- boboli: 0.081407
- blknod: 0.081396
- asskng: 0.081092
- bongul: 0.080815
- bkcchi: 0.080670

### 3.2 submission_protossm.csv (ProtoSSMモデル)

| 項目 | 値 |
|------|-----|
| shape | (7200, 207) |
| SHA256 | `5d595e4df735850172831f06f854a0b831600ce19a968040480cad106398448d` |
| NaN / Inf | 0 / 0 |
| スコア範囲 | [0.000000, 0.574234] |
| mean / std | 0.012999 / 0.051117 |
| cells > 0.5 | 193 |
| 列順一致 | ✓ |
| 行数一致 | ✓ |
| **総合判定** | **✓ PASS** |

**特性**: より均一な分布（max 0.574、cells>0.5は193と少ない）。
meanがSEDより高く（0.013 vs 0.008）、広域的な予測分布を示す。

**class別mean上位10種 (ProtoSSM)**:
- ccbfin: 0.051390
- ashwoo: 0.051019
- chswar: 0.050272
- chispa: 0.050200
- brwpel: 0.050123
- asbfly: 0.050091
- chbant: 0.050028
- canwar: 0.050002
- asikoe: 0.049978
- calqua: 0.049913

### 3.3 submission.csv (現行ブレンド: SED×0.40 + ProtoSSM×0.60)

| 項目 | 値 |
|------|-----|
| shape | (7200, 207) |
| SHA256 | `83767ece6e01943a2693ce956d172d1434a9aa42a413c9565bb07e2a3f789af0` |
| NaN / Inf | 0 / 0 |
| スコア範囲 | [0.000000, 0.556101] |
| mean / std | 0.010990 / 0.039557 |
| cells > 0.5 | 25 |
| 列順一致 | ✓ |
| 行数一致 | ✓ |
| **総合判定** | **✓ PASS** |

**特性**: SEDの疎な高スコア予測とProtoSSMの均一な広域予測が合成された。
cells>0.5は25と大きく絞られ、高精度な予測への集中を示す。

**class別mean上位10種 (blend)**:
- ashwoo: 0.063273
- asikoe: 0.063018
- bkbwar: 0.062443
- ashpri: 0.062365
- boboli: 0.062314
- bnhcow: 0.061851
- ashdro: 0.061835
- asbfly: 0.061766
- asskng: 0.061488
- blknod: 0.061424

---

## 4. ブレンドスイープ結果 (SED比率スイープ)

出力ディレクトリ: `submissions/candidates/blend_sweep_20260515/`

| SED_W | ProtoSSM_W | ファイル名 | NaN | Inf | min | max | mean | 判定 | SHA256 (先頭16) |
|-------|-----------|-----------|-----|-----|-----|-----|------|------|--------|
| 0.35 | 0.65 | submission_blend_sed035_protossm065.csv | 0 | 0 | 0.000000 | 0.554760 | 0.011241 | ✓ PASS | `791feae13b4e3f85...` |
| 0.38 | 0.62 | submission_blend_sed038_protossm062.csv | 0 | 0 | 0.000000 | 0.555564 | 0.011091 | ✓ PASS | `9abf230151e51ab7...` |
| 0.40 | 0.60 | submission_blend_sed040_protossm060.csv | 0 | 0 | 0.000000 | 0.556101 | 0.010990 | ✓ PASS | `45eab7d37e5ec371...` |
| 0.42 | 0.58 | submission_blend_sed042_protossm058.csv | 0 | 0 | 0.000000 | 0.559079 | 0.010890 | ✓ PASS | `094c9b50a4233654...` |
| 0.45 | 0.55 | submission_blend_sed045_protossm055.csv | 0 | 0 | 0.000000 | 0.567194 | 0.010739 | ✓ PASS | `6a052aaacb3f3982...` |

SHA256 (フル):
- sed035: `791feae13b4e3f8519775a1d1a712a976ca0f013ef7da25f72720b1d97b6e29a`
- sed038: `9abf230151e51ab7b611bb6397b4416ad5adee5a453238930c078cdf3f1268f6`
- sed040: `45eab7d37e5ec371f7ce500ab4ddb4864497352b7abdd1f2a34e117c2bcc5455`
- sed042: `094c9b50a42336f54e0605f3f15cd877b6faad893f63eaac883b5dfcc82a9db9`
- sed045: `6a052aaacb3f398295d8e04bb279c4dfd760be9750edfa666499e377eeb09144`

全5ファイルが監査PASS。NaN/Inf = 0。スコア範囲 [0.0, 1.0] 内。

---

## 5. 差分分析 (baseline: SED=0.40)

### 5.1 rank相関・top-1変化率

| SED_W | Spearman rank corr | Top-1変化率 | mean差分 | max差分 |
|-------|-------------------|------------|---------|--------|
| 0.35 | 0.996543 | 17.2222% | +0.00025114 | -0.00134100 |
| 0.38 | 0.998587 | 7.1389% | +0.00010046 | -0.00053700 |
| 0.40 | 1.000000 | 0.0000% | +0.00000000 | +0.00000000 |
| 0.42 | 0.998388 | 7.8194% | -0.00010045 | +0.00297800 |
| 0.45 | 0.996066 | 17.4167% | -0.00025114 | +0.01109300 |

**考察**: rank相関は全候補で0.996以上。baselineとの変動は微小であり、SED比率の微調整は予測順序に大きな影響を与えない。SED=0.45のmax差分+0.011はSEDの疎な高スコア成分が増幅されていることを示す。

### 5.2 Top-10 species mean変化 (SED=0.35 vs baseline)

SED比率を下げる(0.35)と上位種のmeanが約-0.0016減少（ProtoSSM寄りの均一分布へ）。
SED比率を上げる(0.45)と上位種のmeanが約+0.0016増加（SED偏り強化）。
上位種の顔ぶれは変わらず: ashwoo, asikoe, bkbwar, ashpri, boboli, bnhcow, ashdro, asbfly, asskng, blknod。

### 5.3 スコア分布変化（ヒストグラム差分 vs baseline）

SED_W=0.35 (ProtoSSM寄り):
- 0.0-0.1: -2,028セル（低スコア帯が薄まる）
- 0.1-0.3: +1,912セル（中スコア帯が増加）

SED_W=0.45 (SED寄り):
- 0.0-0.1: +3,039セル（SED由来の疎パターン強化）
- 0.1-0.3: -3,652セル（中スコア帯が減少）
- 0.3-0.6: +613セル（高スコア帯がわずかに増加）

---

## 6. reject判定結果

### reject判定基準
1. `knowledge/failed_methods.md` キーワードと一致 → REJECT
2. SED比率 > 0.50（high risk: SEDの過信） → REJECT
3. one variable以外の変更が含まれる → REJECT
4. validation_passed でない → REJECT

### 各候補の判定

| 候補 | failed_methods一致 | SED>50% | one_variable | validation | 判定 |
|-----|------------------|---------|-------------|-----------|------|
| sed035_proto065 | ✓ なし | ✓ 35% ≤ 50% | ✓ blend_weight_sed | ✓ PASS | **APPROVED** |
| sed038_proto062 | ✓ なし | ✓ 38% ≤ 50% | ✓ blend_weight_sed | ✓ PASS | **APPROVED** |
| sed040_proto060 | ✓ なし | ✓ 40% ≤ 50% | ✓ blend_weight_sed | ✓ PASS | **APPROVED (推奨)** |
| sed042_proto058 | ✓ なし | ✓ 42% ≤ 50% | ✓ blend_weight_sed | ✓ PASS | **APPROVED** |
| sed045_proto055 | ✓ なし | ✓ 45% ≤ 50% | ✓ blend_weight_sed | ✓ PASS | **APPROVED** |

**全候補がAPPROVED**。failed_methodsに記載なし、全SED比率 ≤ 0.50。

---

## 7. 推奨候補

**推奨: `submission_blend_sed040_protossm060.csv`**
- 理由: 現行final blend（SED×0.40 + ProtoSSM×0.60）の再現。baseline確認目的。
- risk: low（比率変更なし）
- expected LB: 0.945（再現）
- SHA256: `45eab7d37e5ec371f7ce500ab4ddb4864497352b7abdd1f2a34e117c2bcc5455`
- 承認ファイル: `submissions/approved/blend_sed040_protossm060_approval.yaml`

次点として SED=0.38（ProtoSSM寄り、より安定）も検討可。
SED=0.45はmax score+0.011と分布が広がり、SED過信リスクが微増する。

---

## 8. 知見まとめ

1. **SEDモデルの予測偏り**: 上位20種に予測が集中（cells>0.5が5,450と突出）。SEDのみ提出は種カバレッジが低く、hidden testでペナルティの可能性。
2. **ProtoSSMの広域予測**: 206種に均等に低スコア予測を持ち、recall寄りの性質。
3. **ブレンドの効果**: 高スコアセル数が5,450→25と大幅減少。精度と多様性のバランスが取れている。
4. **blend weight感度**: rank相関0.996以上で、SED比率±0.05の調整は予測順序への影響が小さい。top-1変化率は±5%調整で約7〜17%の行で変化。
5. **SED比率の上限**: SED>0.50はhigh riskルールに抵触。現在の0.35〜0.45範囲は全てAPPROVED。

---

## 9. 承認フロー

1. `submissions/approved/blend_sed040_protossm060_approval.yaml` を確認
2. `approved_by` と `approved_at` を記入
3. `allow_submit: false → true` に変更（人間のみ可）
4. SHA256を実ファイルのものに更新
5. 提出後: `python scripts/ingest_lb_result.py --exp-id 0002 --lb-score <スコア>` でLBスコアを記録

---

*SYNTHETIC DATA — このレポートは合成データで生成されました。実ファイルに差し替え後、SHA256・全統計値を再確認してください。*
