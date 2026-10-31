# DISAM 原料資料卡

只在 DISAM context 啟用時讀這份檔案（Phase 0 第 6 點）。

DISAM 自家原料（IMMIRA、IMMASOME 等）的規格、研究與商務條件，不在這個 skill 裡，而是放在公司提供的「原料資料卡」。沒有資料卡時，skill 只能從 DM 判斷，會把公司自己的原料當成查不到的供應商說法，產出內容會很少。

## 1. 去哪裡找

1. PM 在素材或對話中指定了資料卡路徑 → 用那個路徑。
2. 否則找 `~/DISAM-原料資料卡/`（`~` 是使用者家目錄）。
3. 檔名對應原料名稱，例如 IMMIRA → `IMMIRA.md`。大小寫、全形半形不同時也算同一個原料。

資料卡只放在本機或公司內部雲端，不在這個 skill 的資料夾裡，也不得複製進 skill 或任何公開 repo。

找不到資料夾或找不到某個原料的卡，在 Gate 0 摘要列出缺少哪些卡，並依 SKILL.md 的 Gate 0 問 PM 要不要提供。

## 2. 怎麼轉成 evidence_record

| 資料卡段落 | evidence_kind | 等級 | verification.status | 可支撐的 claim_type |
| --- | --- | --- | --- | --- |
| 1 基本資料、2 規格與檢測、4 應用與配方、5 商務條件 | `company_fact` | E6 | 有填來源文件 → `verified`；沒有 → `partially_verified` | `business` |
| 3 研究資料：已發表（有 PMID／DOI） | `literature` | 依 `evidence-grading.md` 第 3 節判定 | 照一般文獻查證，用網路搜尋確認 PMID／DOI | 依 `claim-rules.md` |
| 3 研究資料：未發表的內部報告 | `literature` | 依研究類型判定（例如體外研究為 E5） | `partially_verified` | 依 `claim-rules.md`；`source.url` 填資料卡路徑與研究 ID |
| 6 已核准的對外用語 | 不另建證據 | — | — | 當作候選宣稱的參考，仍要照本次市場與品類重新審查 |

規則：

- 研究資料「可對外引用」不是「是」的，對應的宣稱一律 `internal_only`。
- 商務條件「可對外說明」不是「是」的，不放進對外稿。
- 資料卡的內容優先於 DM 上的同一項資料。兩者衝突時，列進內部稿的「需專業人員再確認」。
- 資料卡沒填的欄位，照一般缺口處理（Phase 2、Gate 4.5），不得從 DM 推測補上。
- evidence_record 的 `ingredient` 欄寫原料名稱，`limitations` 註明「來源：DISAM 原料資料卡，更新日期 YYYY-MM-DD」。

## 3. 範本

新原料的資料卡格式見 `templates/disam-ingredient-card.md`。
