from aiida import orm
from ase.io import read
from aiida_vasp.workchains.v2 import VaspHybridBandUpdater

def get_upd_hse06(node):
    """
    Generate process builder for HSE band structure
    """
    hse_additions = {'lhfcalc': True, 'hfscreen': 0.2, 'precfock': 'fast', 'hflmax': 4}
    
    upd = VaspHybridBandUpdater().apply_preset(structure=node, overrides={
        'ispin': 1,
        'gga': None,
        'magmom': None,
        'ncore': 4,
        'kpar': 2,
        'sigma': 0.005,
        **hse_additions,
    },
         code='vasp-6.3.2@sugon-xh-v2', label=f'{node.get_formula()} {node.label} HSE06')
    upd.set_resources(num_machines=1, tot_num_mpiprocs=32)
    upd.set_options(max_wallclock_seconds=3600 * 48, queue_name='xhhctdnormal')
    # Only re-try twice if there is convergence problem
    upd.builder.scf.max_iterations = 2
    upd.set_kspacing(0.03)
    upd_relax = VaspRelaxUpdater(builder=upd.builder.relax)
    upd_relax.apply_preset(structure=node, overrides={
        'ispin': 1,
        'gga': None,
        'magmom': None,
        'ncore': 4,
        'kpar': 2
    },
         code='vasp-6.3.2@sugon-xh-v2', label=f'{node.get_formula()} {node.label} RELAX')
    upd_relax.set_resources(num_machines=1, tot_num_mpiprocs=8)
    upd_relax.set_options(max_wallclock_seconds=3600 * 12, queue_name='xhhctdnormal')
    upd_relax.set_relax_settings(keep_sp_workdir=True)
    upd_relax.set_kspacing(0.03)
    upd_relax.builder.vasp.clean_workdir = False # We must not clean in order to reuse the WAVECAR
    upd.set_band_settings(band_mode='bradcrack', line_density=20, kpoints_per_split=200, hybrid_reuse_wavecar=True)
    return upd

atoms = read('InSb.cif')
upd = get_upd_hse06(orm.StructureData(ase=atoms))
running = upd.submit()
print(f'Submitted workflow for InSb HSE06 band structure: {running}')