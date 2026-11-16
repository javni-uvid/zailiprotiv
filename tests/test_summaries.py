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
    anthropic = pytest.importorskip("anthropic")
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


# --- checks and the local-model path ---------------------------------------------------------------------------

def test_latin_and_back_keeps_the_digraphs():
    text = "Предлог закона о љубави, њиви и џему: Љубљана"
    assert summaries.to_latin(text) == "Predlog zakona o ljubavi, njivi i džemu: Ljubljana"
    assert summaries.to_cyrillic(summaries.to_latin(text)) == text


def test_local_material_drops_the_statement_of_conformity_and_the_quotes():
    memo = {"sections": {"reasons": "Разлози са „Службени гласник РС“.\nИЗЈАВА О УСКЛАЂЕНОСТИ ПРОПИСА\nНародни посланици Петар Петровић"}}
    text = summaries.local_material(LAW, memo)
    assert "Razlozi sa Službeni glasnik RS." in text
    assert "Petrović" not in text and "„" not in text and '"' not in text
    # the standard material, which the fingerprint stands for, is untouched
    assert "ИЗЈАВА" in summaries.material(LAW, memo)


def test_attribution_is_added_only_where_it_is_missing():
    s = {"ukratko": "x", "razlozi": ["Предлагач наводи да је закон стар.", "Закон је застарео.", "Према образложењу, треба се ускладити."],
         "promene": [], "sredstva": ""}
    assert summaries.unattributed(s) == ["Закон је застарео."]
    out, added = summaries.attribute(s)
    assert added == 1 and out["razlozi"][1] == "Према предлагачу, закон је застарео."
    assert out["razlozi"][0] == s["razlozi"][0] and s["razlozi"][1] == "Закон је застарео."  # the input is not changed


def test_repeated_items_and_the_sentence_about_funds_are_dropped():
    s = {"ukratko": "x", "razlozi": ["А.", "а", "Б."], "promene": ["В.", "За закон нису потребна додатна средства.", "В."], "sredstva": ""}
    out = summaries.dedupe(s)
    assert out["razlozi"] == ["А.", "Б."] and out["promene"] == ["В."]


def test_a_turned_round_negation_is_flagged_not_edited():
    memo = {"sections": {"reasons": "Садржина закона и поступак његовог усвајања нису у складу са обавезама које је Србија преузела."}}
    bad = {"ukratko": "x", "promene": [], "razlozi": ["Предлагач наводи да је поступак у складу са обавезама које је Србија преузела."]}
    good = {"ukratko": "x", "promene": [], "razlozi": ["Предлагач наводи да поступак није у складу са обавезама које је Србија преузела."]}
    assert summaries.negation_review(bad, memo) == bad["razlozi"]
    assert summaries.negation_review(good, memo) == []


class Reply:
    def __init__(self, content):
        self.body = json.dumps({"message": {"content": content}, "prompt_eval_count": 7, "eval_count": 5}).encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def read(self):
        return self.body


def test_a_local_model_answers_in_latin_and_the_summary_is_cyrillic(monkeypatch):
    monkeypatch.setattr(summaries, "MODEL", "ollama:llama3.1:8b")
    asked = []
    answer = ('{"ukratko": "Predlagač predlaže uređenje zaštite potrošača.", "razlozi": ["Usklađivanje sa propisima EU", '
              '"Usklađivanje sa propisima EU"], "promene": ["Nova pravila"], "sredstva": "Nisu potrebna sredstva."}')

    def urlopen(req, timeout):
        asked.append(json.loads(req.data))
        return Reply(answer)

    out = summaries.ollama_summarize(LAW, MEMO, urlopen)
    assert out["summary"]["ukratko"] == "Предлагач предлаже уређење заштите потрошача."
    assert out["summary"]["razlozi"] == ["Према предлагачу, усклађивање са прописима ЕУ"]  # once, with the attribution
    assert out["review"] == {"attribution_added": 1, "negation": []}
    assert out["model"] == "ollama:llama3.1:8b" and out["usage"] == {"input": 7, "output": 5}
    assert asked[0]["model"] == "llama3.1:8b" and "format" not in asked[0] and asked[0]["options"]["temperature"] == 0
    assert out["fingerprint"] == summaries.fingerprint(summaries.material(LAW, MEMO))  # what the API wrote stays
    assert "Cyrillic" not in asked[0]["messages"][0]["content"] and "latinicom" in asked[0]["messages"][0]["content"]
