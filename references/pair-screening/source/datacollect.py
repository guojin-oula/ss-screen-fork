import pandas as pd
from tqdm.auto import tqdm
from monty.serialization import loadfn

from mp_offline.client import MPOffline, MaterialSummary
from pymatgen.core.composition import Composition
from pymatgen.core import Structure

def load_wbm_data(source_folder, outname):
    """Collect data from the the WBM dataset into a dataframe"""
    entries = []
    for i in range(1, 6):
        name = f'{source_folder}/step_{i}.json.bz2'
        entries.extend(loadfn(name)['entries'])
    summary_df = pd.read_csv('wbm-dataset/summary.txt', delimiter='\t')
    summary_df['reduced_form'] = summary_df['# comp'].apply(lambda x: Composition(x).reduced_formula)


    entries_clean = entries[:185450]
    df_clean = summary_df.iloc[:185450]

    entries_dirty = entries[185450:]
    df_dirty = summary_df.iloc[185450:].copy()

    matched = set()
    # Convert to lists for fast iteration
    form = df_dirty.reduced_form.tolist()
    nsites = df_dirty.nsites.tolist()
    vol = df_dirty.vol.tolist()

    for idx, entry in enumerate(tqdm(entries_dirty)):
        reduced_form = entry.composition.reduced_formula
        for i in range(len(df_dirty)):
            if i in matched:
                continue
                
            if form[i] != reduced_form:
                continue
            if nsites[i] != entry.structure.num_sites:
                continue
            if abs(vol[i] - entry.structure.volume) > 0.01:
                continue
            # Matched
            entry.data['dirty_df_idx'] = i
            matched.add(i)
            break
        if entry.data.get('dirty_df_idx') is None:
            print(f'Unmatch entry @ {idx}: {entry.composition.reduced_formula}')

    df_rest = df_dirty.iloc[[entry.data['dirty_df_idx'] for entry in entries_dirty]]
    assert len(df_rest) == len(entries_dirty)
    df_all = pd.concat([df_clean, df_rest], axis=0)
    # Reset and change the index to 'wbm-xxx', note that xxx starts from 0
    df_all.reset_index(drop=True)
    df_all.index = [f'wbm-{i}' for i in  df_all.index]
    
    assert len(df_all) == len(entries)

    # Validate again
    print('Validating the data')
    for entry, (_, row) in zip(entries, df_all.iterrows()):
        if row.vol != 0:
            assert abs(row.vol - entry.structure.volume) < 0.01
        assert row.nsites == entry.structure.num_sites
        assert row.reduced_form == entry.composition.reduced_formula
    # Compute various useful fields
    df_all['structure'] = [entry.structure for entry in entries]
    df_all['composition'] = df_all.structure.apply(lambda x: x.composition)
    df_all['band_gap'] = df_all.gap
    df_all['nelems'] = df_all['composition'].apply(lambda x: len(x.keys()))
    df_all['reduced_composition'] = df_all.composition.apply(lambda x: x.get_reduced_composition_and_factor()[0])
    df_all.to_pickle(f'{outname}.df')
    return df_all

    
def load_mp_dataset(outfile='mp-dataset'):

    client = MPOffline()

    col =['material_id', 'energy_above_hull', 'composition', 'structure', 'json_data']
    entries = client.query_all(MaterialSummary.energy_above_hull < 0.01, project=col)
    df = pd.DataFrame(entries, columns=col)
    df['composition'] = df['composition'].apply(Composition)
    df['structure'] = df['structure'].apply(Structure.from_dict)
    df['band_gap'] = df['json_data'].apply(lambda x: x['band_gap'])

    df['nelems'] = df['composition'].apply(lambda x: len(x.keys()))

    df['reduced_composition'] = df.composition.apply(lambda x: x.get_reduced_composition_and_factor()[0])

    df.set_index('material_id', inplace=True)
    df.to_pickle(f'{outfile}.df')
    return df