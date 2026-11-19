from dataclasses import dataclass,asdict,fields
import math
@dataclass(frozen=True)
class Policy:
    name:str='v3_evidence_constrained_material_union'
    maximum_edit_m:float=1e-7
    ambiguity_distance_m:float=1e-8
    source_boundary_distance_m:float=1e-7
    numerical_floor_m:float=1e-11
    maximum_interaction_pairs:int=20000
    require_solid:bool=True
    permit_connection_plane_repairs:bool=True
    def __post_init__(self):
        if not isinstance(self.name,str) or not self.name.strip():raise ValueError('Named policy required')
        for key in ['maximum_edit_m','ambiguity_distance_m','source_boundary_distance_m','numerical_floor_m']:
            value=getattr(self,key)
            if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value) or value<=0:raise ValueError('Invalid metric budget: '+key)
        if type(self.maximum_interaction_pairs) is not int or self.maximum_interaction_pairs<1:raise ValueError('Invalid pair budget')
        if type(self.require_solid) is not bool or type(self.permit_connection_plane_repairs) is not bool:raise ValueError('Expected booleans')
    def to_dict(self):return asdict(self)
    @classmethod
    def from_dict(cls,value):
        if set(value)-{f.name for f in fields(cls)}:raise ValueError('Unknown policy fields')
        return cls(**value)
