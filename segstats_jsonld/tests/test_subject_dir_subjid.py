"""-subjid with -s: stats from a subject directory that is not named after the
subject must attach to the input NIDM's subject, not to a new agent named
after the directory. -acq_filename: which of the subject's anatomical
acquisitions the stats are linked to."""
import shutil
import subprocess
import sys
import warnings
from pathlib import Path

import pytest
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import XSD

TESTDATA = Path(__file__).resolve().parent / "testdata"
REPO_ROOT = Path(__file__).resolve().parents[2]
NDAR_ID = URIRef("https://ndar.nih.gov/api/datadictionary/v2/dataelement/src_subject_id")
PROV = Namespace("http://www.w3.org/ns/prov#")
SIO_SUBJECT = URIRef("http://semanticscience.org/ontology/sio.owl#Subject")
SUBJECT = URIRef("http://iri.nidash.org/subject-51456")
NOT_LINKED = "the stats are not linked to an acquisition"

INPUT_TTL = f"""
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix ndar: <https://ndar.nih.gov/api/datadictionary/v2/dataelement/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix nidm: <http://purl.org/nidash/nidm#> .
<http://iri.nidash.org/project> a nidm:Project, prov:Activity .
<{SUBJECT}> a prov:Agent, prov:Person ;
    ndar:src_subject_id "51456"^^xsd:string .
"""

# Anatomical acquisitions for the subject: two sessions, two runs in ses-1
ACQ_NAMES = ("ses-1_run-1", "ses-1_run-2", "ses-2_run-1")
ACQ_TTL = INPUT_TTL + "".join(f"""
<http://iri.nidash.org/acq-{name}> a nidm:AcquisitionObject, prov:Entity ;
    nidm:hadAcquisitionModality nidm:MagneticResonanceImaging ;
    nidm:hadImageUsageType nidm:Anatomical ;
    <http://www.semanticdesktop.org/ontologies/2007/03/22/nfo#filename>
        "bids::sub-0051456/{name[:5]}/anat/sub-0051456_{name}_T1w.nii.gz"^^xsd:string ;
    prov:wasGeneratedBy <http://iri.nidash.org/act-{name}> .
<http://iri.nidash.org/act-{name}> a prov:Activity ;
    prov:qualifiedAssociation [ a prov:Association ; prov:agent <{SUBJECT}> ] .
""" for name in ACQ_NAMES)
ACQ = {name: URIRef(f"http://iri.nidash.org/acq-{name}") for name in ACQ_NAMES}


def t1w(name):
    return f"/bids/sub-0051456/{name[:5]}/anat/sub-0051456_{name}_T1w.nii.gz"


