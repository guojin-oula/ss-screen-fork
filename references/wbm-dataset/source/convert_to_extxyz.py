# Clean and convert the dataset into XYZ format

from monty.serialization import loadfn
import pandas as pd
from pymatgen.core import Composition
from pymatgen.io.ase import AseAtomsAdaptor
from ase.io import write
from tqdm import tqdm

# Load the entries
print('Reading entries')
entries = []
for i in range(1, 6):
    name = f'step_{i}.json.bz2'
    e = loadfn(name)['entries']
    for entry in e:
        entry.data['step'] = i
    entries.extend(e)
summary_df = pd.read_csv('summary.txt', delimiter='\t')
summary_df['reduced_form'] = summary_df['# comp'].apply(lambda x: Composition(x).reduced_formula)

# There are missing/mismatched data points - we split the df and entries in to clean and dirty parts
entries_clean = entries[:185450]
df_clean = summary_df.iloc[:185450]

entries_dirty = entries[185450:]
df_dirty = summary_df.iloc[185450:]

print('Cleaning the dataset')
# Match the entries with the rows in the dirty df

matched = set()

# Convert columns into lists for fast iteration
form = df_dirty.reduced_form.tolist()
nsites = df_dirty.nsites.tolist()
vol = df_dirty.vol.tolist()

for idx, entry in enumerate(tqdm(entries_dirty)):
    reduced_form = entry.composition.reduced_formula
    # Match each entry
    for i in range(len(df_dirty)):
        if i in matched:
            continue
        if form[i] != reduced_form:
            continue
        if nsites[i] != entry.structure.num_sites:
            continue
        if abs(vol[i] - entry.structure.volume) > 0.01:
            continue
        # Recorded the matched index
        entry.data['dirty_df_idx'] = i
        matched.add(i)
        break
    # Prompt for unmatched 
    if entry.data.get('dirty_df_idx') is None:
        print(f'Unmatch entry @ {idx}: {entry.composition.reduced_formula}')

df_rest = df_dirty.iloc[[entry.data['dirty_df_idx'] for entry in entries_dirty]]

assert len(df_rest) == len(entries_dirty)
# Combine to form the final dataframe
df_all = pd.concat([df_clean, df_rest], axis=0)
assert len(df_all) == len(entries)
df_all.reset_index()
df_all.to_csv('cleaned_summary.txt')

# Validate again
print('Validating the data')
for entry, (_, row) in zip(tqdm(entries), df_all.iterrows()):
    if row.vol != 0:
        assert abs(row.vol - entry.structure.volume) < 0.01
    assert row.nsites == entry.structure.num_sites
    assert row.reduced_form == entry.composition.reduced_formula

# Convert to xyz format
atoms_list = []
for entry in entries:
    atoms = AseAtomsAdaptor.get_atoms(entry.structure)
    atoms.info['WBM_energy'] = entry.energy
    atoms.info['WBM_step'] = entry.data['step']
    atoms_list.append(atoms)

i = 0
for atoms, (_idx, row) in zip(atoms_list, df_all.iterrows()):
    for name in ['nsites', 'vol', 'e', 'e_form', 'e_hull', 'gap']:
        atoms.info[f'WBM_{name}'] = getattr(row, name)
    atoms.info['WBM_idx'] = i
    i += 1

write('wbm-dataset.xyz', atoms_list)

