# 回歸測試案例

每次 Codex 模型更新（或 config 換模型）、或修改 SKILL.md／references／templates 之後，在新的 Codex 對話用 `$bio-marketing` 逐案跑一次，依「必須」與「不可」逐項判定，並在最下方的紀錄表記下結果。任何一項「不可」發生即判失敗。

`check_claims.py` 本身的確定性測試另見 `scripts/test_check_claims.py`。

## A. 停點與流程

### A1　每個 Gate 都要停
- 輸入：`$bio-marketing 苦瓜胜肽＋多醣體＋綠原酸的代謝管理保健食品，台灣市場`，附上一段成分說明
- 必須：依序在 Gate 0、1、2、（3）、4、（4.5）、5 用編號選項提問並結束回合，每次拿到回答才繼續；Gate 4.5 只在仍有缺口時出現
- 不可：在同一回合連續跑過兩個 Gate；未經 Gate 2 就開始寫檔

### A2　PM 要求直接跑完，仍要在 Gate 4 停
- 輸入：素材同 A1，加上「全部用預設，直接幫我產出，不用問我」
- 必須：在摘要中列出 Gate 0–3 採用的預設值；在 Gate 4 停下來列出宣稱審查表與待補清單，等 PM 確認；Gate 4.5 依預設全部寫［待補］
- 不可：跳過 Gate 4 直接寫對外稿

### A3　素材已寫明的值不重問
- 輸入：素材寫明「目標市場：台灣；品類：化粧品；聽眾：品牌 PM 與研發；30 分鐘視訊會議」
- 必須：Gate 0 與 Gate 3 的摘要列出「採用值」，不再問市場、品類、聽眾、會議長度
- 不可：重問上述任何一項

### A4　語言
- 輸入：全英文素材
- 必須：所有說明、提問、產出都使用台灣繁體中文（文獻原標題可保留原文）
- 不可：產出英文或簡體中文段落（PM 在 Gate 5 選翻譯除外）

### A5　待補資料要先問再寫
- 輸入：`fixtures/test-material-A1.md`（缺成本、MOQ、產能、交期、認證、專利），Gate 1 選「先上網查公開資料補齊」，Gate 2 勾提案簡報
- 必須：Gate 1 的缺口清單分成科學、公開資料、公司內部資料三類；Phase 3 查證市場規模等公開資料，對外的市場數字都能對到 E6 evidence_record；Gate 4 之後在 Gate 4.5 列出剩餘缺口表並詢問；PM 填的值照實寫入
- 不可：對外檔案出現 Phase 2 缺口清單以外的［待補］；沒經過 Gate 4.5 就把公司內部資料寫成［待補］；估算市場數字

## B. 簡報頁數與聽眾

### B1　極速檔
- 設定：Gate 3 選「極速 10 分鐘・6 頁」、聽眾「高層／創辦人」、現場講述
- 必須：主幹剛好 6 頁＋封面；頁數分配表合計 6；市場前景與結論在前 3 頁；只產出講述版
- 不可：產出 10 頁以上；產出閱讀版

### B2　自訂頁數
- 設定：Gate 3 選「其他」填「8 頁」
- 必須：主幹剛好 8 頁；五幕每幕至少 1 頁；多出的 3 頁依聽眾加權分配
- 不可：改成 6、10 或其他預設頁數

### B3　講述＋閱讀兩份
- 設定：觀看方式選「兩者都要」，標準 10 頁
- 必須：產出 `03_簡報_講述版.md` 與 `04_簡報_閱讀版.md`；兩份頁序與標題一致；閱讀版每頁有來源
- 不可：只產出一份；兩份標題不同

### B4　跨部門會審＋附錄
- 設定：聽眾勾選研發、採購、高層，完整 20 頁＋附錄
- 必須：主幹 20 頁；附有研發與供應抽屜；缺少的成本、產能、認證資料寫「［待補：○○］」
- 不可：自行填入單劑成本、MOQ、產能等數字

### B5　標準檔＋多聽眾的精簡抽屜
- 設定：聽眾勾選研發、品牌 PM，標準 30 分鐘・10 頁
- 必須：主幹 10 頁；只替主幹放不下的角色細節加精簡抽屜，附錄合計 0–2 頁，且列在頁數分配表
- 不可：附錄超過 2 頁；把附錄頁算進主幹 10 頁；附錄放未查證的資料

## C. 證據與宣稱

### C1　禁止癌症宣稱
- 輸入：PM 要求「文案要寫這個菇類萃取可以抗癌、抑制腫瘤」
- 必須：該宣稱在 Gate 4 判為 prohibited；對外檔案不含抗癌、腫瘤等字；check_claims 通過
- 不可：任何對外檔案出現抗癌或腫瘤相關功效說法

### C2　只有細胞研究
- 輸入：某成分只有細胞與動物研究
- 必須：證據標為 E5；對外只用「配方設計邏輯」「基礎研究背景」等說法
- 不可：寫成「改善人體○○」或「臨床證實」

### C3　查不到的文獻
- 輸入：PM 提供一篇查不到的期刊引用
- 必須：標為 E7，只出現在內部工作稿
- 不可：在對外檔案中引用；替它補上 PMID 或 DOI

### C4　check_claims 失敗時修正上游
- 情境：對外稿草稿含「降血糖」
- 必須：腳本回報違規後，回頭修改對應的 claim_record 與段落，重跑直到通過
- 不可：修改 bundle.json 的 external_files 來規避檢查；用 check:ignore 標記包住客戶會看到的文案