def run_fs_to_nidm(tmp_path, *extra, input_ttl=INPUT_TTL):
    # The layout freesurfer-nidm writes: <out>/sub-<id>/freesurfer
    subject_dir = tmp_path / "sub-0051456" / "freesurfer"
    (subject_dir / "stats").mkdir(parents=True)
    shutil.copy(TESTDATA / "aseg.stats", subject_dir / "stats" / "aseg.stats")
    # without a build stamp fs_to_nidm prompts for the FreeSurfer version
    (subject_dir / "scripts").mkdir()
    (subject_dir / "scripts" / "build-stamp.txt").write_text(
        "freesurfer-linux-centos7_x86_64-7.4.1-20230614-7eb8460\n")
    nidm = tmp_path / "nidm.ttl"
    nidm.write_text(input_ttl)
    result = subprocess.run(
        [sys.executable, "-m", "segstats_jsonld.fs_to_nidm", "-s", str(subject_dir),
         "-n", str(nidm), "--forcenidm", *extra],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return Graph().parse(nidm, format="turtle"), result.stderr


def subject_agents(g):
    """Agents that the stats activities are associated with in the subject role."""
    agents = set()
    for assoc in g.subjects(PROV.hadRole, SIO_SUBJECT):
        agents.update(g.objects(assoc, PROV.agent))
    return agents


def used_acquisitions(g):
    return set(g.objects(None, PROV.used)) & set(ACQ.values())


def test_subjid_attaches_stats_to_the_input_subject(tmp_path):
    g, _ = run_fs_to_nidm(tmp_path, "-subjid", "sub-0051456")
    assert subject_agents(g) == {SUBJECT}
    ids = {str(o) for o in g.objects(None, NDAR_ID)}
    assert ids == {"51456"}
    assert not list(g.subjects(None, Literal("freesurfer", datatype=XSD.string)))


def test_without_subjid_the_directory_name_is_the_subject_id(tmp_path):
    """The previous behaviour, kept for callers whose directory is named after
    the subject: here the directory is "freesurfer", so a new agent is made."""
    g, err = run_fs_to_nidm(tmp_path)
    agents = subject_agents(g)
    assert SUBJECT not in agents
    assert list(g.subjects(None, Literal("freesurfer", datatype=XSD.string)))
    # the case behind #21 must be visible to a caller that only reads warnings
    assert "Subject ID freesurfer not found in the input NIDM" in err


def test_acq_filename_picks_the_acquisition_among_several(tmp_path):
    g, err = run_fs_to_nidm(tmp_path, "-subjid", "sub-0051456", "-acq_filename",
                            t1w("ses-2_run-1"), input_ttl=ACQ_TTL)
    assert subject_agents(g) == {SUBJECT}
    assert used_acquisitions(g) == {ACQ["ses-2_run-1"]}
    assert NOT_LINKED not in err


def test_every_run_recon_all_averaged_is_linked(tmp_path):
    g, err = run_fs_to_nidm(tmp_path, "-subjid", "sub-0051456", "-acq_filename",
                            t1w("ses-1_run-1"), t1w("ses-1_run-2"), input_ttl=ACQ_TTL)
    assert used_acquisitions(g) == {ACQ["ses-1_run-1"], ACQ["ses-1_run-2"]}
    assert NOT_LINKED not in err


def test_several_acquisitions_without_a_file_name_are_left_unlinked(tmp_path):
    """Used to raise "Expected exactly 1 AcquisitionObject"; the stats must still
    land on the subject, just without an acquisition link, and say so."""
    g, err = run_fs_to_nidm(tmp_path, "-subjid", "sub-0051456", input_ttl=ACQ_TTL)
    assert subject_agents(g) == {SUBJECT}
    assert used_acquisitions(g) == set()
    assert NOT_LINKED in err


def test_one_unmatched_file_name_leaves_all_unlinked(tmp_path):
    g, err = run_fs_to_nidm(tmp_path, "-subjid", "sub-0051456", "-acq_filename",
                            t1w("ses-1_run-1"), t1w("ses-3_run-1"), input_ttl=ACQ_TTL)
    assert subject_agents(g) == {SUBJECT}
    assert used_acquisitions(g) == set()
    assert NOT_LINKED in err


class Row:
    def __init__(self, acq, filename):
        self.acqObj, self.filename = URIRef(acq), filename and Literal(filename)


A, B = Row("a", "x/a_T1w.nii.gz"), Row("b", "x/b_T1w.nii.gz")


@pytest.mark.parametrize("rows, names, expected", [
    ([A], None, ["a"]),                              # single candidate
    ([Row("a", None)], None, ["a"]),                 # single, no file name
    ([A, B], None, []),                              # several, nothing named
    ([A, B], ["/in/b_T1w.nii.gz"], ["b"]),
    ([A, B], ["a_T1w.nii.gz", "b_T1w.nii.gz"], ["a", "b"]),
    ([A, B], ["a_T1w.nii.gz", "c_T1w.nii.gz"], []),  # one name unmatched
    ([A], ["b_T1w.nii.gz"], []),                     # named, no match
    ([A, Row("a2", "y/a_T1w.nii.gz")], ["a_T1w.nii.gz"], []),  # name matches two
    ([], None, []),
])
def test_select_acquisition(rows, names, expected):
    from segstats_jsonld.fs_to_nidm import select_acquisition
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        got = select_acquisition(rows, names, "sub-01")
    assert got == [URIRef(e) for e in expected]
    assert bool(caught) == (not expected)
