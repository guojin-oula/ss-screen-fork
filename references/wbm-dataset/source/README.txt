# WBM-dataset

Original and converted WBM dataset

Paper:  H.-C. Wang, S. Botti, and M.A.L. Marques, NPJ Comput. Mater. 7, 12 (2021) doi:10.1038/s41524-020-00481-6

We converted the data into xyz format for easier access.
Also the summary.txt is cleaned as it contains invalid entries.

## Original README.txt 

See:
https://doi.org/10.24435/materialscloud:96-09

To read the json.bz2 files you can use the following code in python:

------------------------------------
#!/usr/bin/env python

import json, bz2
from pymatgen.entries.computed_entries import ComputedStructureEntry

with bz2.open("step_1.json.bz2") as fh:
  data = json.loads(fh.read().decode('utf-8'))

entries = [ComputedStructureEntry.from_dict(i) for i in data["entries"]]

print("Found " + str(len(entries)) + " entries")
print("\nEntry:\n", entries[0])
print("\nStructure:\n", entries[0].structure)
------------------------------------

Each file includes the calculations for a single substition step. In the 
article we present the results for three steps. We ended by performing 
also a forth step, and a part of the fifth. These calculations are also 
included here. All results are using the PBE approximation. The number 
of entries per file is

step_1.json.bz2	 61848
step_2.json.bz2	 52800
step_3.json.bz2	 79205
step_4.json.bz2	 40328
step_5.json.bz2	 23308
total		257489	

In the summary.txt file, the meaning of the columns is

1. chemical composition of the material
2. number of sites in the primitive unit cell
3. volume of the primitive unit cell in Angstroem^3
4. total energy in eV
5. energy of formation in eV
6. distance to the convex hull in eV
7. indirect band gap in eV

Note that the distance to the hull (and to a much lesser extent the 
energy of formation) depend on the reservoir compounds used to calculate 
the convex hull. In this case, we used the materials in the Materials 
Project database together with our own internal database. Note that the 
distances to the hull may be negative, as we exclude the composition 
from the hull during the calculation.
