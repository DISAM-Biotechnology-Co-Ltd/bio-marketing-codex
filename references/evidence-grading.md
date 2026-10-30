# 證據查證與 E0–E7 分級

Phase 3 必讀。本檔決定「哪些研究可以拿來說什麼話」。

## 1. 查證鐵律

- 不得憑記憶列出文獻。每一筆文獻都要用網路搜尋實際找到 PubMed、DOI 出版社頁、ClinicalTrials.gov 或官方機關頁面，取得可點開的 PMID、DOI 或 URL。
- 不得編造標題、期刊、年份、PMID、DOI、樣本數、劑量、p 值、終點或結論。查不到的欄位留空並標「未載明」。
- 查不到來源、或來源資訊對不起來 → 一律標 E7（未驗證），只能放內部稿。
- 與較強證據相矛盾的研究必須列出，不可隱藏。
- 優先順序：近五年 → 人體研究（統合分析、系統性回顧、RCT、對照試驗、世代研究）→ 動物／細胞只當機轉背景。用到較舊文獻時說明原因。

## 2. 搜尋順序

1. 產品名 + clinical trial / RCT / human study
2. 配方主成分組合 + human study
3. 單一成分 + 終點 + systematic review / meta-analysis / RCT
4. 成分 + 機轉關鍵字 + human biomarker / pharmacokinetics
5. 成分 + 路徑 + animal / cell / in vitro
6. 成分專論、官方營養素功能、法規來源
7. 供應商資料或品牌文宣（只當查證線索）

## 3. 分級表

| 等級 | 內部標籤 | 判定 | 對外可用的說法 | 不可說 |
|---|---|---|---|---|
| E0 | 成品直接證據 | 同一成品、相近劑量、相關族群的人體研究 | 產品研究背景：「在該研究條件下，受試產品觀察到…」 | 超出研究終點、劑量、族群的延伸 |
| E1 | 近似配方證據 | 相同或幾乎相同配方的人體研究 | 配方研究參考 | 說成「本產品已臨床證實」 |
| E2 | 相似複方證據 | 相似成分組合的人體研究 | 相似營養組合研究 | 把相似配方當成同一配方 |
| E3 | 單一成分人體證據 | 單一成分在人體的相關終點 | 成分研究支持此配方設計 | 暗示整個配方有同等效果 |
| E4 | 人體機轉／生物標記 | 吸收、代謝、生物標記、ex vivo | 機轉研究背景 | 保證消費者效益 |
| E5 | 基礎機轉證據 | 動物、細胞、體外、分子路徑 | 配方設計邏輯、機轉示意 | 任何人體功效說法 |
| E6 | 背景支持 | 傳統使用、專論、營養素功能、市場資料 | 原料故事、營養背景 | 當作功效證明 |
| E7 | 未驗證候選 | 供應商說法、行銷資料、查不到的引用 | 不可對外 | 寫成事實 |

快速判定：同一成品？→E0；同配方？→E1；相似組合人體？→E2；單一成分人體？→E3；人體機轉／標記？→E4；動物細胞體外？→E5；專論／傳統／市場？→E6；以上皆非或查不到 →E7 或排除。

## 4. 關聯性

- 直接：同產品或等同配方，族群、劑量、終點相關。
- 部分：同成分或相近路徑，但不是同一產品。
- 背景：只適合教育或定位，不支持宣稱。

## 5. 不得對外使用機轉證據的情況

- 來源無法查證；
- 被更強證據推翻；
- 研究模型與產品類別無關；
- 劑量不可能或與產品無關；
- 研究終點是疾病終點，而產品是食品、保健品或化粧品；
- 結論必須使用處方、醫療或疾病語言才能表達；
- 只有供應商資料，沒有可追溯文獻或官方文件。

## 6. evidence_record 欄位

每一筆要用在下游的證據都整理成以下格式（同時寫進 Phase 4 的 bundle.json）：

```json
{
  "id": "ev-1",
  "ingredient": "成分或配方",
  "evidence_tier": "E3",
  "evidence_kind": "literature | regulation | company_fact",
  "study": {"title": "", "year": 2023, "type": "RCT", "population": "", "sample_size": null, "dose": "", "duration": ""},
  "endpoint": "",
  "finding": "",
  "limitations": "",
  "relevance": "direct | partial | background",
  "source": {"pmid": "", "doi": "", "url": ""},
  "verification": {"status": "verified | partially_verified | unverified"},
  "safe_wording": [""],
  "forbidden_wording": [""]
}
```

`verification.status` 必須明確填寫。看起來合理不等於已查證。

### evidence_kind：非文獻依據

E0–E7 衡量的是研究強度。有些對外句子的依據不是研究，而是法規條文或公司資料，例如准用詞句「調整體質」、法定警語、產品規格。這類依據也要建成 evidence_record，用 `evidence_kind` 區分（未填視為 `literature`）：

| evidence_kind | 用途 | 等級 | 只能支撐的 claim_type | 查證要求 |
|---|---|---|---|---|
| `literature` | 文獻、研究 | E0–E7 依第 3 節判定 | 依 `claim-rules.md` 第 3 節 | 依第 1 節 |
| `regulation` | 法規條文、主管機關公告 | 一律 E6 | `permitted_phrase`、`label_warning` | `source.url` 必須是官方網址；`limitations` 寫查核日期與使用條件 |
| `company_fact` | PM 或公司提供的規格、商業條件 | 一律 E6 | `business` | 有規格書、COA 等書面文件才算 `verified`，只有口述就標 `partially_verified` |

- 法規與公司資料不能拿來支撐功效、成分角色或機轉宣稱，`check_claims.py` 會擋下。
- 被判為 prohibited 的宣稱，可以引用 regulation 證據作為判定理由。
- 範例：

```json
{
  "id": "ev-reg-1",
  "ingredient": "法規：一般食品准用詞句",
  "evidence_tier": "E6",
  "evidence_kind": "regulation",
  "study": {"title": "食品及相關產品標示宣傳廣告涉及不實誇張易生誤解或醫療效能認定準則 附件一", "year": null, "type": "官方法規", "population": "不適用", "sample_size": null, "dose": "不適用", "duration": "不適用"},
  "endpoint": "不適用",
  "finding": "附件一第六項「調整體質」為通常得使用之詞句",
  "limitations": "查核日期 2026-10-30；依第 3 條整體表現判斷，與疾病暗示並列仍違規",
  "relevance": "background",
  "source": {"pmid": "", "doi": "", "url": "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=L0040140"},
  "verification": {"status": "verified"},
  "safe_wording": ["調整體質"],
  "forbidden_wording": []
}
```

## 7. 對外轉譯用語

| 內部說法 | 對外說法 |
|---|---|
| 證據不足 | 成分研究背景 |
| 無成品證據 | 配方設計邏輯 |
| 只有細胞實驗 | 基礎研究支持此路徑的生物合理性 |
| 單一成分人體研究 | 此成分的人體研究支持其在配方中的角色 |
