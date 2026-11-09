"""An input NIDM without a nidm:Project: fs_to_nidm attaches the stats session
to the input's project, so it refuses such an input with a message instead of
failing with UnboundLocalError, and changes nothing."""
import hashlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from rdflib import Graph, Literal, RDF, URIRef, XSD

from segstats_jsonld._pynidm import NIDM_SUBJECTID_URI, Constants
from segstats_jsonld.fs_to_nidm import (
    InputNIDMError,
    ProjectLookupError,
    SubjectLookupError,
    _check_csv_subjects,
    add_seg_data,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "segstats_jsonld" / "tests"))
from test_cli_options import make_subject_dir, run  # noqa: E402

STATS = SimpleNamespace(uri="http://example.org/entity/fsstats")

SUBJECT_ONLY_TTL = """
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix ndar: <https://ndar.nih.gov/api/datadictionary/v2/dataelement/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
<http://iri.nidash.org/subject-51456> a prov:Agent, prov:Person ;
    ndar:src_subject_id "51456"^^xsd:string .
"""


def _subject_only_graph():
    graph = Graph()
    subject = URIRef("http://example.org/agent/participant")
    graph.add((subject, RDF.type, Constants.PROV["Agent"]))
    graph.add((subject, URIRef(NIDM_SUBJECTID_URI), Literal("0050002", datatype=XSD.string)))
    return graph


def md5(path):
    return hashlib.md5(path.read_bytes()).hexdigest()


def test_both_lookup_errors_are_input_nidm_errors():
    assert issubclass(ProjectLookupError, InputNIDMError)
    assert issubclass(SubjectLookupError, InputNIDMError)
    assert issubclass(InputNIDMError, LookupError)


@pytest.mark.parametrize("case", ["subject-without-project", "empty"])
def test_add_seg_data_refuses_an_input_without_a_project_and_leaves_it_unchanged(case):
    graph = _subject_only_graph() if case == "subject-without-project" else Graph()
    before = set(graph)

    with pytest.raises(ProjectLookupError, match="nidm:Project"):
        add_seg_data(graph, {"version": "7.4.1"}, "sub-0050002", STATS, add_to_nidm=True,
                     forceagent=True)

    assert set(graph) == before


def test_a_new_document_still_gets_its_own_project():
    """Without an input NIDM (add_to_nidm=False) the converter makes the project."""
    graph = Graph()
    add_seg_data(graph, {"version": "7.4.1"}, "sub-0050002", STATS)
    assert len(set(graph.subjects(RDF.type, Constants.NIDM["Project"]))) == 1


@pytest.mark.parametrize("content", [SUBJECT_ONLY_TTL, ""], ids=["subject-without-project", "empty"])
def test_cli_refuses_an_input_without_a_project_and_writes_nothing(tmp_path, content):
    subject_dir = make_subject_dir(tmp_path)
    nidm = tmp_path / "nidm.ttl"
    nidm.write_text(content)
    before = md5(nidm)
    files_before = set(tmp_path.rglob("*"))

    result = run("-s", str(subject_dir), "-subjid", "sub-0051456", "-n", str(nidm), "--forcenidm")

    assert result.returncode != 0
    assert "fs_to_nidm.py: error:" in result.stderr
    assert "nidm:Project" in result.stderr
    assert str(nidm) in result.stderr
    assert "Traceback" not in result.stderr
    assert md5(nidm) == before
    assert set(tmp_path.rglob("*")) == files_before


def test_csv_pre_check_refuses_an_input_without_a_project(tmp_path):
    nidm = tmp_path / "nidm.ttl"
    nidm.write_text(SUBJECT_ONLY_TTL)
    with pytest.raises(ProjectLookupError, match="nidm:Project"):
        _check_csv_subjects(str(nidm), ["51456"], forceagent=False)
