from abc import ABC, abstractmethod
import os.path

import numpy as np
import copy

from .structure.math import Rz, Ry, gram_schmidt_orthonormal_zx


class _BaseSampler(ABC):
    @abstractmethod
    def __call__(self, *args, **kwds):
        ...


class BackboneRotator(_BaseSampler):

    """Rotate around phi, psi angles."""

    def __init__(self, segment):
        self.segment = segment
        self.ndofs = 2 * len(segment.residues)
        self._starting_coor = segment.coor

        # Check for each rotation which atoms are affected. Start with the last residue.
        self._aligners = []
        self._origins = []
        selections = []
        for (psi_sel, psi_axis, psi_origin,
             phi_sel, phi_axis, phi_origin) in segment.get_psi_phi_angles():
            selections += [psi_sel, phi_sel]
            psi_aligner = ZAxisAligner(psi_axis)
            phi_aligner = ZAxisAligner(phi_axis)
            self._aligners += [psi_aligner, phi_aligner]
            self._origins += [psi_origin, phi_origin]

        self._atoms_to_rotate = []
        for selection in selections:
            atoms_to_rotate = []
            if self._atoms_to_rotate:
                atoms_to_rotate = np.concatenate((self._atoms_to_rotate))
            atoms_to_rotate = np.concatenate((atoms_to_rotate, selection)).astype(
                np.int32
            )
            self._atoms_to_rotate.append(np.unique(atoms_to_rotate))

    def __call__(self, torsions):
        assert len(torsions) == self.ndofs, \
            "Number of torsions should equal degrees of freedom"

        # We start with the last torsion as this is more efficient
        torsions = np.deg2rad(torsions[::-1])

        self.segment.coor = self._starting_coor
        atoms_to_rotate = []
        iterator = zip(torsions, self._origins, self._aligners, self._atoms_to_rotate)
        for torsion, origin, aligner, atoms_to_rotate in iterator:
            if torsion == 0.0:
                continue
            coor = self.segment.get_xyz(atoms_to_rotate)
            coor -= origin
            R = aligner.forward_rotation @ Rz(torsion) @ aligner.backward_rotation
            coor = np.dot(coor, R.T)
            coor += origin
            self.segment.set_xyz(coor, atoms_to_rotate)


class Translator(_BaseSampler):
    def __init__(self, ligand):
        self.ligand = ligand
        self.coor_to_translate = self.ligand.coor

    def __call__(self, trans):
        self.ligand.coor = self.coor_to_translate + np.asarray(trans)


class CBAngleRotator(_BaseSampler):
    """Deflects a residue's sidechain by bending the CA-CB-CG angle. Rotate
    about the axis perpendicular to CB-CA and CB-CG vectors.

    Attributes:
        residue (qfit.Residue): Residue being manipulated.
        atoms_to_rotate (np.ndarray[int]): Atom indices that will be moved by
            the flexion.
    """

    def __init__(self, residue):
        """Inits a CBAngleRotator to flex the CA-CB-CG angle of a residue.

        Args:
            residue (qfit.Residue): Residue to manipulate.
        """
        self.residue = residue

        # These atoms define the angle
        angle_selection = residue.select("name", ("CA", "CB", "CG"))
        if angle_selection.size() != 3:
            raise RuntimeError("Residue does not have CA, CB and xG atom for rotation.")

        # Only atoms after CB can be moved
        self.atoms_to_rotate = residue.select(
            "name", ("N", "CA", "C", "O", "CB", "H", "HA", "HB2", "HB3"), "!="
        )

        # Define rotation unit vector
        self._origin = self.residue.extract("name", "CB").coor[0]
        self._coor_to_rotate = self.residue.get_xyz(self.atoms_to_rotate)
        self._coor_to_rotate -= self._origin
        axis_coor = self.residue.extract("name", ("CA", "CG")).coor
        axis_coor -= self._origin
        axis = np.cross(axis_coor[0], axis_coor[1])
        axis /= np.linalg.norm(axis)

        # Align rotation unit vector to Z-axis
        aligner = ZAxisAligner(axis)
        self._forward = aligner.forward_rotation
        self._coor_to_rotate = (aligner.backward_rotation @ self._coor_to_rotate.T).T

    def __call__(self, angle):
        """Flex CA-CB-CG by specified angle.

        Args:
            angle (int): Angle (degrees) for sidechain deflection.
        """
        # Since the axis of rotation is already aligned with the z-axis, we can
        # freely rotate the coordinates and perform the inverse operation to realign the
        # axis to the real world frame.
        rot_mat = self._forward @ Rz(np.deg2rad(angle))
        new_coor = (rot_mat @ self._coor_to_rotate.T).T + self._origin
        self.residue.set_xyz(new_coor, self.atoms_to_rotate)


