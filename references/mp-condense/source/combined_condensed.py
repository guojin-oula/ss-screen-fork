from monty.serialization import dumpfn, loadfn
from pathlib import Path
from tqdm import tqdm

data = {}
for file in tqdm(list(Path('condensed/').glob('*.json'))):
    data[file.stem] = loadfn(file)
    
dumpfn(data, 'condensed_combined.json')
