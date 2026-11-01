from ase.io import read, write
from pymatgen.io.ase import AseAtomsAdaptor
from monty import dumpfn
from monty.serialization import dumpfn
from tqdm import tqdm

atoms = read('../wbm-dataset.xyz@:')
for i, a in enumerate(tqdm(atoms)):
    ps = AseAtomsAdaptor.get_structure(a)
    dumpfn(ps, f'structures/wbm-{i}.json')