class BisectingAngleRotator:
    """"
    Deflects a residue's sidechain by bending the CA-CB-CG angle. Rotate the
    aromatic side chain about an axis bisecting this angle. 

    Attributes:
        residue (qfit.Residue): Residue being manipulated.
        atoms_to_rotate (np.ndarray[int]): Atom indices that will be moved by
            the flexion.
    """
    
    def __init__(self, residue):
        """
        Inits a BisectingAngleRotator to rotate the sidechain about an axis
        bisecting the CA-CB-CG angle of a residue
        
        Args:
            residue (qfit.Residue): Residue to manipulate.
        """
        self.residue = residue

        # These atoms define the angle
        angle_selection = residue.select("name", ("CA", "CB", "CG"))
        if angle_selection.size() != 3:
            raise RuntimeError("Residue does not have CA, CB and xG atom for rotation.")

        # Only atoms after CB can be moved
        self.atoms_to_rotate = residue.select(
            "name", ("N", "CA", "C", "O", "CB", "H", "HA", "HB2", "HB3"), "!="
        )

        # Define the origin of rotation as the coordinates of the CB atom
        self._origin = self.residue.extract("name", "CB").coor[0]
        # Get the coordinates of the atoms to rotate 
        self._coor_to_rotate = self.residue.get_xyz(self.atoms_to_rotate)
        self._coor_to_rotate -= self._origin
        # Extract the coordinates of the CA and CG atoms, and translate them relative to the origin
        axis_coor = self.residue.extract("name", ("CA", "CG")).coor
        axis_coor -= self._origin

        # Normalize the vectors pointing from CB to CA and from CB to CG
        vec_CA = axis_coor[0]
        vec_CG = axis_coor[1]
        vec_CA /= np.linalg.norm(vec_CA)
        vec_CG /= np.linalg.norm(vec_CG)
        # Define a new rotation axis as the normalized sum of vec_CA and vec_CG. This makes the axis bisect the angle between these two vectors 
        new_axis = vec_CA + vec_CG
        new_axis /= np.linalg.norm(new_axis)
        self.new_axis = new_axis

       
        # Align the new rotation axis to the Z-axis to simplify the rotation transformation
        aligner = ZAxisAligner(new_axis)
        self._forward = aligner.forward_rotation
        self._coor_to_rotate = (aligner.backward_rotation @ self._coor_to_rotate.T).T

    def __call__(self, angle):
        # Since the axis of rotation is already aligned with the z-axis, we can
        # freely rotate the coordinates and perform the inverse operation to realign the
        # axis to the real world frame.
        R = self._forward @ Rz(np.deg2rad(angle))
        new_coor = (R @ self._coor_to_rotate.T).T + self._origin
        self.residue.set_xyz(new_coor, self.atoms_to_rotate)


class GlobalRotator(_BaseSampler):
    """Rotate ligand around its center."""

    def __init__(self, ligand, center=None):
        self.ligand = ligand
        self._center = center
        ligand_coor = self.ligand.coor
        if self._center is None:
            self._center = ligand_coor.mean(axis=0)
        self._coor_to_rotate = ligand_coor - self._center
        self._intermediate = np.zeros_like(ligand_coor)

    def __call__(self, rotmat):
        self._intermediate = np.dot(rotmat, self._coor_to_rotate.T).T
        self._intermediate += self._center
        self.ligand.coor = self._intermediate


class ChiRotator(_BaseSampler):

    """Rotate a residue around a chi-angle"""

    def __init__(self, residue, chi_index, covalent=None, length=None):
        self.residue = residue
        self.chi_index = chi_index
        # Get the coordinates that define the torsion angle
        torsion_atoms = self.residue.get_residue_info("chi")[chi_index]
        selection = self.residue.get_named_atom_selection(torsion_atoms)

        # Translate coordinates to center on coor[1]
        coor = self.residue.get_xyz(selection)
        self._origin = coor[1].copy()
        coor -= self._origin

        # Make an orthogonal axis system based on 3 atoms
        self._backward = gram_schmidt_orthonormal_zx(coor)
        self._forward = self._backward.T.copy()

        # Save the coordinates aligned along the Z-axis for fast future rotation
        atoms_to_rotate = self.residue.get_residue_info("chi-rotate")[chi_index]
        self._atom_selection = self.residue.select("name", atoms_to_rotate)
        if covalent in atoms_to_rotate:
            # If we are rotating the atom that is covalently bonded
            # to the ligand, we should also rotate the ligand.
            atoms_to_rotate2 = self.residue.name[length:]
            atom_selection2 = self.residue.select("name", atoms_to_rotate2)
            tmp = list(self._atom_selection)
            tmp += list(atom_selection2)
            self._atom_selection = np.array(tmp, dtype=int)
        self._coor_to_rotate = np.dot(
            self.residue.get_xyz(self._atom_selection) - self._origin, self._backward.T
        )
        self._tmp = np.zeros_like(self._coor_to_rotate)

    def __call__(self, angle):
        R = self._forward @ Rz(np.deg2rad(angle))
        np.dot(self._coor_to_rotate, R.T, self._tmp)
        self._tmp += self._origin
        self.residue.set_xyz(self._tmp, self._atom_selection)


