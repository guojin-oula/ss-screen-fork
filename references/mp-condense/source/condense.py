import mp_api
import pandas as pd
from mp_offline.client import MPOffline, MaterialSummary
from pymatgen.core.composition import Composition
from pymatgen.core import Structure
from tqdm.auto import tqdm
from robocrys import StructureCondenser, StructureDescriber
from monty.serialization import dumpfn
from joblib.parallel import Parallel, delayed
from pathlib import Path


def processone(mid, ps, condenser):
    """Process one structure"""
    fname = f'condensed/{mid}.json'
    if Path(fname).is_file():
        return mid, None
    try:
        ps.add_oxidation_state_by_guess()
    except:
        pass
    condensed = None
    try:
        condensed = condenser.condense_structure(ps)
    except:
        pass
    if condensed:
        dumpfn(condensed, f'condensed/{mid}.json')
    return mid

if __name__ == '__main__':

    client = MPOffline()
    
    col =['material_id', 'energy_above_hull', 'composition', 'structure', 'json_data']
    # Select only near stable structures to limit the size of the dataset
    entries = client.query_all(
        (MaterialSummary.energy_above_hull < 0.2),
        project=col)
    
    df = pd.DataFrame(entries, columns=col)
    df['composition'] = df['composition'].apply(Composition)
    df['structure'] = df['structure'].apply(Structure.from_dict)
    df['band_gap'] = df['json_data'].apply(lambda x: x['band_gap'])
    df['nelems'] = df['composition'].apply(lambda x: len(x.keys()))
    df['reduced_composition'] = df.composition.apply(lambda x: x.get_reduced_composition_and_factor()[0])
    df.set_index('material_id', inplace=True)
    
    # # Select ternary and (PBE) band gap smaller than 1 
    # df_t = df.loc[(df['nelems'] == 3)
    #             & (df['band_gap'] <= 1), :]
    
    condenser = StructureCondenser()
    data = [(index, row.structure) for index, row in df.iterrows()]
    processed = Parallel(n_jobs=8, verbose=10)(delayed(processone)(mid, ps, condenser) for mid, ps in data)
