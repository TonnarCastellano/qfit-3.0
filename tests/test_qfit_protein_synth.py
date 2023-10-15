"""
Relatively fast integration tests of qfit_protein using synthetic data for
a variety of small peptides with several alternate conformers.
"""

import subprocess
import os.path as op
import os
import sys

from iotbx.file_reader import any_file
import pytest

from qfit.structure import Structure
from qfit.xtal.volume import XMap
from qfit.qfit import QFitOptions, QFitSegment
from qfit.utils.mock_utils import BaseTestRunner

DISABLE_SLOW = os.environ.get("QFIT_ENABLE_SLOW_TESTS", None) is None

class SyntheticMapRunner(BaseTestRunner):
    DATA = op.join(op.dirname(__file__), "data")

    def _get_file_path(self, base_name):
        return op.join(self.DATA, base_name)

    def _get_start_models(self, peptide_name):
        return (
            self._get_file_path(f"{peptide_name}_multiconf.pdb"),
            self._get_file_path(f"{peptide_name}_single.pdb"),
        )


class QfitProteinSyntheticDataRunner(SyntheticMapRunner):

    def _run_qfit_cli(self, pdb_file_multi, pdb_file_single, high_resolution):
        fmodel_mtz = self._create_fmodel(pdb_file_multi,
                                         high_resolution=high_resolution)
        os.symlink(pdb_file_single, "single.pdb")
        qfit_args = [
            "qfit_protein",
            fmodel_mtz,
            pdb_file_single,
            "--resolution",
            str(high_resolution),
            "--label",
            "FWT,PHIFWT",
            "--backbone-amplitude",
            "0.1",
            "--rotamer-neighborhood",
            "10",
            "--debug",
        ]
        print(" ".join(qfit_args))
        subprocess.check_call(qfit_args)
        return fmodel_mtz

    def _validate_new_fmodel(
        self,
        fmodel_in,
        high_resolution,
        expected_correlation=0.99,
        model_name="multiconformer_model2.pdb",
    ):
        fmodel_out = self._create_fmodel(model_name,
                                         high_resolution=high_resolution)
        # correlation of the single-conf 7-mer fmodel is 0.922
        self._compare_maps(fmodel_in, fmodel_out, expected_correlation)

    def _run_and_validate_identical_rotamers(
        self,
        pdb_multi,
        pdb_single,
        d_min,
        chi_radius=SyntheticMapRunner.CHI_RADIUS,
        expected_correlation=0.99,
        model_name="multiconformer_model2.pdb",
    ):
        fmodel_mtz = self._run_qfit_cli(pdb_multi, pdb_single, high_resolution=d_min)
        self._validate_new_fmodel(
            fmodel_in=fmodel_mtz,
            high_resolution=d_min,
            expected_correlation=expected_correlation
        )
        rotamers_in = self._get_model_rotamers(pdb_multi, chi_radius)
        rotamers_out = self._get_model_rotamers(model_name, chi_radius)
        for resi in rotamers_in.keys():
            assert rotamers_in[resi] == rotamers_out[resi]
        return rotamers_out


