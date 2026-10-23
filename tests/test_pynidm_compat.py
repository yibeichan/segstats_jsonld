"""The PyNIDM constants this converter uses, on whichever PyNIDM is installed.

Fixtures elsewhere build triples from the same symbols the converter
queries with, so a wrong value would pass them; pin the values here.
"""
from segstats_jsonld._pynidm import (
    NIDM_SUBJECTID_LOCALPART,
    NIDM_SUBJECTID_URI,
    PYNIDM_MAJOR,
    Constants,
)


def test_subject_id_term():
    assert NIDM_SUBJECTID_URI == (
        "https://ndar.nih.gov/api/datadictionary/v2/dataelement/src_subject_id"
    )
    assert NIDM_SUBJECTID_LOCALPART == "src_subject_id"


def test_namespaces():
    assert str(Constants.NIIRI) == "http://iri.nidash.org/"
    assert str(Constants.PROV) == "http://www.w3.org/ns/prov#"
    assert str(Constants.NIDM) == "http://purl.org/nidash/nidm#"
    assert PYNIDM_MAJOR in (4, 5)
