"""
Constants for atomic radii
"""

# XXX these seem like numbers we should be able to extract them from an
# external source or library, but it's not entirely clear where they're from
# and the existing dependencies either lack this information or are
# inconsistent.  CCTBX in particular uses different radii for protein atoms
# than what is reported in Wikipedia:
# https://github.com/cctbx/cctbx_project/blob/master/cctbx/eltbx/van_der_waals_radii.py
# Note that molmass.elements is more consistent with the table below, but it
# also lacks radii for many atoms that are relevant to ligand studies if not
# for protein models, such as boron.  But the Wikipedia entry for boron
# doesn't agree with the table here either!

vdwRadiiTable = {
    "H": 1.2,
    "HE": 1.4,
    "LI": 1.82,
    "BE": 1.78,
    "B": 1.74,
    "C": 1.7,
    "N": 1.55,
    "O": 1.52,
    "F": 1.47,
    "NE": 1.54,
    "NA": 2.27,
    "MG": 1.73,
    "AL": 1.8,
    "SI": 2.1,
    "P": 1.8,
    "S": 1.8,
    "CL": 1.75,
    "AR": 1.88,
    "K": 2.75,
    "CA": 2.65,
    "SC": 2.55,
    "TI": 2.45,
    "V": 2.35,
    "CR": 2.2,
    "MN": 1.73,
    "FE": 1.9,
    "CO": 1.75,
    "NI": 1.63,
    "CU": 1.4,
    "ZN": 1.39,
    "GA": 1.87,
    "GE": 1.86,
    "AS": 1.85,
    "SE": 1.9,
    "BR": 1.85,
    "KR": 2.02,
    "RB": 2.75,
    "SR": 2.65,
    "Y": 2.55,
    "ZR": 2.45,
    "NB": 2.35,
    "MO": 2.2,
    "TC": 2.05,
    "RU": 1.9,
    "RH": 1.75,
    "PD": 1.63,
    "AG": 1.72,
    "CD": 1.58,
    "IN": 1.93,
    "SN": 2.17,
    "SB": 2.1,
    "TE": 2.06,
    "I": 1.98,
    "XE": 2.16,
    "CS": 2.75,
    "BA": 2.75,
    "LA": 2.75,
    "CE": 2.75,
    "PR": 2.75,
    "ND": 2.75,
    "PM": 2.75,
    "SM": 2.75,
    "EU": 2.75,
    "GD": 2.75,
    "TB": 2.75,
    "DY": 2.75,
    "HO": 2.75,
    "ER": 2.75,
    "TM": 2.65,
    "YB": 2.55,
    "LU": 2.45,
    "HF": 2.35,
    "TA": 2.25,
    "W": 2.15,
    "RE": 2.05,
    "OS": 1.95,
    "IR": 1.85,
    "PT": 1.75,
    "AU": 1.66,
    "HG": 1.55,
    "TL": 1.96,
    "PB": 2.02,
    "BI": 2.0,
    "PO": 2.0,
    "AT": 2.0,
    "RN": 2.0,
    "FR": 2.75,
    "RA": 2.75,
    "AC": 2.5,
    "TH": 2.25,
    "PA": 1.95,
    "U": 1.86,
    "NP": 1.8,
    "PU": 1.8,
    "AM": 1.8,
    "CM": 1.8,
    "BK": 1.8,
    "CF": 1.8,
    "ES": 1.8,
    "FM": 1.8,
    "MD": 1.8,
    "NO": 1.8,
    "LR": 1.8,
    "RF": 1.8,
    "DB": 1.8,
    "SG": 1.8,
    "BH": 1.8,
    "HS": 1.8,
    "MT": 1.8,
    "UN": 1.8,
    "UU": 1.8,
    "UB": 1.8,
    "UQ": 1.8,
    "UH": 1.8,
    "UO": 1.8,
    "D": 1.3,
    "AN": 1.5,
}
# from xml.dom import minidom
#
# # parse an xml file by name
# mydoc = minidom.parse('/data/sauloho/qfit/qfit-3.0/qfit/epsilon.xml')
#
# firsts = mydoc.getElementsByTagName('first')
# seconds = mydoc.getElementsByTagName('second')
# epsilons = mydoc.getElementsByTagName('epsilon')
#
# print("EpsilonTable={")
# for first,second,epsilon in zip(firsts,seconds,epsilons):
#     print(f"\'{first.firstChild.data}\':{{\'{second.firstChild.data}\':{epsilon.firstChild.data}}},")
# print("}")

EpsilonTable = {
    "C": {"C": 0.150, "N": 0.155, "O": 0.173, "S": 0.173, "H": 0.055},
    "N": {"C": 0.155, "N": 0.160, "O": 0.179, "S": 0.179, "H": 0.057},
    "O": {"C": 0.173, "N": 0.179, "O": 0.200, "S": 0.200, "H": 0.063},
    "S": {"C": 0.173, "N": 0.179, "O": 0.200, "S": 0.200, "H": 0.063},
    "H": {"C": 0.055, "N": 0.057, "O": 0.063, "S": 0.063, "H": 0.020},
}

EpsilonIndex = ["H", "C", "N", "O", "S"]
EpsilonArray = [
    [0.020, 0.055, 0.057, 0.063, 0.063],  # H
    [0.055, 0.150, 0.155, 0.173, 0.173],  # C
    [0.057, 0.155, 0.160, 0.179, 0.179],  # N
    [0.063, 0.173, 0.179, 0.200, 0.200],  # O
    [0.063, 0.173, 0.179, 0.200, 0.200],
]  # S