# XXX unused, delete?
class CovalentBondRotator(_BaseSampler):

    """Rotate ligand along the bond of two atoms."""

    def __init__(self, covalent_residue, ligand, a1, a2):
        # Atoms connected to a1 will stay fixed.
        self.ligand = ligand
        self.residue = covalent_residue
        self.atom1 = a1
        self.atom2 = a2

        # Determine which atoms will be moved by the rotation.
        self._root = covalent_residue.name.tolist().index(a1)
        self._conn = ligand.connectivity
        self.atoms_to_rotate = range(len(ligand.name))

        # Find the rigid motion that aligns the axis of rotation onto the z-axis.
        self._coor_to_rotate = self.ligand.coor[self.atoms_to_rotate].copy()
        # Move root to origin
        self._t = self.residue.coor[self._root]
        self._coor_to_rotate -= self._t
        # Find angle between rotation axis and x-axis
        axis = self._coor_to_rotate[1] / np.linalg.norm(self._coor_to_rotate[1, :-1])
        aligner = ZAxisAligner(axis)

        # Align the rotation axis to the z-axis for the coordinates
        self._forward = aligner.forward_rotation
        self._coor_to_rotate = (aligner.backward_rotation @ self._coor_to_rotate.T).T

    def __call__(self, angle):
        # Since the axis of rotation is already aligned with the z-axis, we can
        # freely rotate them and perform the inverse operation to realign the
        # axis to the real world frame.
        R = self._forward @ Rz(angle)
        rotated = (R @ self._coor_to_rotate.T).T + self._t
        coor = copy.deepcopy(self.ligand.coor)
        coor[self.atoms_to_rotate] = rotated
        return coor


class BondRotator(_BaseSampler):

    """Rotate ligand along the bond of two atoms."""

    def __init__(self, ligand, a1, a2):
        # Atoms connected to a1 will stay fixed.
        self.ligand = ligand
        self.atom1 = a1
        self.atom2 = a2

        # Determine which atoms will be moved by the rotation.
        atom_names = ligand.name.tolist()
        self._root = atom_names.index(a1)
        self._conn = ligand.connectivity
        self.atoms_to_rotate = [self._root]
        self._foundroot = 0
        curr = atom_names.index(a2)
        self._find_neighbours_recursively(curr)
        # if self._foundroot > 1:
        #    raise ValueError("Atoms are part of a ring. Bond cannot be rotated.")

        # Find the rigid motion that aligns the axis of rotation onto the z-axis.
        self._coor_to_rotate = self.ligand.coor[self.atoms_to_rotate].copy()
        # Move root to origin
        self._t = self.ligand.coor[self._root]
        self._coor_to_rotate -= self._t
        # Find angle between rotation axis and x-axis
        axis = self._coor_to_rotate[1] / np.linalg.norm(self._coor_to_rotate[1, :-1])
        aligner = ZAxisAligner(axis)

        # Align the rotation axis to the z-axis for the coordinates
        self._forward = aligner.forward_rotation
        self._coor_to_rotate = (aligner.backward_rotation @ self._coor_to_rotate.T).T

    def _find_neighbours_recursively(self, curr):
        self.atoms_to_rotate.append(curr)
        bonds = np.flatnonzero(self._conn[curr])
        for b in bonds:
            if b == self._root:
                self._foundroot += 1
            if b not in self.atoms_to_rotate:
                self._find_neighbours_recursively(b)

    # XXX why does this return the new coordinates instead of setting them?
    def __call__(self, angle):
        # print(self.ligand.coor)
        # Since the axis of rotation is already aligned with the z-axis, we can
        # freely rotate them and perform the inverse operation to realign the
        # axis to the real world frame.
        R = self._forward @ Rz(angle)
        rotated = (R @ self._coor_to_rotate.T).T + self._t
        coor = copy.deepcopy(self.ligand.coor)
        coor[self.atoms_to_rotate] = rotated
        return coor


