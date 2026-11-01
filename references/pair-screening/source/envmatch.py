# Code for matching based on environments
from typing import Optional
from dataclasses import dataclass
from pymatgen.core import Composition, Species
import numpy as np
import re

def find_unique_envs(condense_dict):
    """Locate the unique environments of different centre atoms in each structure"""
    envs = []
    for cs in condense_dict:
        if cs is None:
            envs.append([None, None])
            continue
        comp = Composition(cs['formula'])
        env = {str(key): set() for key in comp}
        for site_id, site in cs['sites'].items():
            pform = site['poly_formula']
            ptype = site['geometry']['type']
            # Handle case such as Hf1.5+
            elem = site['element']
            elem = re.match(r'[A-Z][a-z]?', elem).group(0)
            env[Species(elem).symbol].add((str(pform), ptype))
        envs.append([cs['formula'], env])
    return envs

def swap_elem_by_X(name, elem):
    """Swap the element in a string by X. For example CoCa3 to CoX3"""
    temp_comp = {key.symbol: value for key, value in Composition(name).items()}
    
    if elem in temp_comp:
        temp_comp['X'] = temp_comp[elem]
        temp_comp.pop(elem)
        name = Composition(temp_comp).formula
    return name    

def group_similar_structures(envs, comp_template, mp_ids):
    """locate structures with simular environment and group them together"""
    # Result holder
    reprs = []
    aelems = []
    comps = []
    xelems = []
    # Find the spectator elements - those not changed 
    spectator_elements = [x.symbol for x in  Composition(comp_template).keys() if x.symbol != 'X']
    
    #print(spectator_elements)
    # Iterate through all environments
    for comp, item in envs:
        # Skip if the information is missinrg, we make a random representation to avoid any matching
        if item is None:
            reprs.append(str(np.random.rand()))
            aelems.append('MISSING')
            comps.append('MISSING')
            xelems.append('MISSING')
            continue
        
        # Find the X element which is not the spectator_elements
        x_candidiate = list(filter(lambda x: x not in spectator_elements, item))
        assert len(x_candidiate) == 1
        elem = x_candidiate[0]

        # For an descriptor the environment we replace elem to X
       
        repr = str(sorted(list(item[elem]))) + '|'
        rest = []
        for x in spectator_elements:
            rest.append(x)
            for entry in item[x]:
                name, type = entry
                # Swap the X element back to X should it appear in the name part of the environment
                if name != 'None':
                    name = swap_elem_by_X(name, elem)
                rest.append(name + ',' + type)
        repr = repr + '|'.join(rest)
        
        # Collect results
        reprs.append(repr)
        aelems.append(sorted(spectator_elements))
        xelems.append(elem)
        comps.append(comp)
    #print(reprs)
    # Convert to numpy array
    aelems = np.array(aelems)
    comps = np.array(comps)
    xelems = np.array(xelems)
    # Find unique environment
    _, unique_idx, labels =  np.unique(reprs, return_index=True, return_inverse=True)

    # Filter for valid groups, e.g. there are more than one structures in the group    
    valid_group = [] 
    for idx in unique_idx:
        group_id = labels[idx]
        mask = labels == group_id
        # Number of structures in the group
        nin_group = sum(mask)
        # Elements in the group
        if nin_group > 1:
            valid_group.append(StructureGroup(
                entry_idx=np.where(mask)[0].tolist(),
                A_elements=aelems[mask].tolist(),
                compositions=comps[mask].tolist(),
                group_size=nin_group, 
                X_element=xelems[mask].tolist(),
                mp_ids=mp_ids[mask].tolist(),
                group_repr=reprs[idx]
            ))
    return valid_group

@dataclass
class StructureGroup:
    """
    Represents a group of structures with similar environments.

    Attributes:
        entry_idx (list): List of indices of the structures in the original dataset.
        A_elements (list): List of spectator elements common to all structures in the group.
        compositions (list): List of chemical formulas of the structures in the group.
        group_size (int): Number of structures in the group.
        X_element (list): List of the variable element (X) in the structures in the group.
        mp_ids (list): List of Materials Project IDs of the structures in the group.
        group_repr (str): String representation of the environment descriptor for the group.
    """
    entry_idx: list
    A_elements: list
    compositions: list
    group_size: int
    X_element: list
    mp_ids: list
    group_repr: str

    def __getitem___(self, key):
        return getattr(self, key)