"""Explicit representation targets and operational acceptance policies."""
from dataclasses import asdict,dataclass,fields
import math

@dataclass(frozen=True)
class Contract:
    name: str = 'guarded_material_union_v1'
    target: str = 'material_union'
    maximum_vertex_change_m: float = 1e-7
    validator_snap_m: float = 1e-6
    numerical_relation_tolerance_m: float = 1e-11
    require_source_relations: bool = True
    require_solid_diagnostic: bool = True
    allow_unresolved_contacts: bool = False
    coordinate_policy: str = 'engineering_only'

    def __post_init__(self):
        if self.target not in {'source','material_union','envelope','block','generalisation'}:raise ValueError('Unknown representation target')
        if not isinstance(self.name,str) or not self.name.strip():raise ValueError('A named contract is required')
        for key in ['maximum_vertex_change_m','validator_snap_m','numerical_relation_tolerance_m']:
            value=getattr(self,key)
            if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value) or value<=0:raise ValueError('Invalid physical budget: '+key)
        for key in ['require_source_relations','require_solid_diagnostic','allow_unresolved_contacts']:
            if type(getattr(self,key)) is not bool:raise ValueError('Expected boolean: '+key)
        if self.coordinate_policy not in {'engineering_only','verified_metadata_transform'}:raise ValueError('Unknown coordinate policy')
        if self.target=='source' and self.require_solid_diagnostic:raise ValueError('Source surfaces cannot require an aggregate Solid')

    def to_dict(self):return asdict(self)
    @classmethod
    def from_dict(cls,value):
        unknown=set(value)-{f.name for f in fields(cls)}
        if unknown:raise ValueError('Unknown contract fields: '+','.join(sorted(unknown)))
        return cls(**value)

def default_contracts():
    return {
      'source':Contract(name='source_correspondence_v1',target='source',require_solid_diagnostic=False,require_source_relations=False).to_dict(),
      'material_union':Contract().to_dict(),
      'envelope':Contract(name='reviewed_envelope_v1',target='envelope').to_dict(),
      'block':Contract(name='bounds_only_v1',target='block',require_source_relations=False).to_dict(),
      'generalisation':Contract(name='declared_generalisation_v1',target='generalisation').to_dict()}