class ZAxisAligner:
    """Find the rotation that aligns a vector to the Z-axis."""

    def __init__(self, axis):
        # Find angle between rotation axis and x-axis
        axis = axis / np.linalg.norm(axis[:-1])
        xaxis_angle = np.arccos(axis[0])
        if axis[1] < 0:
            xaxis_angle *= -1

        # Rotate around Z-axis
        self._Rz = Rz(xaxis_angle)
        axis = np.dot(self._Rz.T, axis.reshape(3, -1)).ravel()

        # Find angle between rotation axis and z-axis
        zaxis_angle = np.arccos(axis[2] / np.linalg.norm(axis))
        if axis[0] < 0:
            zaxis_angle *= -1
        self._Ry = Ry(zaxis_angle)

        # Check whether the transformation is correct.
        # Rotate around the Y-axis to align to the Z-axis.
        axis = np.dot(self._Ry.T, axis.reshape(3, -1)).ravel() / np.linalg.norm(axis)
        if not np.allclose(axis, [0, 0, 1]):
            raise ValueError(f"Axis {axis} is not aligned to z-axis.")

        self.backward_rotation = self._Ry.T @ self._Rz.T
        self.forward_rotation = self._Rz @ self._Ry


class RotationSets:
    LOCAL = (
        ("local_5_10.npy", 10, 5.00),
        ("local_5_100.npy", 100, 5.00),
        ("local_5_1000.npy", 1000, 5.00),
        ("local_10_10.npy", 10, 10.00),
        ("local_10_100.npy", 100, 10.00),
        ("local_10_1000.npy", 1000, 10.00),
    )

    _DATA_DIRECTORY = os.path.join(os.path.dirname(__file__), "data")

    @classmethod
    def get_local_set(cls, fname="local_10_10.npy"):
        quats = np.load(os.path.join(cls._DATA_DIRECTORY, fname))
        return cls.quats_to_rotmats(quats)

    @classmethod
    def local(cls, max_angle, nrots=100):
        quats = []
        radian_max_angle = np.deg2rad(max_angle)
        while len(quats) < nrots - 1:
            quat = cls.random_rotation()
            angle = 2 * np.arccos(quat[0])
            if angle <= radian_max_angle:
                quats.append(quat)
        quats.append(np.asarray([1, 0, 0, 0], dtype=np.float64))
        return np.asarray(quats)

    @staticmethod
    def quats_to_rotmats(quaternions):
        """Converts an array of quaternions to rotation matrices.

        Args:
            quaternions (np.ndarray[np.float]):
                A (n, 4) array of rotations, expressed as quaternions.

        Returns:
            np.ndarray[np.float]:
                A (n, 3, 3) array of rotations, expressed as rotation matrices.
        """

        # Unpack quaternions into columns of coefficients
        (w, x, y, z) = quaternions.T

        # Calculate the magnitude of the quats
        Nq = w**2 + x**2 + y**2 + z**2

        # Determine values of scalars required to make unit quats
        s = 1.0 / Nq

        # Calculate scaled X, Y, Z
        X, Y, Z = x * s * 2, y * s * 2, z * s * 2

        # Fill rotmats array
        rotmats = np.empty((quaternions.shape[0], 3, 3), dtype=np.float64)
        rotmats[:, 0, 0] = 1.0 - (y * Y + z * Z)
        rotmats[:, 0, 1] = x * Y - w * Z
        rotmats[:, 0, 2] = x * Z + w * Y

        rotmats[:, 1, 0] = x * Y + w * Z
        rotmats[:, 1, 1] = 1.0 - (x * X + z * Z)
        rotmats[:, 1, 2] = y * Z - w * X

        rotmats[:, 2, 0] = x * Z - w * Y
        rotmats[:, 2, 1] = y * Z + w * X
        rotmats[:, 2, 2] = 1.0 - (x * X + y * Y)

        # In place round to 8dp
        rotmats.round(decimals=8, out=rotmats)

        return rotmats

    @classmethod
    def random_rotation(cls):
        """Return a random rotation, expressed as a unit quaternion.

        This algorithm generates uniformly sampled unit quaternions.

        Returns:
            np.ndarray[float]: A (4,) unit quaternion for rotation.

        Citations:
            Marsaglia G: Choosing a Point from the Surface of a Sphere.
                Ann Math Stat 1972, 43:645–646.
                doi:10.1214/aoms/1177692644
        """
        # Choose e1, e2 independent uniform on (-1, 1), until s1 < 1
        s1 = 1
        while s1 >= 1.0:
            e1, e2 = np.random.uniform(-1, 1, size=(2,))
            s1 = e1**2 + e2**2

        # Choose e3, e4 independent uniform on (-1, 1), until s2 < 1
        s2 = 1
        while s2 >= 1.0:
            e3, e4 = np.random.uniform(-1, 1, size=(2,))
            s2 = e3**2 + e4**2

        # Then construct point on surface of 4-sphere
        root = np.sqrt((1 - s1) / s2)
        quat = np.array([e1, e2, e3 * root, e4 * root])

        return quat
