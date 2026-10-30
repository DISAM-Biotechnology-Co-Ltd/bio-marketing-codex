#!/usr/bin/env python3
"""check_claims.py 的單元測試。執行：python3 scripts/test_check_claims.py"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import check_claims  # noqa: E402


def make_bundle(**overrides) -> dict:
    """可通過的基本 bundle；各測試再改成違規情境。"""
    bundle = {
        "evidence_records": [
            {"id": "ev-1", "evidence_tier": "E3", "verification": {"status": "verified"}, "source": {"pmid": "12345678"}}
        ],
        "claim_records": [
            {
                "id": "cl-1",
                "claim_text": "幫助維持日常活力",
                "claim_type": "structure_function",
                "status": "allowed",
                "approved_wording": "幫助維持日常活力",
                "evidence_refs": ["ev-1"],
            }
        ],
        "external_text": "靈芝萃取，幫助維持日常活力。",
        "speaker_deck": False,
    }
    bundle.update(overrides)
    return bundle


def run_bundle(bundle: dict) -> tuple[int, dict]:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "bundle.json"
        path.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
        return check_claims.run([str(path)])


def codes(result: dict, key: str = "violations") -> set[str]:
    return {item["code"] for item in result[key]}


# ---------------------------------------------------------------------------
# 原版 tests/fixtures/policy/ 的四個案例，轉成新格式
# （對外稿 = 原 commercial_brief.external.items 的 text 串接）
# ---------------------------------------------------------------------------

LEGACY_FIXTURES = {
    "e5-human-efficacy": {
        "evidence_records": [
            {
                "id": "ev-preclinical-1",
                "evidence_tier": "E5",
                "verification": {"status": "verified"},
                "source": {"URL": "https://example.test/cell-study"},
            }
        ],
        "claim_records": [
            {
                "id": "claim-e5-1",
                "claim_text": "IMMIO improves human immune function.",
                "claim_type": "human_efficacy",
                "highest_evidence_tier": "E5",
                "status": "allowed",
                "approved_wording": "IMMIO improves human immune function.",
                "evidence_refs": ["ev-preclinical-1"],
            }
        ],
        "external_text": "IMMIO improves human immune function.",
        "speaker_deck": False,
    },
    "e7-external-leak": {
        "evidence_records": [
            {
                "id": "ev-lead-1",
                "evidence_tier": "E7",
                "verification": {"status": "unverified"},
                "source": {"URL": "https://example.test/supplier-lead"},
            }
        ],
        "claim_records": [
            {
                "id": "claim-lead-1",
                "claim_text": "Supplier reports promising research.",
                "claim_type": "research_lead",
                "highest_evidence_tier": "E7",
                "status": "internal_only",
                "approved_wording": None,
                "evidence_refs": ["ev-lead-1"],
            }
        ],
        "external_text": "Supplier reports promising research.",
        "speaker_deck": False,
    },
    "oncology-claim": {
        "evidence_records": [
            {
                "id": "ev-oncology-1",
                "evidence_tier": "E0",
                "verification": {"status": "verified"},
                "source": {"URL": "https://example.test/oncology-study"},
            }
        ],
        "claim_records": [
            {
                "id": "claim-oncology-1",
                "claim_text": "PCPP treats cancer and shrinks tumors.",
                "claim_type": "disease_treatment",
                "highest_evidence_tier": "E0",
                "status": "allowed",
                "approved_wording": "PCPP treats cancer and shrinks tumors.",
                "evidence_refs": ["ev-oncology-1"],
            }
        ],
        "external_text": "PCPP treats cancer and shrinks tumors.",
        "speaker_deck": False,
    },
    "valid-bundle": {
        "evidence_records": [
            {
                "id": "ev-human-1",
                "evidence_tier": "E3",
                "verification": {"status": "verified"},
                "source": {"URL": "https://example.test/study"},
            }
        ],
        "claim_records": [
            {
                "id": "claim-wellness-1",
                "claim_text": "Supports daily wellness.",
                "claim_type": "structure_function",
                "highest_evidence_tier": "E3",
                "status": "allowed",
                "approved_wording": "Supports daily wellness.",
                "evidence_refs": ["ev-human-1"],
            }
        ],
        "external_text": "Supports daily wellness.",
        "speaker_deck": False,
    },
}


class LegacyFixtureTests(unittest.TestCase):
    """判定結果須與原版 policy.py 一致：前三個失敗、valid-bundle 通過。"""

    def test_e5_human_efficacy_fails(self):
        exit_code, result = run_bundle(LEGACY_FIXTURES["e5-human-efficacy"])
        self.assertEqual(exit_code, 1)
        self.assertIn("E5_HUMAN_EFFICACY", codes(result))

    def test_e7_external_leak_fails(self):
        exit_code, result = run_bundle(LEGACY_FIXTURES["e7-external-leak"])
        self.assertEqual(exit_code, 1)
        self.assertIn("EXTERNAL_E7_LEAK", codes(result))

    def test_oncology_claim_fails(self):
        exit_code, result = run_bundle(LEGACY_FIXTURES["oncology-claim"])
        self.assertEqual(exit_code, 1)
        self.assertIn("ONCOLOGY_CLAIM_ALLOWED", codes(result))
        self.assertIn("EXTERNAL_ONCOLOGY_THERAPEUTIC", codes(result))

    def test_valid_bundle_passes(self):
        exit_code, result = run_bundle(LEGACY_FIXTURES["valid-bundle"])
        self.assertEqual(exit_code, 0, result)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["violations"], [])

    def test_oncology_tumor_reduction_is_blocked(self):
        bundle = deepcopy(LEGACY_FIXTURES["oncology-claim"])
        wording = "PCPP reduces tumor growth."
        bundle["claim_records"][0].update({"claim_text": wording, "approved_wording": wording})
        bundle["external_text"] = wording
        _, result = run_bundle(bundle)
        self.assertIn("ONCOLOGY_CLAIM_ALLOWED", codes(result))

    def test_e5_traditional_chinese_efficacy_is_blocked(self):
        bundle = deepcopy(LEGACY_FIXTURES["e5-human-efficacy"])
        wording = "IMMIO 提升免疫力。"
        bundle["claim_records"][0].update(
            {"claim_text": wording, "approved_wording": wording, "claim_type": "structure_function"}
        )
        bundle["external_text"] = wording
        _, result = run_bundle(bundle)
        self.assertIn("E5_HUMAN_EFFICACY", codes(result))


# ---------------------------------------------------------------------------
# 規則 1–7
# ---------------------------------------------------------------------------

class Rule1EvidenceRefTests(unittest.TestCase):
    def test_unknown_evidence_ref_fails(self):
        bundle = make_bundle()
        bundle["claim_records"][0]["evidence_refs"] = ["ev-missing"]
        exit_code, result = run_bundle(bundle)
        self.assertEqual(exit_code, 1)
        self.assertIn("UNKNOWN_EVIDENCE_REF", codes(result))
        self.assertEqual(result["violations"][0]["path"], "claim_records[0].evidence_refs[0]")

    def test_known_evidence_ref_passes(self):
        exit_code, result = run_bundle(make_bundle())
        self.assertEqual(exit_code, 0, result)

    def test_allowed_claim_without_evidence_fails(self):
        bundle = make_bundle()
        bundle["claim_records"][0]["evidence_refs"] = []
        _, result = run_bundle(bundle)
        self.assertIn("ALLOWED_CLAIM_WITHOUT_EVIDENCE", codes(result))

    def test_duplicate_ids_fail(self):
        bundle = make_bundle()
        bundle["evidence_records"].append(deepcopy(bundle["evidence_records"][0]))
        bundle["claim_records"].append(deepcopy(bundle["claim_records"][0]))
        _, result = run_bundle(bundle)
        self.assertIn("DUPLICATE_EVIDENCE_ID", codes(result))
        self.assertIn("DUPLICATE_CLAIM_ID", codes(result))


class EvidenceKindTests(unittest.TestCase):
    REGULATION = {
        "id": "ev-reg",
        "evidence_tier": "E6",
        "evidence_kind": "regulation",
        "verification": {"status": "verified"},
        "source": {"url": "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=L0040140"},
    }
    COMPANY = {
        "id": "ev-spec",
        "evidence_tier": "E6",
        "evidence_kind": "company_fact",
        "verification": {"status": "partially_verified"},
        "source": {},
    }

    def _claim(self, claim_type: str, refs: list[str], status: str = "allowed") -> dict:
        return {
            "id": "cl-1",
            "claim_text": "幫助維持日常活力",
            "claim_type": claim_type,
            "status": status,
            "approved_wording": "幫助維持日常活力",
            "evidence_refs": refs,
        }

    def _run(self, claim: dict, *evidence: dict) -> tuple[int, dict]:
        return run_bundle(make_bundle(evidence_records=[deepcopy(item) for item in evidence], claim_records=[claim]))

    def test_permitted_phrase_backed_by_regulation_passes(self):
        exit_code, result = self._run(self._claim("permitted_phrase", ["ev-reg"]), self.REGULATION)
        self.assertEqual(exit_code, 0, result)

    def test_business_claim_backed_by_company_fact_only_warns(self):
        exit_code, result = self._run(self._claim("business", ["ev-spec"]), self.COMPANY)
        self.assertEqual(exit_code, 0, result)
        self.assertEqual(codes(result, "warnings"), {"UNVERIFIED_EVIDENCE"})

    def test_regulation_cannot_back_efficacy_claim(self):
        _, result = self._run(self._claim("structure_function", ["ev-reg"]), self.REGULATION)
        self.assertEqual(codes(result), {"NON_LITERATURE_EVIDENCE_MISUSE"})

    def test_company_fact_cannot_back_rewritten_ingredient_claim(self):
        _, result = self._run(self._claim("ingredient_role", ["ev-spec"], "rewrite_required"), self.COMPANY)
        self.assertEqual(codes(result), {"NON_LITERATURE_EVIDENCE_MISUSE"})

    def test_prohibited_claim_may_cite_regulation_as_reason(self):
        claim = self._claim("disease_treatment", ["ev-reg"], "prohibited")
        claim["claim_text"] = "可以取代藥物"
        claim["approved_wording"] = None
        exit_code, result = self._run(claim, self.REGULATION, make_bundle()["evidence_records"][0])
        self.assertEqual(exit_code, 0, result)

    def test_permitted_phrase_without_regulation_fails(self):
        _, result = self._run(self._claim("permitted_phrase", ["ev-1"]), make_bundle()["evidence_records"][0])
        self.assertEqual(codes(result), {"REGULATION_BACKED_CLAIM_WITHOUT_REGULATION"})

    def test_regulation_without_url_fails(self):
        regulation = deepcopy(self.REGULATION)
        regulation["source"] = {}
        _, result = self._run(self._claim("label_warning", ["ev-reg"]), regulation)
        self.assertEqual(codes(result), {"REGULATION_WITHOUT_URL"})

    def test_non_literature_must_be_e6(self):
        regulation = deepcopy(self.REGULATION)
        regulation["evidence_tier"] = "E3"
        exit_code, result = self._run(self._claim("permitted_phrase", ["ev-reg"]), regulation)
        self.assertEqual(exit_code, 2, result)

    def test_unknown_kind_is_input_error(self):
        regulation = deepcopy(self.REGULATION)
        regulation["evidence_kind"] = "supplier_brochure"
        exit_code, _ = self._run(self._claim("permitted_phrase", ["ev-reg"]), regulation)
        self.assertEqual(exit_code, 2)


class Rule2E7Tests(unittest.TestCase):
    def test_e7_only_allowed_fails(self):
        bundle = make_bundle()
        bundle["evidence_records"][0]["evidence_tier"] = "E7"
        _, result = run_bundle(bundle)
        self.assertIn("E7_CLAIM_ALLOWED", codes(result))

    def test_e7_internal_only_not_in_text_passes(self):
        bundle = make_bundle()
        bundle["evidence_records"].append({"id": "ev-7", "evidence_tier": "E7"})
        bundle["claim_records"].append(
            {
                "id": "cl-7",
                "claim_text": "供應商簡報說可以大幅提升精神",
                "claim_type": "research_lead",
                "status": "internal_only",
                "evidence_refs": ["ev-7"],
            }
        )
        exit_code, result = run_bundle(bundle)
        self.assertEqual(exit_code, 0, result)

    def test_e7_mixed_with_stronger_evidence_only_warns(self):
        bundle = make_bundle()
        bundle["evidence_records"].append({"id": "ev-7", "evidence_tier": "E7"})
        bundle["claim_records"][0]["evidence_refs"].append("ev-7")
        exit_code, result = run_bundle(bundle)
        self.assertEqual(exit_code, 0, result)
        self.assertIn("E7_EVIDENCE_CITED", codes(result, "warnings"))


class Rule3E5HumanEfficacyTests(unittest.TestCase):
    def test_e5_human_efficacy_type_fails(self):
        bundle = make_bundle()
        bundle["evidence_records"][0]["evidence_tier"] = "E5"
        bundle["claim_records"][0]["claim_type"] = "human_efficacy"
        _, result = run_bundle(bundle)
        self.assertIn("E5_HUMAN_EFFICACY", codes(result))

    def test_e6_human_efficacy_text_fails(self):
        bundle = make_bundle()
        bundle["evidence_records"][0]["evidence_tier"] = "E6"
        wording = "有助於提升免疫力"
        bundle["claim_records"][0].update({"claim_text": wording, "approved_wording": wording})
        bundle["external_text"] = wording
        _, result = run_bundle(bundle)
        self.assertIn("E5_HUMAN_EFFICACY", codes(result))

    def test_e5_mechanism_education_passes(self):
        bundle = make_bundle()
        bundle["evidence_records"][0]["evidence_tier"] = "E5"
        wording = "細胞研究觀察到多醣體與免疫訊號路徑的關聯"
        bundle["claim_records"][0].update(
            {"claim_text": wording, "approved_wording": wording, "claim_type": "mechanism_education"}
        )
        bundle["external_text"] = wording
        exit_code, result = run_bundle(bundle)
        self.assertEqual(exit_code, 0, result)

    def test_e3_human_efficacy_passes_rule3(self):
        bundle = make_bundle()
        bundle["claim_records"][0]["claim_type"] = "human_efficacy"
        _, result = run_bundle(bundle)
        self.assertNotIn("E5_HUMAN_EFFICACY", codes(result))

    def test_e5_plus_e3_uses_best_tier(self):
        bundle = make_bundle()
        bundle["evidence_records"].append({"id": "ev-5", "evidence_tier": "E5", "verification": {"status": "verified"}})
        bundle["claim_records"][0]["evidence_refs"].append("ev-5")
        bundle["claim_records"][0]["claim_type"] = "human_efficacy"
        _, result = run_bundle(bundle)
        self.assertNotIn("E5_HUMAN_EFFICACY", codes(result))


class Rule4ApprovedWordingTests(unittest.TestCase):
    def test_allowed_without_wording_fails(self):
        for wording in (None, "", "   "):
            with self.subTest(wording=wording):
                bundle = make_bundle()
                bundle["claim_records"][0]["approved_wording"] = wording
                _, result = run_bundle(bundle)
                self.assertIn("ALLOWED_WITHOUT_APPROVED_WORDING", codes(result))

    def test_prohibited_without_wording_passes(self):
        bundle = make_bundle()
        bundle["claim_records"].append(
            {"id": "cl-2", "claim_text": "吃了精神百倍", "status": "prohibited", "approved_wording": None, "evidence_refs": []}
        )
        exit_code, result = run_bundle(bundle)
        self.assertEqual(exit_code, 0, result)


class Rule5ExternalTextTests(unittest.TestCase):
    def test_oncology_therapeutic_context_fails(self):
        _, result = run_bundle(make_bundle(external_text="臨床觀察可縮小腫瘤體積。"))
        self.assertIn("EXTERNAL_ONCOLOGY_THERAPEUTIC", codes(result))

    def test_oncology_mention_alone_only_warns(self):
        exit_code, result = run_bundle(make_bundle(external_text="本研究受試者為癌症病友家屬。\n幫助維持日常活力。"))
        self.assertEqual(exit_code, 0, result)
        self.assertIn("EXTERNAL_ONCOLOGY_MENTION", codes(result, "warnings"))

    def test_oncology_and_therapeutic_in_different_sentences(self):
        text = "癌症是國人十大死因之一。\n規律作息有助降低壓力感受。"
        _, result = run_bundle(make_bundle(external_text=text))
        self.assertNotIn("EXTERNAL_ONCOLOGY_THERAPEUTIC", codes(result))

    def test_internal_marker_fails_with_line_number(self):
        _, result = run_bundle(make_bundle(external_text="第一行\n（內部註記：法規風險高）"))
        markers = [v for v in result["violations"] if v["code"] == "EXTERNAL_INTERNAL_MARKER"]
        self.assertTrue(markers)
        self.assertEqual(markers[0]["path"], "external_text:2")

    def test_english_internal_marker_fails(self):
        _, result = run_bundle(make_bundle(external_text="Internal only: supports daily wellness."))
        self.assertIn("EXTERNAL_INTERNAL_MARKER", codes(result))

    def test_placeholder_only_warns_regardless_of_speaker_deck(self):
        for speaker_deck in (True, False, None):
            with self.subTest(speaker_deck=speaker_deck):
                bundle = make_bundle(external_text="單劑成本：［待補：單劑成本］")
                if speaker_deck is None:
                    bundle.pop("speaker_deck")
                else:
                    bundle["speaker_deck"] = speaker_deck
                exit_code, result = run_bundle(bundle)
                self.assertEqual(exit_code, 0, result)
                self.assertIn("PLACEHOLDER_PENDING", codes(result, "warnings"))

    def test_bare_pending_marker_fails(self):
        _, result = run_bundle(make_bundle(external_text="MOQ 待補"))
        self.assertIn("EXTERNAL_INTERNAL_MARKER", codes(result))

    def test_clean_text_passes(self):
        exit_code, result = run_bundle(make_bundle())
        self.assertEqual(exit_code, 0, result)
        self.assertEqual(result["warnings"], [])


class Rule6RejectedWordingTests(unittest.TestCase):
    def _bundle_with(self, status: str, text: str, approved=None) -> dict:
        bundle = make_bundle(external_text=text)
        bundle["claim_records"].append(
            {
                "id": "cl-x",
                "claim_text": "一週就能感受到明顯改變",
                "claim_type": "human_efficacy",
                "status": status,
                "approved_wording": approved,
                "evidence_refs": ["ev-1"],
            }
        )
        return bundle

    def test_prohibited_sentence_leak_fails(self):
        bundle = self._bundle_with("prohibited", "好消息！一週就能感受到明顯改變。")
        _, result = run_bundle(bundle)
        self.assertIn("REJECTED_CLAIM_LEAK", codes(result))

    def test_rewrite_required_sentence_leak_fails_despite_formatting(self):
        bundle = self._bundle_with("rewrite_required", "**一週 就能感受到** 明顯改變", approved="日常保養的好選擇")
        _, result = run_bundle(bundle)
        self.assertIn("REJECTED_CLAIM_LEAK", codes(result))

    def test_rewritten_wording_passes(self):
        bundle = self._bundle_with("rewrite_required", "日常保養的好選擇。", approved="日常保養的好選擇")
        exit_code, result = run_bundle(bundle)
        self.assertEqual(exit_code, 0, result)

    def test_internal_only_sentence_leak_fails(self):
        bundle = self._bundle_with("internal_only", "一週就能感受到明顯改變")
        _, result = run_bundle(bundle)
        self.assertIn("INTERNAL_CLAIM_LEAK", codes(result))


class Rule7TaiwanTermsTests(unittest.TestCase):
    def test_each_listed_term_fails(self):
        for term in ("治療", "治癒", "預防疾病", "消炎", "抗癌", "減肥", "瘦身", "燃脂", "降血壓", "降血糖", "根治", "藥效"):
            with self.subTest(term=term):
                _, result = run_bundle(make_bundle(external_text=f"本產品可{term}。"))
                self.assertIn("TW_PROHIBITED_TERM", codes(result))

    def test_fullwidth_percent_is_normalized(self):
        _, result = run_bundle(make_bundle(external_text="１００％有效"))
        self.assertIn("TW_PROHIBITED_TERM", codes(result))

    def test_disclaimer_is_not_flagged(self):
        exit_code, result = run_bundle(make_bundle(external_text="本產品非藥品，不具治療效果。"))
        self.assertEqual(exit_code, 0, result)

    def test_terms_are_constants_at_module_top(self):
        self.assertIn("降血糖", check_claims.TAIWAN_PROHIBITED_TERMS)



class IgnoreBlockTests(unittest.TestCase):
    PROMPT = (
        "# 提示詞\n"
        "<!-- check:ignore-start -->\n"
        "禁止使用：治療、抗癌、瘦身、100%\n"
        "內部說明：不要寫癌症治療相關內容（法規風險）\n"
        "<!-- check:ignore-end -->\n"
        "{body}\n"
    )

    def test_ignored_block_is_not_scanned(self):
        text = self.PROMPT.format(body="幫助維持日常活力。")
        exit_code, result = run_bundle(make_bundle(external_text=text))
        self.assertEqual(exit_code, 0, result)
        self.assertEqual(result["warnings"], [])

    def test_text_outside_block_is_still_scanned_with_correct_line(self):
        text = self.PROMPT.format(body="可以瘦身")
        _, result = run_bundle(make_bundle(external_text=text))
        hits = [v for v in result["violations"] if v["code"] == "TW_PROHIBITED_TERM"]
        self.assertEqual([v["path"] for v in hits], ["external_text:6"])

    def test_multiple_blocks(self):
        text = (
            "<!-- check:ignore-start -->治療<!-- check:ignore-end -->\n"
            "中間有減肥\n"
            "<!-- check:ignore-start -->\n抗癌\n<!-- check:ignore-end -->"
        )
        _, result = run_bundle(make_bundle(external_text=text))
        hits = [v for v in result["violations"] if v["code"] == "TW_PROHIBITED_TERM"]
        self.assertEqual([v["path"] for v in hits], ["external_text:2"])

    def test_rejected_wording_leak_is_scanned_inside_block(self):
        bundle = make_bundle(external_text=self.PROMPT.format(body="").replace("禁止使用", "一週就能感受到明顯改變；禁止使用"))
        bundle["claim_records"].append(
            {"id": "cl-x", "claim_text": "一週就能感受到明顯改變", "status": "prohibited", "evidence_refs": []}
        )
        _, result = run_bundle(bundle)
        self.assertEqual(codes(result), {"REJECTED_CLAIM_LEAK"})
        self.assertIn("改寫成類別描述", result["violations"][0]["message"])

    def test_rejected_wording_leak_outside_block_has_no_ignore_hint(self):
        bundle = make_bundle(external_text=self.PROMPT.format(body="一週就能感受到明顯改變"))
        bundle["claim_records"].append(
            {"id": "cl-x", "claim_text": "一週就能感受到明顯改變", "status": "prohibited", "evidence_refs": []}
        )
        _, result = run_bundle(bundle)
        self.assertEqual(codes(result), {"REJECTED_CLAIM_LEAK"})
        self.assertNotIn("改寫成類別描述", result["violations"][0]["message"])

    def test_unbalanced_markers_scan_everything(self):
        text = "<!-- check:ignore-start -->\n禁止使用：治療\n"
        _, result = run_bundle(make_bundle(external_text=text))
        self.assertIn("TW_PROHIBITED_TERM", codes(result))
        self.assertIn("UNBALANCED_IGNORE_BLOCK", codes(result, "warnings"))

    def test_ignore_block_in_external_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "prompt.md").write_text(self.PROMPT.format(body="幫助維持日常活力。"), encoding="utf-8")
            bundle = {
                "evidence_records": make_bundle()["evidence_records"],
                "claim_records": make_bundle()["claim_records"],
                "external_files": ["prompt.md"],
            }
            path = Path(tmp) / "bundle.json"
            path.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
            exit_code, result = check_claims.run([str(path)])
        self.assertEqual(exit_code, 0, result)

class HtmlExternalFileTests(unittest.TestCase):
    def _run_file(self, name: str, content: str) -> tuple[int, dict]:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / name).write_text(content, encoding="utf-8")
            bundle = make_bundle()
            del bundle["external_text"]
            bundle["external_files"] = [name]
            path = Path(tmp) / "bundle.json"
            path.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
            return check_claims.run([str(path)])

    def test_css_percentage_is_not_flagged(self):
        html = (
            "<style>\n  table { width: 100%; }\n</style>\n"
            '<div style="width:100%">幫助維持日常活力。</div>\n'
        )
        exit_code, result = self._run_file("page.html", html)
        self.assertEqual(exit_code, 0, result)

    def test_script_strings_are_still_scanned(self):
        html = "<style>p { width: 100%; }</style>\n<script>\nconst t = '可以瘦身';\n</script>\n"
        _, result = self._run_file("page.html", html)
        hits = [v for v in result["violations"] if v["code"] == "TW_PROHIBITED_TERM"]
        self.assertEqual([v["path"] for v in hits], ["external_files[0]:3"])

    def test_text_attributes_are_still_scanned(self):
        _, result = self._run_file("page.htm", '<img alt="保證有效" style="width:100%">')
        self.assertIn("保證", " ".join(v["message"] for v in result["violations"]))
        self.assertNotIn("100%", " ".join(v["message"] for v in result["violations"]))

    def test_markdown_percentage_is_still_flagged(self):
        _, result = self._run_file("brief.md", "width: 100%")
        self.assertIn("TW_PROHIBITED_TERM", codes(result))


# ---------------------------------------------------------------------------
# 輸入、檔案與 CLI
# ---------------------------------------------------------------------------

def make_series_bundle(**overrides) -> dict:
    """可通過的系列模式 bundle：兩個產品，各一筆證據，另有一筆兩者共用的證據。"""
    bundle = {
        "products": [{"id": "p-a", "name": "產品 A"}, {"id": "p-b", "name": "產品 B"}],
        "evidence_records": [
            {"id": "ev-a", "products": ["p-a"], "evidence_tier": "E3", "verification": {"status": "verified"}},
            {"id": "ev-b", "products": ["p-b"], "evidence_tier": "E3", "verification": {"status": "verified"}},
            {"id": "ev-ab", "products": ["p-a", "p-b"], "evidence_tier": "E3", "verification": {"status": "verified"}},
        ],
        "claim_records": [
            {
                "id": "cl-a",
                "product": "p-a",
                "claim_text": "幫助維持日常活力",
                "claim_type": "structure_function",
                "status": "allowed",
                "approved_wording": "幫助維持日常活力",
                "evidence_refs": ["ev-a", "ev-ab"],
            },
            {
                "id": "cl-series",
                "product": "series",
                "claim_text": "整個系列都能提升免疫力",
                "claim_type": "human_efficacy",
                "status": "rewrite_required",
                "approved_wording": None,
                "evidence_refs": ["ev-a", "ev-b"],
            },
        ],
        "external_text": "靈芝萃取，幫助維持日常活力。",
    }
    bundle.update(overrides)
    return bundle


class SeriesModeTests(unittest.TestCase):
    def test_valid_series_bundle_passes(self):
        code, result = run_bundle(make_series_bundle())
        self.assertEqual(code, 0, result)

    def test_cross_product_evidence_fails(self):
        bundle = make_series_bundle()
        bundle["claim_records"][0]["evidence_refs"] = ["ev-b"]
        code, result = run_bundle(bundle)
        self.assertEqual(code, 1)
        self.assertEqual(codes(result), {"PRODUCT_EVIDENCE_MISMATCH"})
        self.assertIn("ev-b", result["violations"][0]["message"])

    def test_rewrite_required_product_claim_is_also_checked(self):
        bundle = make_series_bundle()
        bundle["claim_records"][0].update(status="rewrite_required", evidence_refs=["ev-b"])
        code, result = run_bundle(bundle)
        self.assertEqual(code, 1)
        self.assertIn("PRODUCT_EVIDENCE_MISMATCH", codes(result))

    def test_prohibited_claim_is_not_checked(self):
        bundle = make_series_bundle()
        bundle["claim_records"][0].update(status="prohibited", evidence_refs=["ev-b"])
        bundle["external_text"] = "靈芝萃取。"
        code, result = run_bundle(bundle)
        self.assertEqual(code, 0, result)

    def test_series_efficacy_claim_missing_product_fails(self):
        bundle = make_series_bundle()
        bundle["claim_records"][1]["evidence_refs"] = ["ev-a"]
        code, result = run_bundle(bundle)
        self.assertEqual(code, 1)
        self.assertEqual(codes(result), {"SERIES_CLAIM_EVIDENCE_GAP"})
        self.assertIn("p-b", result["violations"][0]["message"])

    def test_series_efficacy_detected_from_wording(self):
        bundle = make_series_bundle()
        bundle["claim_records"][1].update(claim_type="positioning", evidence_refs=["ev-a"])
        code, result = run_bundle(bundle)
        self.assertEqual(code, 1)
        self.assertIn("SERIES_CLAIM_EVIDENCE_GAP", codes(result))

    def test_shared_evidence_covers_series_claim(self):
        bundle = make_series_bundle()
        bundle["claim_records"][1]["evidence_refs"] = ["ev-ab"]
        code, result = run_bundle(bundle)
        self.assertEqual(code, 0, result)

    def test_series_positioning_claim_is_exempt(self):
        bundle = make_series_bundle()
        bundle["claim_records"][1].update(
            claim_text="同一套萃取平台的系列產品",
            claim_type="business",
            status="allowed",
            approved_wording="同一套萃取平台的系列產品",
            evidence_refs=["ev-a"],
        )
        code, result = run_bundle(bundle)
        self.assertEqual(code, 0, result)

    def test_series_structure_function_claim_needs_all_products(self):
        # 中文功能性說法不會被 _human_efficacy 的英文規則抓到，仍須每款都有證據。
        bundle = make_series_bundle()
        bundle["claim_records"][1].update(
            claim_text="整個系列都能幫助維持免疫",
            claim_type="structure_function",
            status="allowed",
            approved_wording="整個系列都能幫助維持免疫",
            evidence_refs=["ev-a"],
        )
        code, result = run_bundle(bundle)
        self.assertEqual(code, 1, result)
        self.assertIn("SERIES_CLAIM_EVIDENCE_GAP", codes(result))

    def test_malformed_products_exit_2(self):
        cases = {
            "empty": [],
            "not_list": {"id": "p-a"},
            "reserved_id": [{"id": "series", "name": "系列"}],
            "duplicate_id": [{"id": "p-a", "name": "A"}, {"id": "p-a", "name": "A2"}],
            "missing_name": [{"id": "p-a"}],
            "not_object": ["p-a"],
        }
        for name, products in cases.items():
            with self.subTest(name):
                code, result = run_bundle(make_series_bundle(products=products))
                self.assertEqual(code, 2)
                self.assertEqual(result["status"], "error")
                self.assertTrue(any(error["path"].startswith("products") for error in result["errors"]))

    def test_missing_evidence_products_exit_2(self):
        for value in (None, [], ["p-unknown"], "p-a"):
            with self.subTest(value):
                bundle = make_series_bundle()
                if value is None:
                    del bundle["evidence_records"][0]["products"]
                else:
                    bundle["evidence_records"][0]["products"] = value
                code, result = run_bundle(bundle)
                self.assertEqual(code, 2)
                self.assertEqual([error["path"] for error in result["errors"]], ["evidence_records[0].products"])

    def test_unknown_claim_product_exit_2(self):
        for value in (None, "p-unknown", ["p-a"]):
            with self.subTest(value):
                bundle = make_series_bundle()
                if value is None:
                    del bundle["claim_records"][0]["product"]
                else:
                    bundle["claim_records"][0]["product"] = value
                code, result = run_bundle(bundle)
                self.assertEqual(code, 2)
                self.assertEqual([error["path"] for error in result["errors"]], ["claim_records[0].product"])

    def test_single_product_bundle_ignores_product_fields(self):
        # 沒有 products 時，證據與宣稱上的 products／product 不影響判定。
        bundle = make_bundle()
        bundle["evidence_records"][0]["products"] = ["p-other"]
        bundle["claim_records"][0]["product"] = "p-a"
        self.assertEqual(run_bundle(bundle), run_bundle(make_bundle()))
        for fixture in LEGACY_FIXTURES.values():
            self.assertEqual(check_claims.validate_input(fixture), [])


class InputTests(unittest.TestCase):
    def test_missing_bundle_file_exits_2(self):
        exit_code, result = check_claims.run(["/nonexistent/bundle.json"])
        self.assertEqual(exit_code, 2)
        self.assertEqual(result["status"], "error")

    def test_broken_json_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bundle.json"
            path.write_text("{not json", encoding="utf-8")
            exit_code, result = check_claims.run([str(path)])
        self.assertEqual(exit_code, 2)
        self.assertEqual(result["errors"][0]["code"], "INPUT_BAD_JSON")

    def test_missing_required_fields_exit_2(self):
        cases = {
            "no_claims": lambda b: b.pop("claim_records"),
            "no_external": lambda b: b.pop("external_text"),
            "bad_status": lambda b: b["claim_records"][0].update(status="approved"),
            "bad_tier": lambda b: b["evidence_records"][0].update(evidence_tier="E9"),
            "no_claim_text": lambda b: b["claim_records"][0].pop("claim_text"),
            "bad_speaker_deck": lambda b: b.update(speaker_deck="yes"),
        }
        for name, mutate in cases.items():
            with self.subTest(case=name):
                bundle = make_bundle()
                mutate(bundle)
                exit_code, result = run_bundle(bundle)
                self.assertEqual(exit_code, 2, result)

    def test_external_files_are_read_relative_to_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            out.mkdir()
            (out / "a.md").write_text("# 標題\n\n幫助維持日常活力。\n", encoding="utf-8")
            (out / "b.md").write_text("第一行\n可以瘦身\n", encoding="utf-8")
            bundle = make_bundle(external_files=["out/a.md", "out/b.md"])
            bundle.pop("external_text")
            path = Path(tmp) / "bundle.json"
            path.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
            exit_code, result = check_claims.run([str(path)])
        self.assertEqual(exit_code, 1)
        hits = [v for v in result["violations"] if v["code"] == "TW_PROHIBITED_TERM"]
        self.assertEqual(hits[0]["path"], "external_files[1]:2")

    def test_missing_external_file_exits_2(self):
        bundle = make_bundle(external_files=["missing.md"])
        bundle.pop("external_text")
        exit_code, result = run_bundle(bundle)
        self.assertEqual(exit_code, 2)


class CliTests(unittest.TestCase):
    def _cli(self, bundle: dict) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bundle.json"
            path.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "check_claims.py"), str(path)],
                text=True,
                capture_output=True,
                check=False,
            )

    def test_cli_pass(self):
        proc = self._cli(LEGACY_FIXTURES["valid-bundle"])
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(json.loads(proc.stdout), {"status": "pass", "violations": [], "warnings": []})

    def test_cli_fail_has_stable_shape(self):
        proc = self._cli(LEGACY_FIXTURES["oncology-claim"])
        self.assertEqual(proc.returncode, 1)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["status"], "fail")
        for item in payload["violations"]:
            self.assertEqual(set(item), {"code", "path", "message"})


if __name__ == "__main__":
    unittest.main()