class TestQfitProteinSyntheticData(QfitProteinSyntheticDataRunner):

    def _run_kmer_and_validate_identical_rotamers(
        self, peptide_name, d_min, chi_radius=SyntheticMapRunner.CHI_RADIUS
    ):
        (pdb_multi, pdb_single) = self._get_start_models(peptide_name)
        return self._run_and_validate_identical_rotamers(
            pdb_multi, pdb_single, d_min, chi_radius
        )

    def _run_serine_monomer(self, space_group_symbol):
        (pdb_multi, pdb_single) = self._get_serine_monomer_with_symmetry(
            space_group_symbol)
        return self._run_and_validate_identical_rotamers(
            pdb_multi, pdb_single, d_min=1.5, chi_radius=5)

    @pytest.mark.slow
    def test_qfit_protein_ser_basic_box(self):
        """A single two-conformer Ser residue in a perfectly cubic P1 cell"""
        (pdb_multi, pdb_single) = self._get_serine_monomer_inputs()
        return self._run_and_validate_identical_rotamers(
            pdb_multi, pdb_single, d_min=1.5, chi_radius=5)

    @pytest.mark.fast
    def test_qfit_protein_ser_p1(self):
        """A single two-conformer Ser residue in an irregular triclinic cell"""
        self._run_serine_monomer("P1")

    @pytest.mark.fast
    def test_qfit_segment_ser_p1(self):
        """
        Run just the segment sampling routine on a single two-conformer Ser
        residue in an irregular triclinic cell
        """
        (pdb_multi, pdb_single) = self._get_serine_monomer_inputs()
        fmodel_mtz = self._create_fmodel(pdb_multi, high_resolution=1.5)
        xmap = XMap.fromfile(fmodel_mtz, label="FWT,PHIFWT")
        structure = Structure.fromfile(pdb_single)
        assert structure.n_residues() == 1
        assert len(list(structure.extract("record", "ATOM").residue_groups)) == 1
        qfit = QFitSegment(structure, xmap, QFitOptions())
        multiconf = qfit()

    @pytest.mark.slow
    def test_qfit_protein_ser_p21(self):
        """A single two-conformer Ser residue in a P21 cell"""
        self._run_serine_monomer("P21")

    @pytest.mark.slow
    def test_qfit_protein_ser_p4212(self):
        """A single two-conformer Ser residue in a P4212 cell"""
        self._run_serine_monomer("P4212")

    @pytest.mark.slow
    def test_qfit_protein_ser_p6322(self):
        """A single two-conformer Ser residue in a P6322 cell"""
        self._run_serine_monomer("P6322")

    @pytest.mark.slow
    def test_qfit_protein_ser_c2221(self):
        """A single two-conformer Ser residue in a C2221 cell"""
        self._run_serine_monomer("C2221")

    @pytest.mark.slow
    def test_qfit_protein_ser_i212121(self):
        """A single two-conformer Ser residue in a I212121 cell"""
        self._run_serine_monomer("I212121")

    @pytest.mark.slow
    def test_qfit_protein_ser_i422(self):
        """A single two-conformer Ser residue in a I422 cell"""
        self._run_serine_monomer("I422")

    @pytest.mark.slow
    def test_qfit_protein_3mer_arg_p21(self):
        """Build an Arg residue with two conformers"""
        self._run_kmer_and_validate_identical_rotamers("ARA", d_min=1.0, chi_radius=8)

    @pytest.mark.slow
    def test_qfit_protein_3mer_lys_p21(self):
        """Build a Lys residue with three rotameric conformations"""
        rotamers = self._run_kmer_and_validate_identical_rotamers(
            "AKA", d_min=1.2, chi_radius=15
        )
        assert len(rotamers) == 3  # just to be certain

    @pytest.mark.slow
    def test_qfit_protein_3mer_ser_p21(self):
        """Build a Ser residue with two rotamers at moderate resolution"""
        self._run_kmer_and_validate_identical_rotamers("ASA", 1.65, chi_radius=15)

    @pytest.mark.slow
    def test_qfit_protein_3mer_trp_2conf_p21(self):
        """
        Build a Trp residue with two rotamers at medium resolution
        """
        pdb_multi = self._get_file_path("AWA_2conf.pdb")
        pdb_single = self._get_file_path("AWA_single.pdb")
        rotamers = self._run_and_validate_identical_rotamers(
            pdb_multi,
            pdb_single,
            d_min=2.00009,
            chi_radius=15,
            # FIXME the associated CCP4 map input test consistently has a lower
            # correlation than the MTZ input version
            expected_correlation=0.9845,
        )
        # this should not find a third distinct conformation (although it may
        # have overlapped conformations of the same rotamer)
        assert len(rotamers[2]) == 2

    @pytest.mark.skipif(sys.platform == "darwin", reason="FIXME: Skipping due to CPLEX Error 5002 in CI tests")
    def test_qfit_protein_3mer_trp_3conf_p21(self):
        """
        Build a Trp residue with three different rotamers, two of them
        with overlapped 5-member rings
        """
        pdb_multi = self._get_file_path("AWA_3conf.pdb")
        pdb_single = self._get_file_path("AWA_single.pdb")
        rotamers = self._run_and_validate_identical_rotamers(
            pdb_multi, pdb_single, d_min=0.8
        )
        assert len(rotamers[2]) == 3
        s = Structure.fromfile("multiconformer_model2.pdb")
        trp_confs = [r for r in s.residues if r.resn[0] == "TRP"]
        # FIXME with the minimized model we get 4 confs, at any resolution
        assert len(trp_confs) >= 3

    def _validate_phe_3mer_confs(
        self, pdb_file_multi, new_model_name="multiconformer_model2.pdb"
    ):
        #rotamers_in = self._get_model_rotamers(pdb_file_multi)
        rotamers_out = self._get_model_rotamers(new_model_name, chi_radius=15)
        # Phe2 should have two rotamers, but this may occasionally appear as
        # three due to the ring flips, and we can't depend on which orientation
        # the ring ends up in
        assert (-177, 80) in rotamers_out[2]  # this doesn't flip???
        assert (-65, -85) in rotamers_out[2] or (-65, 85) in rotamers_out[2]

    @pytest.mark.slow
    def test_qfit_protein_3mer_phe_p21(self):
        """
        Build a Phe residue with two conformers in P21 at medium resolution
        """
        d_min = 1.5
        (pdb_multi, pdb_single) = self._get_start_models("AFA")
        fmodel_in = self._run_qfit_cli(pdb_multi, pdb_single, high_resolution=d_min)
        self._validate_phe_3mer_confs(pdb_multi)
        self._validate_new_fmodel(fmodel_in=fmodel_in, high_resolution=d_min)

    @pytest.mark.slow
    def test_qfit_protein_3mer_phe_p21_mmcif(self):
        """
        Build a Phe residue with two conformers using mmCIF input
        """
        d_min = 1.5
        (pdb_multi, pdb_single) = self._get_start_models("AFA")
        cif_single = "single_conf.cif"
        s = Structure.fromfile(pdb_single)
        s.tofile(cif_single)
        fmodel_in = self._run_qfit_cli(pdb_multi, cif_single, high_resolution=d_min)
        self._validate_phe_3mer_confs(pdb_multi, "multiconformer_model.cif")
        self._validate_new_fmodel(
            fmodel_in=fmodel_in,
            high_resolution=d_min, model_name="multiconformer_model.cif"
        )

    @pytest.mark.slow
    def test_qfit_protein_3mer_phe_p1(self):
        """
        Build a Phe residue with two conformers in a smaller P1 cell at
        medium resolution
        """
        d_min = 1.5
        new_models = []
        for pdb_file in self._get_start_models("AFA"):
            new_models.append(self._replace_symmetry(
                new_symmetry=("P1", (12, 6, 10, 90, 105, 90)),
                pdb_file=pdb_file))
        (pdb_multi, pdb_single) = new_models
        fmodel_in = self._run_qfit_cli(pdb_multi, pdb_single, high_resolution=d_min)
        self._validate_phe_3mer_confs(pdb_multi)
        self._validate_new_fmodel(fmodel_in=fmodel_in,
                                  high_resolution=d_min)

    @pytest.mark.slow
    def test_qfit_protein_7mer_peptide_p21(self):
        """
        Build a 7-mer peptide with multiple residues in double conformations
        """
        d_min = 1.3
        (pdb_multi, pdb_single) = self._get_start_models("GNNAFNS")
        fmodel_in = self._run_qfit_cli(pdb_multi, pdb_single, high_resolution=d_min)
        self._validate_7mer_confs(pdb_multi)
        self._validate_new_fmodel(fmodel_in, d_min, 0.95)

    @pytest.mark.slow
    def test_qfit_protein_7mer_peptide_p1(self):
        """
        Build a 7-mer peptide with multiple residues in double conformations
        in a smaller P1 cell.
        """
        d_min = 1.3
        new_models = []
        for pdb_file in self._get_start_models("GNNAFNS"):
            new_models.append(self._replace_symmetry(
                new_symmetry=("P1", (30, 10, 15, 90, 105, 90)),
                pdb_file=pdb_file))
        (pdb_multi, pdb_single) = new_models
        fmodel_in = self._run_qfit_cli(pdb_multi, pdb_single, high_resolution=d_min)
        self._validate_7mer_confs(pdb_multi)
        self._validate_new_fmodel(fmodel_in, d_min, 0.95)

    def _validate_7mer_confs(self, pdb_file_multi):
        rotamers_in = self._get_model_rotamers(pdb_file_multi)
        rotamers_out = self._get_model_rotamers(
            "multiconformer_model2.pdb", chi_radius=15
        )
        # Phe5 should have two rotamers, but this may occasionally appear as
        # three due to the ring flips, and we can't depend on which orientation
        # the ring ends up in
        assert (-177, 80) in rotamers_out[5]  # this doesn't flip???
        assert (-65, -85) in rotamers_out[5] or (-65, 85) in rotamers_out[5]
        # Asn are also awkward because of flips
        assert len(rotamers_out[3]) >= 2
        assert len(rotamers_out[6]) >= 2
        # these are all of the alt confs present in the fmodel structure
        assert rotamers_in[3] - rotamers_out[3] == set()
        assert rotamers_in[2] - rotamers_out[2] == set()

    @pytest.mark.skipif(DISABLE_SLOW, reason="Slow P6322 symmetry test disabled")
    def test_qfit_protein_3mer_lys_p6322_all_sites(self):
        """
        Iterate over all symmetry operators in the P6(3)22 space group and
        confirm that qFit builds three distinct rotamers starting from
        the symmetry mate coordinates
        """
        d_min = 1.2
        pdb_multi = self._get_file_path("AKA_p6322_3conf.pdb")
        pdb_single_start = self._get_file_path("AKA_p6322_single.pdb")
        for i_op, pdb_single in enumerate(
            self._iterate_symmetry_mate_models(pdb_single_start)
        ):
            print(f"running with model {op.basename(pdb_single)}")
            with self._run_in_tmpdir(f"op{i_op}"):
                rotamers = self._run_and_validate_identical_rotamers(
                    pdb_multi, pdb_single, d_min=d_min, chi_radius=15
                )
                assert len(rotamers[2]) == 3

    @pytest.mark.slow
    def test_qfit_protein_3mer_arg_sensitivity(self):
        """
        Build a low-occupancy Arg conformer.
        """
        d_min = 1.20059
        # FIXME this test is very sensitive to slight differences in input and
        # OS - in some circumstances it can detect occupancy as low as 0.28,
        # but not when using CCP4 input
        occ_B = 0.32
        (pdb_multi_start, pdb_single) = self._get_start_models("ARA")
        pdb_in = any_file(pdb_multi_start)
        symm = pdb_in.file_object.crystal_symmetry()
        pdbh = pdb_in.file_object.hierarchy
        cache = pdbh.atom_selection_cache()
        atoms = pdbh.atoms()
        occ = atoms.extract_occ()
        sele1 = cache.selection("altloc A")
        sele2 = cache.selection("altloc B")
        occ.set_selected(sele1, 1 - occ_B)
        occ.set_selected(sele2, occ_B)
        atoms.set_occ(occ)
        pdb_multi_new = "ARA_low_occ.pdb"
        pdbh.write_pdb_file(pdb_multi_new, crystal_symmetry=symm)
        self._run_and_validate_identical_rotamers(pdb_multi_new, pdb_single, d_min)

    #@pytest.mark.skip(reason="FIXME restore rebuilding support")
    @pytest.mark.slow
    def test_qfit_protein_3mer_arg_rebuild(self):
        d_min = 1.2
        (pdb_multi_start, pdb_single) = self._get_start_models("ARA")
        s = Structure.fromfile(pdb_single)
        s = s.extract("name", ("N", "CA", "CB", "C", "O")).copy()
        pdb_single_partial = "ara_single_partial.pdb"
        s.tofile(pdb_single_partial)
        self._run_and_validate_identical_rotamers(pdb_multi_start,
                                                  pdb_single_partial,
                                                  d_min)

    @pytest.mark.slow
    def test_qfit_protein_3mer_multiconformer(self):
        """
        Build a 3-mer peptide with three continuous conformations and one or
        two alternate rotamers for each residue
        """
        d_min = 1.2
        (pdb_multi, pdb_single) = self._get_start_models("SKH")
        rotamers = self._run_and_validate_identical_rotamers(
            pdb_multi, pdb_single, d_min=d_min, chi_radius=15
        )
        # TODO this test should also evaluate the occupancies, which are not
        # constrained between residues
        assert len(rotamers[1]) == 2
        assert len(rotamers[2]) == 3
        assert len(rotamers[3]) == 2


