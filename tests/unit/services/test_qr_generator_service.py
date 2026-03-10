import io
import zipfile

import pytest

from app.services import qr_generator
from app.services.qr_generator import QRGeneratorParams, generate_qr_docs_zip


def test_safe_db_name_rejects_unsupported_characters():
    with pytest.raises(ValueError):
        qr_generator._safe_db_name("CashDB51]; DROP TABLE users;")


def test_generate_qr_docs_zip_skips_empty_datasets_and_builds_both_databases(monkeypatch):
    calls: list[tuple[str, str]] = []

    def _fake_query_rows(*, server, database, sql_login, sql_password, airport_code, surnames):
        calls.append((server, database))
        if "KC01" in server:
            return [{"LOGIN": "4007001", "NAME": "Иванов Иван", "NameExt": "QR-DATA-1"}]
        return []

    monkeypatch.setattr(qr_generator, "_query_rows", _fake_query_rows)
    monkeypatch.setattr(
        qr_generator,
        "_build_word_from_nameext",
        lambda rows, **kwargs: ("cashiers.docx", f"nameext:{len(rows)}".encode()),
    )
    monkeypatch.setattr(
        qr_generator,
        "_build_word_from_login",
        lambda rows, **kwargs: ("sip.docx", f"login:{len(rows)}".encode()),
    )

    payload = generate_qr_docs_zip(
        QRGeneratorParams(
            server="DC1-SRV-KC01.regstaer.local",
            database="CashDB51",
            sql_login="sa",
            sql_password="secret",
            airport_code="4007",
            surnames=None,
            add_login=False,
            both_databases=True,
        )
    )

    assert calls == [
        ("DC1-SRV-KC01.regstaer.local", "CashDB51"),
        ("DC1-SRV-KC02.regstaer.local", "CashDB51"),
    ]

    archive = zipfile.ZipFile(io.BytesIO(payload))
    assert sorted(archive.namelist()) == ["cashiers.docx", "sip.docx"]
    assert archive.read("cashiers.docx") == b"nameext:1"
    assert archive.read("sip.docx") == b"login:1"


def test_generate_qr_docs_zip_raises_when_no_rows_found(monkeypatch):
    monkeypatch.setattr(qr_generator, "_query_rows", lambda **kwargs: [])

    with pytest.raises(ValueError, match="Нет данных"):
        generate_qr_docs_zip(
            QRGeneratorParams(
                server="DC1-SRV-KC01.regstaer.local",
                database="CashDB51",
                sql_login="sa",
                sql_password="secret",
                airport_code="4007",
                surnames=None,
                add_login=False,
                both_databases=False,
            )
        )
