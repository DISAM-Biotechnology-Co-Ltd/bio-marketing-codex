#!/usr/bin/env python3
"""對外文案宣稱合規檢查（確定性規則，只用 Python 標準函式庫）。

用法：
    python3 check_claims.py bundle.json

bundle 格式：
    {
      "evidence_records": [{"id", "evidence_tier", "evidence_kind"（選填）, "verification": {"status"}, "source": {...}}],
      "claim_records": [{"id", "claim_text", "claim_type", "status", "approved_wording", "evidence_refs"}],
      "external_text": "對外稿全文"  或  "external_files": ["相對於 bundle 的路徑.md", ...],
      "speaker_deck": true/false,  （選填，目前不影響判定）
      "products": [{"id", "name"}, ...]   （選填，系列模式）
    }

系列模式（bundle 有 products 時才啟用；沒有 products 時判定與單一產品完全相同）：
    - products 為非空陣列，id 不可重複、不可用保留字 "series"
    - 每筆 evidence_record 必須有 "products": [產品 id, ...]（非空，皆須列在 products 中）
    - 每筆 claim_record 必須有 "product": 產品 id 或 "series"
    - 單一產品的宣稱只能引用涵蓋該產品的證據；series 宣稱除 business、label_warning 外，
      引用證據合起來須涵蓋所有產品

對外檔案中 <!-- check:ignore-start --> 與 <!-- check:ignore-end --> 之間的文字
不掃描違規詞、癌症治療語境與內部註記；被否決原句外流仍掃全文。
.html／.htm 對外檔的 <style> 區塊與 style 屬性不掃描（CSS 不是文案）；<script> 照常掃描。

輸出：stdout 印 JSON
    {"status": "pass|fail", "violations": [{"code","path","message"}], "warnings": [...]}
輸入錯誤時印 {"status": "error", "errors": [...], "violations": [], "warnings": []}。

結束碼：0 通過、1 有違規、2 輸入錯誤。

規則改寫自 bio-marketing-prompt-generator 2.0.0 的 validators/policy.py。
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# 可維護常數
# ---------------------------------------------------------------------------

# 台灣食品／保健品／化粧品對外稿常見違規詞（對應 references/claim-rules.md 第 6 節）。
# 新增或刪除詞彙時直接改這裡；比對時不分大小寫。
TAIWAN_PROHIBITED_TERMS = (
    # 疾病與醫療
    "治療",
    "治癒",
    "根治",
    "預防疾病",
    "消炎",
    "抗發炎",
    "抗癌",
    "防癌",
    "抑制腫瘤",
    "降血壓",
    "降血糖",
    "降血脂",
    "藥效",
    "處方",
    "療程",
    # 體態誇大
    "減肥",
    "瘦身",
    "燃脂",
    "消脂",
    "溶脂",
    "窈窕",
    # 保證效果
    "保證",
    "100%",
    "永久",
    "立即見效",
    "根除",
)

# 法定或常見的免責聲明句。掃描違規詞前會先把這些句子從對外稿中移除，
# 避免「本產品非藥品，不具治療效果」這類必要聲明被誤判。
DISCLAIMER_ALLOWLIST = (
    "不具治療效果",
    "不具醫療效能",
    "不能取代正規治療",
    "無法取代正規治療",
    "不可取代藥物治療",
)

VALID_TIERS = ("E0", "E1", "E2", "E3", "E4", "E5", "E6", "E7")
VALID_STATUSES = ("allowed", "rewrite_required", "prohibited", "internal_only")

# 證據來源種類（evidence_kind，選填，預設 literature）。法規條文與公司資料不是研究，
# 一律標 E6，且只能支撐下表列出的 claim_type，避免借法規或規格偷渡功效說法。
VALID_EVIDENCE_KINDS = ("literature", "regulation", "company_fact")
NON_LITERATURE_TIER = "E6"
NON_LITERATURE_CLAIM_TYPES = {
    "regulation": {"permitted_phrase", "label_warning"},
    "company_fact": {"business"},
}
# 這兩種宣稱的依據就是法規本身，allowed 時至少要引用一筆 regulation 證據。
REGULATION_BACKED_CLAIM_TYPES = {"permitted_phrase", "label_warning"}

# 以下四組正規表示式沿用原版 policy.py 第 12–37 行。
HUMAN_EFFICACY_CLAIM_TYPES = {
    "human_efficacy",
    "clinical_efficacy",
    "disease_treatment",
    "disease_prevention",
}
HUMAN_EFFICACY_RE = re.compile(
    r"(?:\b(?:treat|cure|prevent|improv\w*|reduc\w*|boost\w*)\b.{0,60}"
    r"\b(?:human|patient|people|adult|child|symptom|disease|outcome|function|immunity)\b)"
    r"|(?:\b(?:human|patient|people|adult|child)\b.{0,60}"
    r"\b(?:efficacy|benefit|treat|cure|prevent|improv\w*|reduc\w*|boost\w*)\b)"
    r"|(?:人體|患者|病患|成人|兒童).{0,24}(?:療效|改善|提升|降低|治療|預防)"
    r"|(?:改善|提升|增強|促進|降低|治療|預防).{0,24}(?:人體|患者|病患|症狀|疾病|免疫功能|免疫力)",
    re.IGNORECASE,
)
ONCOLOGY_RE = re.compile(r"\b(?:cancer|oncolog\w*|tumou?r|neoplasm)\b|癌|腫瘤", re.IGNORECASE)
THERAPEUTIC_RE = re.compile(
    r"\b(?:treat\w*|cure\w*|prevent\w*|shrink\w*|reduc\w*|fight\w*|combat\w*|"
    r"suppress\w*|inhibit\w*|anti[- ]?(?:cancer|tumou?r)|eradicate\w*)\b"
    r"|治療|治癒|預防|抗癌|縮小|降低|消滅|抑制腫瘤",
    re.IGNORECASE,
)
INTERNAL_MARKER_RE = re.compile(
    r"\binternal[\s_-]*only\b|\bdo not distribute\b|\bdata gap\b|\bregulatory risk\b|"
    r"\bprohibited claim\b|\bunresolved\b|內部|不得對外|待補|法規風險|禁用",
    re.IGNORECASE,
)

# 系列模式：claim_record.product 用這個值代表「整個系列」，不得當作產品 id。
SERIES_PRODUCT = "series"

# series 宣稱中不需各產品證據涵蓋的 claim_type（公司／平台事實與法定警語）；
# 其餘類型（含 structure_function 等功能性說法）都視為功效，必須每款都有證據。
SERIES_EXEMPT_CLAIM_TYPES = {"business", "label_warning"}

# 佔位符開頭，例如「［待補：單劑成本］」；出現時只列警告。
PLACEHOLDER_PREFIXES = ("［", "[")

# 對外檔案中這對標記之間的文字（如提示詞裡的禁用詞清單、操作說明）
# 不掃描違規詞、癌症治療語境與內部註記；被否決原句外流仍掃全文。
IGNORE_START = "<!-- check:ignore-start -->"
IGNORE_END = "<!-- check:ignore-end -->"
_IGNORE_BLOCK_RE = re.compile(re.escape(IGNORE_START) + r".*?" + re.escape(IGNORE_END), re.DOTALL)

# HTML 對外檔的樣式不是文案（例如 `width: 100%`），掃描前遮掉 <style> 區塊與 style 屬性。
# <script> 不遮：互動頁的文案常寫在 JS 字串裡，仍要掃描。
HTML_SUFFIXES = (".html", ".htm")
_HTML_STYLE_RE = re.compile(
    r"<style\b[^>]*>.*?</style\s*>|\sstyle\s*=\s*(?:\"[^\"]*\"|'[^']*')",
    re.DOTALL | re.IGNORECASE,
)

# 用來切句子以判斷「癌症＋治療」是否出現在同一句。
SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？!?；;])|\n|(?<=\.)\s+")

_PROHIBITED_TERMS_RE = re.compile(
    "|".join(re.escape(term) for term in sorted(TAIWAN_PROHIBITED_TERMS, key=len, reverse=True)),
    re.IGNORECASE,
)
# 比對原句外流時忽略的字元：空白與常見 Markdown 符號。
_NORMALIZE_STRIP_RE = re.compile(r"[\s*_`>#~|]+")


class InputError(Exception):
    """輸入檔案或格式錯誤，結束碼 2。"""


# ---------------------------------------------------------------------------
# 工具函式
# ---------------------------------------------------------------------------

def _issue(code: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "path": path, "message": message}


def _tier_rank(tier: str) -> int:
    """E0 最強、E7 最弱；回傳數字，越小越強。"""
    return VALID_TIERS.index(tier)


def _normalize(text: str) -> str:
    """原句比對用：全形半形統一、去空白與 Markdown 符號、去句尾標點、轉小寫。"""
    text = unicodedata.normalize("NFKC", text)
    text = _NORMALIZE_STRIP_RE.sub("", text)
    return text.strip("。.！!？?；;，,").lower()


def _line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def _snippet(text: str, start: int, end: int, margin: int = 12) -> str:
    left = max(0, start - margin)
    right = min(len(text), end + margin)
    return text[left:right].replace("\n", " ").strip()


def _mask_disclaimers(text: str) -> str:
    """把免責聲明換成等長空白，保留字元位置以便回報行號。"""
    for phrase in DISCLAIMER_ALLOWLIST:
        text = text.replace(phrase, " " * len(phrase))
    return text


def _human_efficacy(claim: dict[str, Any]) -> bool:
    if claim.get("claim_type") in HUMAN_EFFICACY_CLAIM_TYPES:
        return True
    return any(
        isinstance(text, str) and HUMAN_EFFICACY_RE.search(text)
        for text in (claim.get("claim_text"), claim.get("approved_wording"))
    )


# ---------------------------------------------------------------------------
# 讀取與格式檢查
# ---------------------------------------------------------------------------

def _require(condition: bool, errors: list[dict[str, str]], path: str, message: str) -> None:
    if not condition:
        errors.append(_issue("INPUT_INVALID", path, message))


def validate_input(bundle: object) -> list[dict[str, str]]:
    """檢查 bundle 必要欄位與型別；回傳錯誤清單（空清單代表格式正確）。"""
    errors: list[dict[str, str]] = []
    if not isinstance(bundle, dict):
        return [_issue("INPUT_INVALID", "$", "bundle 必須是 JSON 物件")]

    for field in ("evidence_records", "claim_records"):
        _require(isinstance(bundle.get(field), list), errors, field, f"缺少 {field} 或不是陣列")

    has_text = "external_text" in bundle
    has_files = "external_files" in bundle
    _require(has_text or has_files, errors, "$", "必須提供 external_text 或 external_files 其中之一")
    _require(not (has_text and has_files), errors, "$", "external_text 與 external_files 只能擇一")
    if has_text:
        _require(isinstance(bundle["external_text"], str), errors, "external_text", "external_text 必須是字串")
    if has_files:
        files = bundle["external_files"]
        _require(
            isinstance(files, list) and bool(files) and all(isinstance(f, str) and f for f in files),
            errors,
            "external_files",
            "external_files 必須是非空的路徑字串陣列",
        )
    if "speaker_deck" in bundle:
        _require(isinstance(bundle["speaker_deck"], bool), errors, "speaker_deck", "speaker_deck 必須是 true 或 false")

    series_mode = "products" in bundle
    product_ids = _validate_products(bundle["products"], errors) if series_mode else set()

    for position, record in enumerate(bundle.get("evidence_records") or []):
        path = f"evidence_records[{position}]"
        if not isinstance(record, dict):
            errors.append(_issue("INPUT_INVALID", path, "evidence_record 必須是 JSON 物件"))
            continue
        _require(isinstance(record.get("id"), str) and bool(record.get("id")), errors, f"{path}.id", "缺少 id")
        _require(
            record.get("evidence_tier") in VALID_TIERS,
            errors,
            f"{path}.evidence_tier",
            f"evidence_tier 必須是 {'、'.join(VALID_TIERS)} 之一",
        )
        kind = record.get("evidence_kind", "literature")
        _require(
            kind in VALID_EVIDENCE_KINDS,
            errors,
            f"{path}.evidence_kind",
            f"evidence_kind 必須是 {'、'.join(VALID_EVIDENCE_KINDS)} 之一",
        )
        _require(
            kind == "literature" or record.get("evidence_tier") == NON_LITERATURE_TIER,
            errors,
            f"{path}.evidence_tier",
            f"evidence_kind 為 {kind} 時，evidence_tier 必須是 {NON_LITERATURE_TIER}",
        )
        if series_mode:
            products = record.get("products")
            _require(
                isinstance(products, list)
                and bool(products)
                and all(isinstance(item, str) and item in product_ids for item in products),
                errors,
                f"{path}.products",
                "系列模式下 products 必須是非空陣列，且每個值都是 products 中的產品 id",
            )

    for position, record in enumerate(bundle.get("claim_records") or []):
        path = f"claim_records[{position}]"
        if not isinstance(record, dict):
            errors.append(_issue("INPUT_INVALID", path, "claim_record 必須是 JSON 物件"))
            continue
        _require(isinstance(record.get("id"), str) and bool(record.get("id")), errors, f"{path}.id", "缺少 id")
        _require(
            isinstance(record.get("claim_text"), str) and bool(record.get("claim_text").strip()),
            errors,
            f"{path}.claim_text",
            "缺少 claim_text",
        )
        _require(
            record.get("status") in VALID_STATUSES,
            errors,
            f"{path}.status",
            f"status 必須是 {'、'.join(VALID_STATUSES)} 之一",
        )
        refs = record.get("evidence_refs", [])
        _require(
            isinstance(refs, list) and all(isinstance(ref, str) for ref in refs),
            errors,
            f"{path}.evidence_refs",
            "evidence_refs 必須是字串陣列",
        )
        wording = record.get("approved_wording")
        _require(
            wording is None or isinstance(wording, str),
            errors,
            f"{path}.approved_wording",
            "approved_wording 必須是字串或 null",
        )
        declared = record.get("highest_evidence_tier")
        _require(
            declared is None or declared in VALID_TIERS,
            errors,
            f"{path}.highest_evidence_tier",
            f"highest_evidence_tier 必須是 {'、'.join(VALID_TIERS)} 之一",
        )
        if series_mode:
            product = record.get("product")
            _require(
                isinstance(product, str) and (product in product_ids or product == SERIES_PRODUCT),
                errors,
                f"{path}.product",
                f"系列模式下 product 必須是 products 中的產品 id 或 {SERIES_PRODUCT}",
            )
    return errors


def _validate_products(products: object, errors: list[dict[str, str]]) -> set[str]:
    """檢查系列模式的 products 陣列；回傳格式正確的產品 id 集合。"""
    if not (isinstance(products, list) and products):
        errors.append(_issue("INPUT_INVALID", "products", "products 必須是非空陣列"))
        return set()
    product_ids: set[str] = set()
    for position, product in enumerate(products):
        path = f"products[{position}]"
        if not isinstance(product, dict):
            errors.append(_issue("INPUT_INVALID", path, "product 必須是 JSON 物件"))
            continue
        product_id = product.get("id")
        if not (isinstance(product_id, str) and product_id):
            errors.append(_issue("INPUT_INVALID", f"{path}.id", "缺少 id"))
        elif product_id == SERIES_PRODUCT:
            errors.append(_issue("INPUT_INVALID", f"{path}.id", f"{SERIES_PRODUCT} 是保留字，不能當產品 id"))
        elif product_id in product_ids:
            errors.append(_issue("INPUT_INVALID", f"{path}.id", f"產品 id 重複：{product_id}"))
        else:
            product_ids.add(product_id)
        name = product.get("name")
        _require(isinstance(name, str) and bool(name.strip()), errors, f"{path}.name", "缺少 name")
    return product_ids


def _mask_html_styles(text: str) -> str:
    """把 HTML 的 <style> 區塊與 style 屬性換成空白（保留換行，行號不變）。"""
    return _HTML_STYLE_RE.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)


def load_external_texts(bundle: dict[str, Any], base_dir: Path) -> list[tuple[str, str]]:
    """回傳 [(路徑標籤, 全文), ...]；檔案讀不到時丟 InputError。"""
    if "external_text" in bundle:
        return [("external_text", bundle["external_text"])]
    texts: list[tuple[str, str]] = []
    for position, relative in enumerate(bundle["external_files"]):
        file_path = (base_dir / relative).resolve()
        try:
            text = file_path.read_text(encoding="utf-8")
            if file_path.suffix.lower() in HTML_SUFFIXES:
                text = _mask_html_styles(text)
            texts.append((f"external_files[{position}]", text))
        except FileNotFoundError:
            raise InputError(f"external_files[{position}] 找不到檔案：{relative}") from None
        except (OSError, UnicodeDecodeError) as exc:
            raise InputError(f"external_files[{position}] 無法以 UTF-8 讀取：{relative}（{exc}）") from None
    return texts


# ---------------------------------------------------------------------------
# 規則
# ---------------------------------------------------------------------------

def _index(records: list[dict[str, Any]], kind: str, violations: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for position, record in enumerate(records):
        record_id = record["id"]
        if record_id in index:
            violations.append(
                _issue(f"DUPLICATE_{kind.upper()}_ID", f"{kind}_records[{position}].id", f"{kind} id 重複：{record_id}")
            )
        else:
            index[record_id] = record
    return index


def check_claim_records(
    claims: list[dict[str, Any]],
    evidence_by_id: dict[str, dict[str, Any]],
    violations: list[dict[str, str]],
    warnings: list[dict[str, str]],
    product_ids: list[str] | None = None,
) -> dict[str, str | None]:
    """規則 1–4：引用一致性、E7、E5 人體功效、核准用字。回傳每個 claim id 的最高證據層級。

    product_ids 不為 None 時（系列模式），另外檢查證據與產品是否對應。
    """
    best_tiers: dict[str, str | None] = {}
    for position, claim in enumerate(claims):
        path = f"claim_records[{position}]"
        status = claim["status"]
        allowed = status == "allowed"

        linked: list[dict[str, Any]] = []
        for ref_position, ref in enumerate(claim.get("evidence_refs", [])):
            evidence = evidence_by_id.get(ref)
            if evidence is None:
                violations.append(
                    _issue("UNKNOWN_EVIDENCE_REF", f"{path}.evidence_refs[{ref_position}]", f"引用的證據不存在：{ref}")
                )
            else:
                linked.append(evidence)

        if linked:
            best = min((item["evidence_tier"] for item in linked), key=_tier_rank)
            declared = claim.get("highest_evidence_tier")
            if declared and _tier_rank(declared) < _tier_rank(best):
                warnings.append(
                    _issue(
                        "DECLARED_TIER_OVERSTATED",
                        f"{path}.highest_evidence_tier",
                        f"宣告的最高證據層級 {declared} 比實際引用證據的 {best} 更強，以 {best} 判定",
                    )
                )
        else:
            best = claim.get("highest_evidence_tier")
            if allowed and not claim.get("evidence_refs"):
                violations.append(
                    _issue("ALLOWED_CLAIM_WITHOUT_EVIDENCE", f"{path}.evidence_refs", "allowed 的宣稱必須引用至少一筆證據")
                )
        best_tiers[claim["id"]] = best

        # 規則 2：最高證據為 E7 只能 internal_only。
        if allowed and best == "E7":
            violations.append(
                _issue("E7_CLAIM_ALLOWED", f"{path}.status", "最高證據層級為 E7 的宣稱只能是 internal_only，不得 allowed")
            )
        elif allowed and any(item["evidence_tier"] == "E7" for item in linked):
            warnings.append(
                _issue("E7_EVIDENCE_CITED", f"{path}.evidence_refs", "allowed 的宣稱同時引用了 E7 未驗證證據，對外稿不得引用該來源")
            )

        # 規則 1b：法規與公司資料只能支撐對應的 claim_type；法規證據要有官方網址。
        if status in ("allowed", "rewrite_required"):
            claim_type = claim.get("claim_type")
            for item in linked:
                kind = item.get("evidence_kind", "literature")
                if kind == "literature":
                    continue
                if claim_type not in NON_LITERATURE_CLAIM_TYPES[kind]:
                    violations.append(
                        _issue(
                            "NON_LITERATURE_EVIDENCE_MISUSE",
                            f"{path}.evidence_refs",
                            f"{item['id']} 是 {kind}，只能支撐 "
                            f"{'、'.join(sorted(NON_LITERATURE_CLAIM_TYPES[kind]))}，不能支撐 {claim_type}",
                        )
                    )
                source = item.get("source")
                if kind == "regulation" and not (isinstance(source, dict) and source.get("url")):
                    violations.append(
                        _issue("REGULATION_WITHOUT_URL", f"{path}.evidence_refs", f"{item['id']} 是法規證據，必須附官方網址")
                    )
        # 系列模式：A 產品的證據不能支撐 B 產品；series 的功效宣稱要涵蓋所有產品。
        if product_ids is not None and status in ("allowed", "rewrite_required"):
            product = claim["product"]
            if product == SERIES_PRODUCT:
                covered = {covered_id for item in linked for covered_id in item["products"]}
                missing = [product_id for product_id in product_ids if product_id not in covered]
                if missing and claim.get("claim_type") not in SERIES_EXEMPT_CLAIM_TYPES:
                    violations.append(
                        _issue(
                            "SERIES_CLAIM_EVIDENCE_GAP",
                            f"{path}.evidence_refs",
                            f"series 的功效宣稱，引用證據未涵蓋產品：{'、'.join(missing)}；"
                            "請補齊各產品的證據，或改成單一產品宣稱",
                        )
                    )
            else:
                for item in linked:
                    if product not in item["products"]:
                        violations.append(
                            _issue(
                                "PRODUCT_EVIDENCE_MISMATCH",
                                f"{path}.evidence_refs",
                                f"{item['id']} 的證據對象是 {'、'.join(item['products'])}，不能支撐產品 {product} 的宣稱",
                            )
                        )

        if (
            allowed
            and claim.get("claim_type") in REGULATION_BACKED_CLAIM_TYPES
            and not any(item.get("evidence_kind") == "regulation" for item in linked)
        ):
            violations.append(
                _issue(
                    "REGULATION_BACKED_CLAIM_WITHOUT_REGULATION",
                    f"{path}.evidence_refs",
                    f"{claim.get('claim_type')} 必須引用至少一筆 evidence_kind 為 regulation 的證據",
                )
            )

        # 規則 3：只有 E5 以下證據不可核准人體功效。
        if allowed and best is not None and _tier_rank(best) >= _tier_rank("E5") and _human_efficacy(claim):
            violations.append(
                _issue(
                    "E5_HUMAN_EFFICACY",
                    f"{path}.status",
                    f"最高證據僅 {best}（動物／細胞／背景或未驗證），不得核准人體功效宣稱",
                )
            )

        # 沿用原版：癌症＋治療語境的宣稱不得 allowed。
        claim_words = " ".join(
            text for text in (claim.get("claim_text"), claim.get("approved_wording")) if isinstance(text, str)
        )
        if allowed and ONCOLOGY_RE.search(claim_words) and THERAPEUTIC_RE.search(claim_words):
            violations.append(
                _issue("ONCOLOGY_CLAIM_ALLOWED", f"{path}.status", "癌症治療、預防或縮小腫瘤的宣稱不得 allowed")
            )

        # 規則 4：allowed 必須有核准用字。
        wording = claim.get("approved_wording")
        if allowed and not (isinstance(wording, str) and wording.strip()):
            violations.append(
                _issue("ALLOWED_WITHOUT_APPROVED_WORDING", f"{path}.approved_wording", "allowed 的宣稱必須填寫 approved_wording")
            )

        if allowed:
            for item in linked:
                verification = item.get("verification")
                verified = isinstance(verification, dict) and verification.get("status") == "verified"
                if not verified:
                    warnings.append(
                        _issue(
                            "UNVERIFIED_EVIDENCE",
                            f"{path}.evidence_refs",
                            f"allowed 的宣稱引用了尚未查證的證據：{item['id']}",
                        )
                    )
    return best_tiers


def _mask_ignored_blocks(label: str, text: str, warnings: list[dict[str, str]]) -> str:
    """把 check:ignore 區塊內的字換成空白（保留換行，行號不變）。

    區塊只開不關時不略過任何內容，並列警告。
    """
    if IGNORE_START not in text and IGNORE_END not in text:
        return text
    starts = text.count(IGNORE_START)
    ends = text.count(IGNORE_END)
    if starts != ends:
        warnings.append(
            _issue(
                "UNBALANCED_IGNORE_BLOCK",
                label,
                f"{IGNORE_START} 與 {IGNORE_END} 數量不符（{starts}／{ends}），本檔不略過任何內容",
            )
        )
        return text
    return _IGNORE_BLOCK_RE.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)


def check_external_text(
    label: str,
    text: str,
    violations: list[dict[str, str]],
    warnings: list[dict[str, str]],
) -> None:
    """規則 5、7：癌症治療語境、內部註記、台灣常見違規詞。check:ignore 區塊內不掃描。"""
    text = _mask_ignored_blocks(label, text, warnings)

    # 規則 5a：癌症與治療用語出現在同一句 → 違規；只提到癌症 → 警告，需人工確認。
    offset = 0
    for sentence in SENTENCE_SPLIT_RE.split(text):
        start = text.find(sentence, offset) if sentence else offset
        offset = start + len(sentence)
        oncology = ONCOLOGY_RE.search(sentence)
        if not oncology:
            continue
        where = f"{label}:{_line_of(text, start + oncology.start())}"
        therapeutic = THERAPEUTIC_RE.search(sentence)
        if therapeutic:
            violations.append(
                _issue(
                    "EXTERNAL_ONCOLOGY_THERAPEUTIC",
                    where,
                    f"對外稿出現癌症治療語境（「{oncology.group(0)}」＋「{therapeutic.group(0)}」）：{sentence.strip()}",
                )
            )
        else:
            warnings.append(
                _issue(
                    "EXTERNAL_ONCOLOGY_MENTION",
                    where,
                    f"對外稿提到癌症／腫瘤（「{oncology.group(0)}」），請人工確認沒有暗示療效：{sentence.strip()}",
                )
            )

    # 規則 5b、7：逐行掃描（先做全形半形統一，行號才準確）。
    for line_no, raw_line in enumerate(text.split("\n"), start=1):
        line = unicodedata.normalize("NFKC", raw_line)
        where = f"{label}:{line_no}"

        # 規則 5b：內部註記外流；「［待補…」佔位符只列警告。
        for match in INTERNAL_MARKER_RE.finditer(line):
            is_placeholder = match.group(0) == "待補" and match.start() > 0 and line[match.start() - 1] in PLACEHOLDER_PREFIXES
            if is_placeholder:
                warnings.append(
                    _issue("PLACEHOLDER_PENDING", where, f"對外稿仍有待補佔位符：{_snippet(line, match.start() - 1, match.end())}")
                )
                continue
            violations.append(
                _issue(
                    "EXTERNAL_INTERNAL_MARKER",
                    where,
                    f"對外稿出現內部註記「{match.group(0)}」：{_snippet(line, match.start(), match.end())}",
                )
            )

        # 規則 7：台灣常見違規詞（先遮掉免責聲明）。
        for match in _PROHIBITED_TERMS_RE.finditer(_mask_disclaimers(line)):
            violations.append(
                _issue(
                    "TW_PROHIBITED_TERM",
                    where,
                    f"對外稿出現台灣法規高風險用語「{match.group(0)}」：{_snippet(line, match.start(), match.end())}",
                )
            )


def _first_leak(needle: str, normalized_texts: list[tuple[str, str]]) -> str | None:
    """回傳第一個含有 needle 的對外稿標籤；都沒有則回傳 None。"""
    for label, haystack in normalized_texts:
        if needle and needle in haystack:
            return label
    return None


def check_rejected_wording(
    claims: list[dict[str, Any]],
    best_tiers: dict[str, str | None],
    texts: list[tuple[str, str]],
    violations: list[dict[str, str]],
) -> None:
    """規則 6：被否決或僅限內部的原句不得出現在對外稿（含 check:ignore 區塊）。"""
    normalized_texts = [(label, _normalize(text)) for label, text in texts]
    # 遮掉 ignore 區塊後的版本，只用來判斷外流位置，給出修正方向。
    outside_ignore = {label: _normalize(_mask_ignored_blocks(label, text, [])) for label, text in texts}
    for position, claim in enumerate(claims):
        status = claim["status"]
        path = f"claim_records[{position}].claim_text"
        e7 = best_tiers.get(claim["id"]) == "E7"
        if status == "allowed" and not e7:
            continue

        candidates = [claim["claim_text"]]
        wording = claim.get("approved_wording")
        if status == "internal_only" or e7:
            # 僅限內部或 E7 的宣稱，連核准用字都不得對外。
            if isinstance(wording, str) and wording.strip():
                candidates.append(wording)
        elif status == "rewrite_required" and isinstance(wording, str):
            # 改寫版本身包含原句時無法區分，略過以免誤判。
            if _normalize(claim["claim_text"]) in _normalize(wording):
                continue

        if e7:
            code, reason = "EXTERNAL_E7_LEAK", "最高證據為 E7 的宣稱"
        elif status == "internal_only":
            code, reason = "INTERNAL_CLAIM_LEAK", "internal_only 的宣稱"
        else:
            code, reason = "REJECTED_CLAIM_LEAK", f"狀態為 {status} 的原句"
        for candidate in candidates:
            needle = _normalize(candidate)
            label = _first_leak(needle, normalized_texts)
            if label is not None:
                message = f"{label} 出現{reason}（{claim['id']}）：{candidate.strip()}"
                if needle not in outside_ignore[label]:
                    message += "。此句只出現在 check:ignore 區塊內：禁止清單請改寫成類別描述（例如「疾病相關功效說法」），不要逐字寫出被否決的原句"
                violations.append(_issue(code, path, message))
                break


# ---------------------------------------------------------------------------
# 進入點
# ---------------------------------------------------------------------------

def check_bundle(bundle: dict[str, Any], base_dir: Path) -> dict[str, Any]:
    """檢查已通過格式驗證的 bundle；外部檔案讀取失敗時丟 InputError。"""
    texts = load_external_texts(bundle, base_dir)
    violations: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    evidence_by_id = _index(bundle["evidence_records"], "evidence", violations)
    _index(bundle["claim_records"], "claim", violations)
    product_ids = [product["id"] for product in bundle["products"]] if "products" in bundle else None
    best_tiers = check_claim_records(bundle["claim_records"], evidence_by_id, violations, warnings, product_ids)
    for label, text in texts:
        check_external_text(label, text, violations, warnings)
    check_rejected_wording(bundle["claim_records"], best_tiers, texts, violations)

    return {"status": "fail" if violations else "pass", "violations": violations, "warnings": warnings}


def _error_result(errors: list[dict[str, str]]) -> dict[str, Any]:
    return {"status": "error", "errors": errors, "violations": [], "warnings": []}


def run(argv: list[str]) -> tuple[int, dict[str, Any]]:
    if len(argv) != 1:
        return 2, _error_result([_issue("INPUT_USAGE", "$", "用法：python3 check_claims.py <bundle.json>")])
    bundle_path = Path(argv[0])
    try:
        raw = bundle_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return 2, _error_result([_issue("INPUT_NOT_FOUND", str(bundle_path), "找不到 bundle 檔案")])
    except (OSError, UnicodeDecodeError) as exc:
        return 2, _error_result([_issue("INPUT_UNREADABLE", str(bundle_path), f"無法以 UTF-8 讀取：{exc}")])
    try:
        bundle = json.loads(raw)
    except json.JSONDecodeError as exc:
        return 2, _error_result(
            [_issue("INPUT_BAD_JSON", str(bundle_path), f"JSON 格式錯誤（第 {exc.lineno} 行第 {exc.colno} 欄）：{exc.msg}")]
        )

    errors = validate_input(bundle)
    if errors:
        return 2, _error_result(errors)
    try:
        result = check_bundle(bundle, bundle_path.resolve().parent)
    except InputError as exc:
        return 2, _error_result([_issue("INPUT_NOT_FOUND", "external_files", str(exc))])
    return (1 if result["violations"] else 0), result


def main() -> int:
    code, result = run(sys.argv[1:])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
