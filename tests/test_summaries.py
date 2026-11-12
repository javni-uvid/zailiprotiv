import json
from types import SimpleNamespace

import pytest

from zailiprotiv import summaries

MEMO = {"sections": {"reasons": "Разлог за доношење закона је усклађивање са прописима ЕУ.",
                     "funds": "За спровођење овог закона нису потребна средства из буџета.", "explained": "x" * 20000}}
LAW = {"title": "Zakon o zaštiti potrošača"}


class Client:
    def __init__(self, text):
        self.text, self.asked = text, []
        self.messages = self

    def create(self, **kw):
        self.asked.append(kw)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=self.text)],
                               usage=SimpleNamespace(input_tokens=100, output_tokens=50))


def test_material_cuts_long_sections():
    text = summaries.material(LAW, MEMO)
    assert text.startswith("Наслов закона: Zakon o zaštiti potrošača")
    assert "## Разлози за доношење" in text and "x" * 8000 in text and "x" * 8001 not in text


def test_summary_keeps_only_expected_fields():
    reply = 'Ево: {"ukratko": "Закон уређује заштиту потрошача, према предлагачу.", "razlozi": ["усклађивање", ""], ' \
            '"promene": ["нова правила"], "sredstva": "Нису потребна средства.", "ocena": "одличан"}'
    client = Client(reply)
    out = summaries.summarize(LAW, MEMO, client)
    assert out["summary"] == {"ukratko": "Закон уређује заштиту потрошача, према предлагачу.",
                              "razlozi": ["усклађивање"], "promene": ["нова правила"],
                              "sredstva": "Нису потребна средства."}
    assert client.asked[0]["model"] == summaries.MODEL and client.asked[0]["system"] == summaries.SYSTEM
    assert out["fingerprint"] == summaries.fingerprint(summaries.material(LAW, MEMO))


def test_an_empty_or_malformed_reply_is_refused():
    with pytest.raises(ValueError):
        summaries.parse("Не могу.")
    with pytest.raises(ValueError):
        summaries.parse('{"ukratko": ""}')


def test_summaries_command_skips_the_unchanged(tmp_path, monkeypatch):
    from zailiprotiv import cli
    (tmp_path / "bills").mkdir()
    (tmp_path / "bills" / "b.json").write_text(json.dumps(MEMO))
    (tmp_path / "laws.json").write_text(json.dumps({"laws": {"L": {**LAW, "bill_file": "b.json"}}}))
    client = Client('{"ukratko": "Кратко.", "razlozi": [], "promene": [], "sredstva": ""}')
    import anthropic
    monkeypatch.setattr(anthropic, "Anthropic", lambda: client)
    args = ["summaries", "--laws", str(tmp_path / "laws.json"), "--bills", str(tmp_path / "bills"),
            "--out", str(tmp_path / "s")]
    assert cli.main(args) == 0 and cli.main(args) == 0
    assert len(client.asked) == 1
    assert json.loads((tmp_path / "s" / "b.json").read_text())["summary"]["ukratko"] == "Кратко."


def test_session_summaries_are_checked_and_kept(tmp_path):
    from zailiprotiv import cli
    (tmp_path / "bills").mkdir()
    (tmp_path / "bills" / "b.json").write_text(json.dumps(MEMO))
    (tmp_path / "laws.json").write_text(json.dumps({"laws": {"L": {**LAW, "bill_file": "b.json", "passed": "2026-01-01",
                                                                   "kind": "law"}}}))
    common = ["--laws", str(tmp_path / "laws.json"), "--bills", str(tmp_path / "bills"), "--out", str(tmp_path / "s")]
    assert cli.main(["export", *common, "--to", str(tmp_path / "x")]) == 0
    assert (tmp_path / "x" / "b.txt").read_text().startswith("Наслов закона:")
    (tmp_path / "in.jsonl").write_text(
        json.dumps({"bill_file": "b", "summary": {"ukratko": "Кратко.", "razlozi": ["а"], "promene": [],
                                                  "sredstva": ""}}, ensure_ascii=False) + "\n" +
        json.dumps({"bill_file": "nema", "summary": {"ukratko": "x"}}) + "\n")
    assert cli.main(["import", *common, str(tmp_path / "in.jsonl"), "--model", "claude-opus-5-5"]) == 0
    saved = json.loads((tmp_path / "s" / "b.json").read_text())
    assert saved["model"] == "claude-opus-5-5" and saved["summary"]["razlozi"] == ["а"]
    # the API run then leaves it alone
    assert cli._pending(type("A", (), {"laws": str(tmp_path / "laws.json"), "bills": str(tmp_path / "bills"),
                                       "out": str(tmp_path / "s")})) == []
