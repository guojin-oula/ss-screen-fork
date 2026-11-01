from monty.serialization import loadfn, dumpfn
from pymatgen.core.composition import Composition
from pymatgen.core import Structure
from robocrys import StructureCondenser, StructureDescriber
import click

@click.command('condense')
@click.argument('fin')
@click.argument('fout')
def main(fin, fout):
    """Process one structure"""
    ps = loadfn(fin)
    try:
        ps.add_oxidation_state_by_guess()
    except:
        pass
    try:
        condensed = StructureCondenser().condense_structure(ps)
    except Exception as e:
        click.echo(f'Failed to process {fin}')
        raise(e) 
        return 
    dumpfn(condensed, fout)
    return 

if __name__ == '__main__':
    main()