class TestQfitProteinSidechainRebuild(QfitProteinSyntheticDataRunner):
    """
    Integration tests for qfit_protein with sidechain rebuilding, covering
    all non-PRO/GLY/ALA residues
    """

    def _create_mock_multi_conf_3mer(self, resname, set_b_iso=10):
        """
        Create a tripeptide model AXA where the central residue is rebuilt
        to have two conformations with the most distant rotamers possible,
        as well as the sidechain-free single-conformer starting model.
        """
        ALA_3MER = open(self._get_file_path("AAA_single.pdb"), "rt").read()
        pdb_str = ALA_3MER.replace("ALA A   2", f"{resname} A   2")
        # this is the truncated-sidechain version; only the multi-conf pdb
        # has complete sidechains
        pdb_single = self._write_tmp_pdb(pdb_str, f"-{resname}-single")
        s_single = Structure.fromfile(pdb_single)
        res = s_single.copy().chains[0].conformers[0].residues[1]
        res.complete_residue()
        s = res.get_rebuilt_structure()
        res = s.chains[0].conformers[0].residues[1]
        best_rmsd = 0
        best_pair = []
        for i, angles1 in enumerate(res.rotamers[:-1]):
            res1 = res.copy()
            for k, chi in enumerate(angles1, start=1):
                res1.set_chi(k, chi)
            for j, angles2 in enumerate(res.rotamers[i+1:]):
                res2 = res.copy()
                for k, chi in enumerate(angles2, start=1):
                    res2.set_chi(k, chi)
                rmsd = res1.rmsd(res2)
                if rmsd > best_rmsd:
                    best_rmsd = rmsd
                    best_pair = (res1, res2)
        (res1, res2) = best_pair
        res1.q = 0.5
        res2.q = 0.5
        res1.atoms[0].parent().altloc = "A"
        res2.atoms[0].parent().altloc = "B"
        first_res = s_single.extract("resi 1").copy()
        last_res = s_single.extract("resi 3").copy()
        s_multi = first_res.combine(res1).combine(res2).combine(last_res)
        xrs = s_multi._pdb_hierarchy.extract_xray_structure()
        s_multi = s_multi.with_symmetry(xrs.crystal_symmetry())
        s_single = s_single.with_symmetry(xrs.crystal_symmetry())
        # XXX it is very important that these be the same initial values!
        s_multi.b = set_b_iso
        s_single.b = set_b_iso
        assert s_multi.natoms == 10 + 2 * len(res.name)
        pdb_multi = pdb_single.replace(f"-{resname}-single.pdb",
                                       f"-{resname}-multi.pdb")
        s_multi.tofile(pdb_multi)
        s_single.tofile(pdb_single)
        print(f"RMSD is {best_rmsd}")
        return (pdb_multi, pdb_single)

    def _run_rebuilt_multi_conformer_tripeptide(
            self,
            resname,
            d_min=1.5,
            chi_radius=SyntheticMapRunner.CHI_RADIUS):
        """
        Create a fake two-conformer structure for an A*A peptide where the
        central residue is the specified type, and a single-conformer starting
        model with truncated sidechains
        """
        pdb_multi, pdb_single = self._create_mock_multi_conf_3mer(resname)
        return self._run_and_validate_identical_rotamers(
            pdb_multi, pdb_single, d_min, chi_radius)

    @pytest.mark.slow
    def test_qfit_protein_rebuilt_tripeptide_arg(self):
        self._run_rebuilt_multi_conformer_tripeptide("ARG", d_min=1.4)

    @pytest.mark.slow
    def test_qfit_protein_rebuilt_tripeptide_asn(self):
        self._run_rebuilt_multi_conformer_tripeptide("ASN")

    @pytest.mark.slow
    def test_qfit_protein_rebuilt_tripeptide_asp(self):
        self._run_rebuilt_multi_conformer_tripeptide("ASP")

    @pytest.mark.slow
    def test_qfit_protein_rebuilt_tripeptide_cys(self):
        self._run_rebuilt_multi_conformer_tripeptide("CYS")

    @pytest.mark.slow
    def test_qfit_protein_rebuilt_tripeptide_gln(self):
        self._run_rebuilt_multi_conformer_tripeptide("GLN", d_min=1.4)

    @pytest.mark.slow
    def test_qfit_protein_rebuilt_tripeptide_glu(self):
        self._run_rebuilt_multi_conformer_tripeptide("GLU", d_min=1.3)

    @pytest.mark.slow
    def test_qfit_protein_rebuilt_tripeptide_his(self):
        self._run_rebuilt_multi_conformer_tripeptide("HIS")

    @pytest.mark.slow
    def test_qfit_protein_rebuilt_tripeptide_ile(self):
        self._run_rebuilt_multi_conformer_tripeptide("ILE")

    @pytest.mark.slow
    def test_qfit_protein_rebuilt_tripeptide_leu(self):
        self._run_rebuilt_multi_conformer_tripeptide("LEU")

    @pytest.mark.slow
    def test_qfit_protein_rebuilt_tripeptide_lys(self):
        self._run_rebuilt_multi_conformer_tripeptide("LYS", d_min=1.4)

    @pytest.mark.slow
    def test_qfit_protein_rebuilt_tripeptide_met(self):
        self._run_rebuilt_multi_conformer_tripeptide("MET")

    @pytest.mark.slow
    def test_qfit_protein_rebuilt_tripeptide_phe(self):
        self._run_rebuilt_multi_conformer_tripeptide("PHE", d_min=1.3)

    @pytest.mark.slow
    def test_qfit_protein_rebuilt_tripeptide_ser(self):
        self._run_rebuilt_multi_conformer_tripeptide("SER")

    @pytest.mark.slow
    def test_qfit_protein_rebuilt_tripeptide_thr(self):
        self._run_rebuilt_multi_conformer_tripeptide("THR")

    @pytest.mark.slow
    def test_qfit_protein_rebuilt_tripeptide_trp(self):
        self._run_rebuilt_multi_conformer_tripeptide("TRP")

    @pytest.mark.slow
    def test_qfit_protein_rebuilt_tripeptide_tyr(self):
        self._run_rebuilt_multi_conformer_tripeptide("TYR")

    @pytest.mark.slow
    def test_qfit_protein_rebuilt_tripeptide_val(self):
        self._run_rebuilt_multi_conformer_tripeptide("VAL")
