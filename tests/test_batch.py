import json
from types import SimpleNamespace

from zailiprotiv import batch

MEMO = {"sections": {"reasons": "Разлог за доношење закона је усклађивање са прописима ЕУ."}}
LAW = {"title": "Zakon o zaštiti potrošača"}


class Batches:
    """A fake Message Batches API: a batch ends after `polls` looks; each request gets `reply(params)`."""

    def __init__(self, reply, polls=1):
        self.reply, self.polls, self.sent, self.looks = reply, polls, [], 0
        self.messages = SimpleNamespace(batches=self)

    def create(self, requests):
        self.sent.append(list(requests))
        return SimpleNamespace(id=f"b{len(self.sent)}")

    def retrieve(self, id):
        self.looks += 1
        return SimpleNamespace(processing_status="ended" if self.looks >= self.polls else "in_progress")

    def results(self, id):
        for r in self.sent[int(id[1:]) - 1]:
            msg = SimpleNamespace(content=[SimpleNamespace(type="text", text=self.reply(r["params"]))])
            yield SimpleNamespace(custom_id=r["custom_id"], result=SimpleNamespace(type="succeeded", message=msg))


def test_a_batch_left_running_is_picked_up_next_run(tmp_path, monkeypatch):
    monkeypatch.setattr(batch, "POLL", 0)
    client, state = Batches(lambda p: "одговор", polls=3), batch.State(tmp_path / "batches.json")
    reqs = {"име-ћирилицом.json": {"messages": []}}
    assert batch.run(client, state, "k", reqs, wait_minutes=0) is None
    assert json.loads((tmp_path / "batches.json").read_text())["pending"]["k"]["id"] == "b1"
    state = batch.State(tmp_path / "batches.json")  # the next run
    assert batch.run(client, state, "k", reqs, wait_minutes=1) == {"име-ћирилицом.json": "одговор"}
    assert len(client.sent) == 1 and not state.pending("k")


def test_a_refused_reply_is_sent_back_with_what_was_wrong_and_then_given_up(tmp_path):
    state = batch.State(tmp_path / "batches.json")
    state.refuse("k", "n", "{\"x\": 1}", ["citat nije doslovan"])
    msgs = batch.messages("k", "n", "материјал", state)
    assert [m["role"] for m in msgs] == ["user", "assistant", "user"] and "citat nije doslovan" in msgs[2]["content"]
    assert not state.gave_up("k", "n")
    state.refuse("k", "n", "{}", ["опет"])
    assert state.gave_up("k", "n")
    state.accept("k", "n")
    assert not state.gave_up("k", "n") and state.data["refused"] == {}


def test_summaries_through_a_batch(tmp_path, monkeypatch):
    import anthropic

    from zailiprotiv import cli
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setattr(batch, "POLL", 0)
    client = Batches(lambda p: '{"ukratko": "Кратко.", "razlozi": [], "promene": [], "sredstva": ""}')
    monkeypatch.setattr(anthropic, "Anthropic", lambda: client)
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    (tmp_path / "bills").mkdir()
    (tmp_path / "bills" / "b.json").write_text(json.dumps(MEMO))
    (tmp_path / "laws.json").write_text(json.dumps({"laws": {"L": {**LAW, "bill_file": "b.json"}}}))
    args = ["summaries", "--batch", "--laws", str(tmp_path / "laws.json"), "--bills", str(tmp_path / "bills"),
            "--out", str(tmp_path / "s")]
    assert cli.main(args) == 0 and cli.main(args) == 0
    assert len(client.sent) == 1 and len(client.sent[0]) == 1
    assert json.loads((tmp_path / "s" / "b.json").read_text())["summary"]["ukratko"] == "Кратко."


def test_bills_in_procedure_are_summarised_too(tmp_path, monkeypatch):
    import anthropic

    from zailiprotiv import cli
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setattr(batch, "POLL", 0)
    client = Batches(lambda p: '{"ukratko": "Кратко.", "razlozi": [], "promene": [], "sredstva": ""}')
    monkeypatch.setattr(anthropic, "Anthropic", lambda: client)
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    (tmp_path / "bills").mkdir()
    (tmp_path / "bills" / "p.json").write_text(json.dumps(MEMO))
    (tmp_path / "laws.json").write_text(json.dumps({"laws": {}}))
    (tmp_path / "procedure.json").write_text(json.dumps({"fetched": "2026-11-13", "bills": {
        "https://x/p.pdf": {"title": "Predlog zakona", "last_seen": "2026-11-13", "bill_file": "p.json"},
        "https://x/gone.pdf": {"title": "Stari predlog", "last_seen": "2026-11-01", "bill_file": "gone.json"}}}))
    args = ["summaries", "--batch", "--laws", str(tmp_path / "laws.json"), "--bills", str(tmp_path / "bills"),
            "--out", str(tmp_path / "s")]
    assert cli.main(args) == 0
    assert [p.name for p in (tmp_path / "s").iterdir()] == ["p.json"]


def test_a_federated_client_signs_in_with_the_rules_ids(monkeypatch):
    from zailiprotiv import federated
    for k, v in federated.SETTINGS.items():
        monkeypatch.setenv(v, k + "-x")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    client = federated.client()
    assert client.api_key is None and client.credentials is not None  # no key: the repository's identity


def test_federated_sign_in_is_used_only_when_set_up(monkeypatch):
    from zailiprotiv import federated
    for v in list(federated.SETTINGS.values()) + ["ACTIONS_ID_TOKEN_REQUEST_URL"]:
        monkeypatch.delenv(v, raising=False)
    assert not federated.available()
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_URL", "https://x/?a=1")
    for v in federated.SETTINGS.values():
        monkeypatch.setenv(v, "x")
    assert federated.available()


def test_a_reply_cut_off_at_the_limit_is_not_a_reply(tmp_path, monkeypatch):
    monkeypatch.setattr(batch, "POLL", 0)
    client, state = Batches(lambda p: '{"pola'), batch.State(tmp_path / "batches.json")
    whole = client.results

    def cut(id):
        for e in whole(id):
            e.result.message.stop_reason = "max_tokens"
            yield e
    client.results = cut
    assert batch.run(client, state, "k", {"n": {"messages": []}}, wait_minutes=1) == {}
    assert not state.pending("k") and not state.refused("k", "n")


def test_tokens_are_counted_by_kind_and_model(tmp_path, monkeypatch):
    monkeypatch.setattr(batch, "POLL", 0)
    client, state = Batches(lambda p: "ok"), batch.State(tmp_path / "batches.json")
    whole = client.results

    def metered(id):
        for e in whole(id):
            e.result.message.model = "m"
            e.result.message.usage = SimpleNamespace(input_tokens=10, output_tokens=3, cache_read_input_tokens=7,
                                                     cache_creation_input_tokens=None)
            yield e
    client.results = metered
    batch.run(client, state, "k", {"a": {}, "b": {}}, wait_minutes=1)
    assert batch.State(tmp_path / "batches.json").data["usage"]["k"]["m"] == {
        "replies": 2, "input": 20, "cache_written": 0, "cache_read": 14, "output": 6}


def test_nothing_new_is_sent_while_paused(tmp_path):
    client, state = Batches(lambda p: "ok"), batch.State(tmp_path / "batches.json")
    state.data["paused"] = True
    assert batch.run(client, state, "k", {"a": {}}, wait_minutes=0) == {} and not client.sent
