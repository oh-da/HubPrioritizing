"""
One-command hub prioritization pipeline.

Every stage is a pure function (DataFrame / GeoDataFrame in, DataFrame out).
File paths are resolved only in :mod:`src.pipeline.inputs` and the
orchestrator (:mod:`src.pipeline.run`); stage modules never open files.

Column names follow the canonical notebook (``COMPLETE_TRANSIT_PIPELINE.ipynb``)
so that the final ``hub_prioritization_results.xlsx`` keeps the schema the
display page expects.
"""
