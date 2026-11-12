"""The PyNIDM constants this converter uses, on whichever PyNIDM is installed.

Fixtures elsewhere build triples from the same symbols the converter
queries with, so a wrong value would pass them; pin the values here.
"""
import ast
import importlib.metadata
from pathlib import Path

import pytest
from rdflib import RDF, URIRef

import segstats_jsonld
from segstats_jsonld._pynidm import (
    NIDM_SUBJECTID_LOCALPART,
    NIDM_SUBJECTID_URI,
    PYNIDM_MAJOR,
    Constants,
)

PACKAGE = Path(segstats_jsonld.__file__).resolve().parent

# Every name the package takes from Constants, except NIDM_SUBJECTID
# (test_subject_id_term). The values end up in the NIDM files the converter
# writes, so a PyNIDM release that moved one would change the output without
# an error.
CONSTANTS = {
    "DCT": "http://purl.org/dc/terms/",
    # must equal the fs: prefix of mapping_data/fs_cde.ttl, which PyNIDM
    # resolves the measures against
    "FREESURFER": "https://surfer.nmr.mgh.harvard.edu/",
    "FSL": "http://purl.org/nidash/fsl#",
    "NDAR": "https://ndar.nih.gov/api/datadictionary/v2/dataelement/",
    "NFO": "http://www.semanticdesktop.org/ontologies/2007/03/22/nfo#",
    "NIDM": "http://purl.org/nidash/nidm#",
    "NIDM_NEUROIMAGING_ANALYSIS_SOFTWARE": "http://purl.org/nidash/nidm#NIDM_0000164",
    "NIIRI": "http://iri.nidash.org/",
    "PROV": "http://www.w3.org/ns/prov#",
    "SIO": "http://semanticscience.org/ontology/sio.owl#",
    "XSD": "http://www.w3.org/2001/XMLSchema#",
}

# All but the one term: the converter takes terms from these as NAMESPACE["term"]
NAMESPACES = sorted(set(CONSTANTS) - {"NIDM_NEUROIMAGING_ANALYSIS_SOFTWARE"})


def constants_used():
    """The Constants attributes each module of the package reads, by file name.

    Only the spelling ``Constants.NAME`` is counted, so a module that renames
    Constants on import or reads it with getattr fails here instead of
    escaping the count.
    """
    used = {}
    for path in sorted(PACKAGE.rglob("*.py")):
        if "tests" in path.relative_to(PACKAGE).parts:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                renamed = [a.asname for a in node.names
                           if a.name.split(".")[-1] == "Constants" and a.asname]
                assert not renamed, f"{path.name} imports Constants as {renamed}"
            elif isinstance(node, ast.Call):
                indirect = (isinstance(node.func, ast.Name) and node.func.id == "getattr"
                            and node.args and isinstance(node.args[0], ast.Name)
                            and node.args[0].id == "Constants")
                assert not indirect, f"{path.name} reads Constants with getattr"
            elif (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                    and node.value.id == "Constants"):
                used.setdefault(path.name, set()).add(node.attr)
    return used


def test_the_checkout_is_the_package_under_test():
    # conftest.py at the repository root puts the checkout first on sys.path
    assert PACKAGE == Path(__file__).resolve().parents[1] / "segstats_jsonld"


def test_pynidm_line():
    assert PYNIDM_MAJOR == int(importlib.metadata.version("pynidm").split(".")[0])
    assert PYNIDM_MAJOR in (4, 5)


def test_subject_id_term():
    assert NIDM_SUBJECTID_URI == (
        "https://ndar.nih.gov/api/datadictionary/v2/dataelement/src_subject_id"
    )
    assert NIDM_SUBJECTID_LOCALPART == "src_subject_id"


@pytest.mark.parametrize("name", sorted(CONSTANTS))
def test_constant(name):
    assert str(getattr(Constants, name)) == CONSTANTS[name]


@pytest.mark.parametrize("name", NAMESPACES)
def test_namespace_term(name):
    assert str(getattr(Constants, name)["term"]) == CONSTANTS[name] + "term"


def test_every_constant_the_package_uses_is_pinned():
    used = constants_used()
    # NIDM_SUBJECTID is a prov QualifiedName on PyNIDM 4 and a URIRef on 5;
    # only the shim may touch it, the other modules take NIDM_SUBJECTID_URI
    assert "NIDM_SUBJECTID" in used["_pynidm.py"]
    used["_pynidm.py"].discard("NIDM_SUBJECTID")
    assert set().union(*used.values()) == set(CONSTANTS)


def test_fsl_helpers():
    """The two fslutils functions that use PyNIDM; no other test imports the module."""
    from segstats_jsonld import fslutils

    fsl = CONSTANTS["FSL"]
    g = fslutils.create_cde_graph()
    elements = set(g.subjects(RDF.type, URIRef(fsl + "DataElement")))
    assert elements
    assert all(str(e).startswith(fsl + "fsl_") for e in elements)

    entity, _ = fslutils.convert_stats_to_nidm([("000001", "12"), ("000002", "3.5")])
    # prov QualifiedNames, whichever PyNIDM line is installed
    assert entity.identifier.uri.startswith(CONSTANTS["NIIRI"])
    assert {k.uri for k, _ in entity.attributes} >= {fsl + "fsl_000001", fsl + "fsl_000002"}