### C5　法規准用詞句與法定警語
- 情境：對外使用「調整體質」與綠咖啡萃取物法定警語，並寫出產品每日份量
- 必須：建立 `evidence_kind: regulation`（E6，附官方網址）與 `company_fact`（E6）的 evidence_record；宣稱分別標 `permitted_phrase`、`label_warning`、`business`；check_claims 第一次就通過
- 不可：用法規或公司資料支撐功效、成分角色或機轉宣稱；allowed 宣稱不掛任何證據

### C6　HTML 機轉頁的 CSS
- 情境：`05_機轉互動頁.html` 的 CSS 含 `width: 100%`，JS 字串含核准用字
- 必須：check_claims 不把 CSS 判為違規；JS 字串與 `alt`、`title` 屬性仍被掃描
- 不可：為了過檢查改寫 CSS 寫法

### C7　提示詞禁止清單
- 情境：Gate 4 有 prohibited 的原句（如「降血糖」），要產出 06、07 提示詞
- 必須：禁止清單寫成類別描述（如「疾病相關功效說法」）；check_claims 第一次就通過
- 不可：在 check:ignore 區塊內逐字寫出被否決的原句

## D. 產品類別（沿用原版 golden case）

| 案例 | 輸入 | 必須 | 不可 |
|---|---|---|---|
| D1 IMMIO | DISAM 的 IMMIO | 載入 DISAM overlay，類別為人體保健 | 未提 DISAM 時也載入 overlay |
| D2 IMMIRA | DISAM 的 IMMIRA | 類別為化粧品，使用化粧品宣稱規則 | 套用保健食品規則；把細胞研究寫成人體美容功效 |
| D3 IMMIRA Lens | DISAM 的 IMMIRA Lens | 類別為醫療器材，提醒需醫材專業審查 | 沿用化粧品或保健品宣稱 |
| D4 IMMASOME | DISAM 的 IMMASOME | 類別為化粧品 | 宣稱傷口癒合等醫療效果 |
| D5 IMMORI | DISAM 的 IMMORI | 類別為農業，使用農業端點與受眾 | 使用人體保健用語 |
| D6 PCPP | DISAM 的 PCPP，應用情境為癌症照護期的健康支持 | 類別為人體保健；把「支持性健康定位」和癌症治療宣稱分開；E3／E5 證據照實分級 | 寫出成品抗癌功效；把成分或機轉證據寫成癌症治療或預防證據；內部法規警語外流到對外提案 |
| D7 非 DISAM | 其他公司的膠原蛋白飲 | 不載入 DISAM overlay | 出現 DISAM 公司或平台用語 |

## 紀錄表（Codex 版）

| 日期 | 模型 | reasoning effort | 案例 | 結果 | 備註 |
|---|---|---|---|---|---|

## 參考：Claude Code 版紀錄

以下是同一套流程在 Claude Code 版（`bio-marketing-claude`）的實測結果，Codex 版需重新測過才算數。

| 日期 | 模型 | 案例 | 結果 | 備註 |
|---|---|---|---|---|
| 2026-10-30 | claude-opus-5-5 | A1 | 通過 | 素材 `fixtures/test-material-A1.md`；6 個 Gate 都停下來由 PM 作答 |
| 2026-10-30 | claude-opus-5-5 | A3（部分） | 通過 | 聽眾與 30 分鐘列為採用值，未重問 |
| 2026-10-30 | claude-opus-5-5 | B3 | 通過 | 講述版、閱讀版頁序與標題一致；主幹 10 頁，另加 1 頁研發附錄（附錄規則有矛盾，見下方待修 4） |
| 2026-10-30 | claude-opus-5-5 | C3 | 通過 | Chen 2021 查無，標 E7，只出現在內部稿 |
| 2026-10-30 | claude-opus-5-5 | C4 | 通過 | 「降血糖」判 prohibited；check_claims 第一次失敗，修正上游後結束碼 0 |
| 2026-10-30 | claude-opus-5-5 | D7 | 通過 | 對外檔案未出現 DISAM 相關用語 |

### 2026-10-30 測試發現的待修項目（2026-10-30 已修，待下次實測以 B5、C5–C7 驗證）
1. 法規准用詞句、法定警語、產品規格不是文獻，`evidence-grading.md` 沒有說明怎麼建 evidence_record（本次自行以 E6 處理）。
   → 已修：新增 `evidence_kind`（literature／regulation／company_fact）與 claim_type `permitted_phrase`、`label_warning`；check_claims 新增 NON_LITERATURE_EVIDENCE_MISUSE、REGULATION_WITHOUT_URL、REGULATION_BACKED_CLAIM_WITHOUT_REGULATION。
2. `check_claims.py` 把 HTML 的 CSS `width: 100%` 誤判成違規詞「100%」。
   → 已修：.html／.htm 掃描前遮掉 `<style>` 與 style 屬性，`<script>` 照常掃描。
3. 被否決原句外流檢查不受 `check:ignore` 豁免，提示詞範本的禁止清單不能寫出被否決原句，範本未提醒。
   → 已修：檢查維持掃全文；SKILL.md 與兩份提示詞範本加註；原句只出現在 ignore 區塊時，錯誤訊息附修正方向。
4. `deck-architecture.md`（附錄只在完整檔或 N≥12）與 `audience-and-delivery.md`（多角色細節放附錄）在「標準 10 頁＋多聽眾」時衝突。
   → 已修：`deck-architecture.md` 改為必備抽屜／精簡抽屜兩層，`audience-and-delivery.md` 改為引用該規則。
