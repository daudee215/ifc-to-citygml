"""Declared physical representation selection for bounding-block aggregation."""

POLICY = "explicit_body_with_annotation_omissions_v1"


def representation_record(rep):
    context = rep.ContextOfItems
    return {"step_id": rep.id(), "ifc_class": rep.is_a(), "identifier": rep.RepresentationIdentifier,
            "representation_type": rep.RepresentationType, "context_step_id": context.id(),
            "context_type": getattr(context, "ContextType", None),
            "item_step_ids": [item.id() for item in rep.Items]}


def select_block_representations(element):
    """All Body reps; explicit fallback only when no Body; never recover a bad Body.

    Unrecognised/axis/footprint-only representations fail rather than being called
    annotations. Class names and geometric representation types do not determine
    whether a representation is an annotation.
    """
    reps = tuple(element.Representation.Representations)
    records = [representation_record(r) for r in reps]
    selection = {"policy": POLICY, "source_representations": records}
    if reps and all(r.RepresentationIdentifier == "Annotation" for r in reps):
        return [], {**selection, "status": "annotation_only", "selected_step_ids": [],
                    "excluded_representations": [{**r, "reason": "Explicit Annotation representation"} for r in records]}
    primary = [r for r in reps if r.RepresentationIdentifier == "Body"]
    chosen = primary or [r for r in reps if r.RepresentationIdentifier == "Body-FallBack"]
    if not chosen:
        raise ValueError("No supported physical Body/Body-FallBack representation; non-annotation data is not silently omitted")
    identifiers = {r.id() for r in chosen}
    return chosen, {**selection, "status": "selected", "selected_step_ids": [r.id() for r in chosen],
                    "selection_level": "Body" if primary else "Body-FallBack",
                    "excluded_representations": [{**r, "reason": "Not selected by physical Body precedence"}
                                                   for r in records if r["step_id"] not in identifiers]}
