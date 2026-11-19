"""New references construct the cell arrangement before scaling its coordinates."""
import math
import numpy as np
from ifc_citygml_lab.fixtures import reference_mesh,specification

def corrected_reference(expected):
    family=expected['family'];scale=expected['scale'];gap=expected['gap_m']/scale
    parts,*_=specification(family,1.,gap)
    vertices,faces=reference_mesh(parts,family,1.)
    vertices=np.asarray(vertices,float)*scale
    angle=math.radians(expected['building_yaw']+expected['contents_yaw']);c,s=math.cos(angle),math.sin(angle)
    rotation=np.array([[c,-s,0],[s,c,0],[0,0,1]])
    vertices=vertices@rotation.T+np.asarray(expected['translation_m'])
    return {'vertices':vertices.tolist(),'triangles':faces,'method':'Unscaled cell arrangement followed by one scale and rigid transform; no floating scaled-axis reconstruction',
        'maximum_curve_chord_error_m':4*scale*(1-math.cos(math.pi/512)) if family=='cylinder' else 0.}

def corrected_expected(expected):
    result=dict(expected);result['reference_mesh']=corrected_reference(expected)
    result['reference_revision']='v3_unscaled_cell_arrangement';return result
